"""Regression test for dispatching several incoming channels.
"""

import dbus
import dbus.service

from servicetest import EventPattern, tp_name_prefix, tp_path_prefix, \
        call_async
from mctest import exec_test, SimulatedConnection, SimulatedClient, \
        create_fakecm_account, enable_fakecm_account, SimulatedChannel, \
        expect_client_setup
import constants as cs

def test(q, bus, mc):
    params = dbus.Dictionary({"account": "someguy@example.com",
        "password": "secrecy"}, signature='sv')
    cm_name_ref, account = create_fakecm_account(q, bus, mc, params)
    conn = enable_fakecm_account(q, bus, mc, account, params)

    text_fixed_properties = dbus.Dictionary({
        cs.CHANNEL + '.TargetHandleType': cs.HT_CONTACT,
        cs.CHANNEL + '.ChannelType': cs.CHANNEL_TYPE_TEXT,
        }, signature='sv')

    media_fixed_properties = dbus.Dictionary({
        cs.CHANNEL + '.TargetHandleType': cs.HT_CONTACT,
        cs.CHANNEL + '.ChannelType': cs.CHANNEL_TYPE_STREAMED_MEDIA,
        }, signature='sv')

    misc_fixed_properties = dbus.Dictionary({
        cs.CHANNEL + '.TargetHandleType': cs.HT_CONTACT,
        cs.CHANNEL + '.ChannelType': 'com.example.Extension',
        }, signature='sv')

    # Two clients want to observe, approve and handle channels. Empathy handles
    # VoIP, Kopete does not.
    empathy = SimulatedClient(q, bus, 'org.gnome.Empathy',
            observe=[text_fixed_properties, media_fixed_properties],
            approve=[text_fixed_properties, media_fixed_properties],
            handle=[text_fixed_properties, media_fixed_properties],
            bypass_approval=False)

    kopete = SimulatedClient(q, bus, 'org.kde.Kopete',
            observe=[text_fixed_properties], approve=[text_fixed_properties],
            handle=[text_fixed_properties], bypass_approval=False)

    # wait for MC to download the properties
    expect_client_setup(q, [empathy, kopete])

    # subscribe to the OperationList interface (MC assumes that until this
    # property has been retrieved once, nobody cares)

    cd = bus.get_object(cs.CD, cs.CD_PATH)
    cd_props = dbus.Interface(cd, cs.PROPERTIES_IFACE)
    assert cd_props.Get(cs.CD_IFACE_OP_LIST, 'DispatchOperations') == []

    # Part 1. A bundle that Empathy, but not Kopete, can handle

    text_channel_properties = dbus.Dictionary(text_fixed_properties,
            signature='sv')
    text_channel_properties[cs.CHANNEL + '.TargetID'] = 'juliet'
    text_channel_properties[cs.CHANNEL + '.TargetHandle'] = \
            conn.ensure_handle(cs.HT_CONTACT, 'juliet')
    text_channel_properties[cs.CHANNEL + '.InitiatorID'] = 'juliet'
    text_channel_properties[cs.CHANNEL + '.InitiatorHandle'] = \
            conn.ensure_handle(cs.HT_CONTACT, 'juliet')
    text_channel_properties[cs.CHANNEL + '.Requested'] = False
    text_channel_properties[cs.CHANNEL + '.Interfaces'] = dbus.Array(
            [cs.CHANNEL_IFACE_DESTROYABLE], signature='s')

    text_chan = SimulatedChannel(conn, text_channel_properties,
            destroyable=True)

    media_channel_properties = dbus.Dictionary(media_fixed_properties,
            signature='sv')
    media_channel_properties[cs.CHANNEL + '.TargetID'] = 'juliet'
    media_channel_properties[cs.CHANNEL + '.TargetHandle'] = \
            conn.ensure_handle(cs.HT_CONTACT, 'juliet')
    media_channel_properties[cs.CHANNEL + '.InitiatorID'] = 'juliet'
    media_channel_properties[cs.CHANNEL + '.InitiatorHandle'] = \
            conn.ensure_handle(cs.HT_CONTACT, 'juliet')
    media_channel_properties[cs.CHANNEL + '.Requested'] = False
    media_channel_properties[cs.CHANNEL + '.Interfaces'] = dbus.Array(
            signature='s')

    media_chan = SimulatedChannel(conn, media_channel_properties,
            destroyable=False)

    conn.NewChannels([text_chan, media_chan])

    # A channel dispatch operation is created

    e = q.expect('dbus-signal',
            path=cs.CD_PATH,
            interface=cs.CD_IFACE_OP_LIST,
            signal='NewDispatchOperation')

    cdo_path = e.args[0]
    cdo_properties = e.args[1]

    assert cdo_properties[cs.CDO + '.Account'] == account.object_path
    assert cdo_properties[cs.CDO + '.Connection'] == conn.object_path

    handlers = cdo_properties[cs.CDO + '.PossibleHandlers'][:]
    # only Empathy can handle the whole batch
    assert handlers == [cs.tp_name_prefix + '.Client.org.gnome.Empathy'], \
            handlers

    assert cs.CD_IFACE_OP_LIST in cd_props.Get(cs.CD, 'Interfaces')
    assert cd_props.Get(cs.CD_IFACE_OP_LIST, 'DispatchOperations') ==\
            [(cdo_path, cdo_properties)]

    cdo = bus.get_object(cs.CD, cdo_path)
    cdo_iface = dbus.Interface(cdo, cs.CDO)

    # Both Observers are told about the new channels

    e, k = q.expect_many(
            EventPattern('dbus-method-call',
                path=empathy.object_path,
                interface=cs.OBSERVER, method='ObserveChannels',
                handled=False),
            EventPattern('dbus-method-call',
                path=kopete.object_path,
                interface=cs.OBSERVER, method='ObserveChannels',
                handled=False),
            )
    assert e.args[0] == account.object_path, e.args
    assert e.args[1] == conn.object_path, e.args
    assert e.args[3] == cdo_path, e.args
    assert e.args[4] == [], e.args      # no requests satisfied
    channels = e.args[2]
    assert len(channels) == 2, channels
    assert (text_chan.object_path, text_channel_properties) in channels
    assert (media_chan.object_path, media_channel_properties) in channels

    # fd.o #21089: telepathy-spec doesn't say whether Kopete observes the whole
    # batch or just the text channel. In current MC, it only observes the text.
    assert k.args[0] == e.args[0], k.args
    assert k.args[1] == e.args[1], e.args
    assert k.args[2] == [(text_chan.object_path, text_channel_properties)]

    # Both Observers indicate that they are ready to proceed
    q.dbus_return(k.message, signature='')
    q.dbus_return(e.message, signature='')

    # The Approvers are next
    # fd.o #21090: telepathy-spec doesn't say whether Kopete is asked to
    # approve this CDO. In current MC, it is.
    e, k = q.expect_many(
            EventPattern('dbus-method-call',
                path=empathy.object_path,
                interface=cs.APPROVER, method='AddDispatchOperation',
                handled=False),
            EventPattern('dbus-method-call',
                path=kopete.object_path,
                interface=cs.APPROVER, method='AddDispatchOperation',
                handled=False),
            )
    assert len(e.args[0]) == 2
    assert (text_chan.object_path, text_channel_properties) in e.args[0]
    assert (media_chan.object_path, media_channel_properties) in e.args[0]
    assert e.args[1:] == [cdo_path, cdo_properties]
    assert k.args == e.args

    q.dbus_return(e.message, signature='')
    q.dbus_return(k.message, signature='')

    # Both Approvers now have a flashing icon or something, trying to get the
    # user's attention

    # The user doesn't care which one will handle the channels - because
    # Empathy is the only possibility, it will be chosen (this is also a
    # regression test for the ability to leave the handler unspecified).
    call_async(q, cdo_iface, 'HandleWith', '')

    # Empathy is asked to handle the channels
    e = q.expect('dbus-method-call',
            path=empathy.object_path,
            interface=cs.HANDLER, method='HandleChannels',
            handled=False)

    # Empathy accepts the channels
    q.dbus_return(e.message, signature='')

    # FIXME: this shouldn't happen until after HandleChannels has succeeded,
    # but MC currently does this as soon as HandleWith is called (fd.o #21003)
    #q.expect('dbus-signal', path=cdo_path, signal='Finished')
    #q.expect('dbus-signal', path=cs.CD_PATH,
    #    signal='DispatchOperationFinished', args=[cdo_path])

    # HandleWith succeeds
    q.expect('dbus-return', method='HandleWith')

    # Now there are no more active channel dispatch operations
    assert cd_props.Get(cs.CD_IFACE_OP_LIST, 'DispatchOperations') == []

    text_chan.close()
    media_chan.close()

    # Part 2. A bundle that neither client can handle in its entirety

    respawning_channel_properties = dbus.Dictionary(misc_fixed_properties,
            signature='sv')
    respawning_channel_properties[cs.CHANNEL + '.TargetID'] = 'juliet'
    respawning_channel_properties[cs.CHANNEL + '.TargetHandle'] = \
            conn.ensure_handle(cs.HT_CONTACT, 'juliet')
    respawning_channel_properties[cs.CHANNEL + '.InitiatorID'] = 'juliet'
    respawning_channel_properties[cs.CHANNEL + '.InitiatorHandle'] = \
            conn.ensure_handle(cs.HT_CONTACT, 'juliet')
    respawning_channel_properties[cs.CHANNEL + '.Requested'] = False
    respawning_channel_properties[cs.CHANNEL + '.Interfaces'] = dbus.Array(
            [cs.CHANNEL_IFACE_DESTROYABLE], signature='s')

    ext_channel_properties = dbus.Dictionary(misc_fixed_properties,
            signature='sv')
    ext_channel_properties[cs.CHANNEL + '.TargetID'] = 'juliet'
    ext_channel_properties[cs.CHANNEL + '.TargetHandle'] = \
            conn.ensure_handle(cs.HT_CONTACT, 'juliet')
    ext_channel_properties[cs.CHANNEL + '.InitiatorID'] = 'juliet'
    ext_channel_properties[cs.CHANNEL + '.InitiatorHandle'] = \
            conn.ensure_handle(cs.HT_CONTACT, 'juliet')
    ext_channel_properties[cs.CHANNEL + '.Requested'] = False
    ext_channel_properties[cs.CHANNEL + '.Interfaces'] = dbus.Array(
            signature='s')

    text_chan = SimulatedChannel(conn, text_channel_properties,
            destroyable=True)
    media_chan = SimulatedChannel(conn, media_channel_properties,
            destroyable=False)
    respawning_chan = SimulatedChannel(conn, respawning_channel_properties,
            destroyable=True)
    ext_chan = SimulatedChannel(conn, ext_channel_properties,
            destroyable=False)

    conn.NewChannels([text_chan, media_chan, ext_chan, respawning_chan])

    # No client can handle all four channels, so the bundle explodes into
    # two dispatch operations and two failures. We can only match the first
    # CDO here - we look at the others later.
    e_observe_media, e_observe_text, k_observe_text, \
    e_approve_media, e_approve_text, k_approve_text, \
    _, _, _ = q.expect_many(
            EventPattern('dbus-method-call',
                path=empathy.object_path,
                interface=cs.OBSERVER, method='ObserveChannels',
                predicate=(lambda e: e.args[2][0][0] == media_chan.object_path),
                handled=False),
            EventPattern('dbus-method-call',
                path=empathy.object_path,
                interface=cs.OBSERVER, method='ObserveChannels',
                predicate=(lambda e: e.args[2][0][0] == text_chan.object_path),
                handled=False),
            EventPattern('dbus-method-call',
                path=kopete.object_path,
                interface=cs.OBSERVER, method='ObserveChannels',
                predicate=(lambda e: e.args[2][0][0] == text_chan.object_path),
                handled=False),
            EventPattern('dbus-method-call',
                path=empathy.object_path,
                interface=cs.APPROVER, method='AddDispatchOperation',
                predicate=(lambda e:
                    e.args[0][0][0] ==
                    media_chan.object_path),
                handled=False),
            EventPattern('dbus-method-call',
                path=empathy.object_path,
                interface=cs.APPROVER, method='AddDispatchOperation',
                predicate=(lambda e:
                    e.args[0][0][0] ==
                    text_chan.object_path),
                handled=False),
            EventPattern('dbus-method-call',
                path=kopete.object_path,
                interface=cs.APPROVER, method='AddDispatchOperation',
                predicate=(lambda e:
                    e.args[0][0][0] ==
                    text_chan.object_path),
                handled=False),
            EventPattern('dbus-method-call',
                interface=cs.CHANNEL_IFACE_DESTROYABLE,
                method='Destroy',
                path=respawning_chan.object_path,
                handled=True),
            EventPattern('dbus-method-call',
                interface=cs.CHANNEL,
                method='Close',
                path=ext_chan.object_path,
                handled=True),
            # we can't distinguish between the two NewDispatchOperation signals
            # since we no longer see the Channels property (it's mutable)
            EventPattern('dbus-signal',
                path=cs.CD_PATH,
                interface=cs.CD_IFACE_OP_LIST,
                signal='NewDispatchOperation'),
            )

    q.dbus_return(e_observe_media.message, signature='')
    q.dbus_return(e_observe_text.message, signature='')
    q.dbus_return(k_observe_text.message, signature='')
    q.dbus_return(e_approve_media.message, signature='')
    q.dbus_return(e_approve_text.message, signature='')
    q.dbus_return(k_approve_text.message, signature='')

if __name__ == '__main__':
    exec_test(test, {})
