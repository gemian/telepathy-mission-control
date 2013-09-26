# Copyright (C) 2009 Nokia Corporation
# Copyright (C) 2009 Collabora Ltd.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301 USA

import dbus
"""Regression test for the unofficial Account.Interface.Requests API when
a channel can be created successfully.
"""

import dbus
import dbus.service

from servicetest import (EventPattern, tp_name_prefix, tp_path_prefix,
        call_async, assertEquals, assertContains, assertLength)
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

    client = SimulatedClient(q, bus, 'Empathy',
            observe=[text_fixed_properties], approve=[text_fixed_properties],
            handle=[text_fixed_properties], bypass_approval=False)

    # This client doesn't say it can handle channels, but if it requests one
    # for itself, we'll at least try dispatching to it.
    #
    # A real-world use case for this is if a client wants to request channels,
    # and handle the channels that it, itself, requested, but not handle
    # anything requested by others: for instance, nautilus-sendto behaves
    # like this. See fd.o #23651
    unsuitable = SimulatedClient(q, bus, 'Unsuitable',
            observe=[], approve=[], handle=[], is_handler=True,
            bypass_approval=False)

    # No Approver should be invoked at any point during this test, because the
    # Channel was Requested
    def fail_on_approval(e):
        raise AssertionError('Approver should not be invoked')
    q.add_dbus_method_impl(fail_on_approval, path=client.object_path,
            interface=cs.APPROVER, method='AddDispatchOperation')

    # wait for MC to download the properties
    expect_client_setup(q, [client, unsuitable])

    test_channel_creation(q, bus, account, client, conn, False)
    test_channel_creation(q, bus, account, client, conn, True)
    test_channel_creation(q, bus, account, client, conn, False, unsuitable)
    test_channel_creation(q, bus, account, client, conn, False, unsuitable,
            cs.CHANNEL_TYPE_CALL)

def test_channel_creation(q, bus, account, client, conn,
        ensure=False, prefer=None, channel_type=cs.CHANNEL_TYPE_TEXT):
    user_action_time = dbus.Int64(1238582606)

    if prefer is None:
        prefer = client

    cd = bus.get_object(cs.CD, cs.CD_PATH)
    cd_props = dbus.Interface(cd, cs.PROPERTIES_IFACE)

    # chat UI calls ChannelDispatcher.EnsureChannel or CreateChannel
    request = dbus.Dictionary({
            cs.CHANNEL + '.ChannelType': channel_type,
            cs.CHANNEL + '.TargetHandleType': cs.HT_CONTACT,
            cs.CHANNEL + '.TargetID': 'juliet',
            }, signature='sv')
    call_async(q, cd,
            (ensure and 'EnsureChannel' or 'CreateChannel'),
            account.object_path, request, user_action_time, prefer.bus_name,
            dbus.Dictionary({}, signature='sv'),
            dbus_interface=cs.CD)
    ret = q.expect('dbus-return',
            method=(ensure and 'EnsureChannel' or 'CreateChannel'))
    request_path = ret.value[0]

    # chat UI connects to signals and calls ChannelRequest.Proceed()

    cr = bus.get_object(cs.AM, request_path)
    request_props = cr.GetAll(cs.CR, dbus_interface=cs.PROPERTIES_IFACE)
    assert request_props['Account'] == account.object_path
    assert request_props['Requests'] == [request]
    assert request_props['UserActionTime'] == user_action_time
    assert request_props['PreferredHandler'] == prefer.bus_name
    assert request_props['Interfaces'] == []

    cr.Proceed(dbus_interface=cs.CR)

    # FIXME: should the EnsureChannel/CreateChannel call, and the AddRequest
    # call, be in a defined order? Probably not though, since CMs and Clients
    # aren't meant to be the same process!

    cm_request_call, add_request_call = q.expect_many(
            EventPattern('dbus-method-call',
                interface=cs.CONN_IFACE_REQUESTS,
                method=(ensure and 'EnsureChannel' or 'CreateChannel'),
                path=conn.object_path, args=[request], handled=False),
            EventPattern('dbus-method-call', handled=False,
                interface=cs.CLIENT_IFACE_REQUESTS,
                method='AddRequest'),
            )

    assert add_request_call.args[0] == request_path
    assert add_request_call.path == prefer.object_path
    request_props = add_request_call.args[1]
    assert request_props[cs.CR + '.Account'] == account.object_path
    assert request_props[cs.CR + '.Requests'] == [request]
    assert request_props[cs.CR + '.UserActionTime'] == user_action_time
    assert request_props[cs.CR + '.PreferredHandler'] == prefer.bus_name
    assert request_props[cs.CR + '.Interfaces'] == []

    q.dbus_return(add_request_call.message, signature='')

    # Time passes. A channel is returned.

    channel_immutable = dbus.Dictionary(request)
    channel_immutable[cs.CHANNEL + '.InitiatorID'] = conn.self_ident
    channel_immutable[cs.CHANNEL + '.InitiatorHandle'] = conn.self_handle
    channel_immutable[cs.CHANNEL + '.Requested'] = True
    channel_immutable[cs.CHANNEL + '.Interfaces'] = \
        dbus.Array([], signature='s')
    channel_immutable[cs.CHANNEL + '.TargetHandle'] = \
        conn.ensure_handle(cs.HT_CONTACT, 'juliet')
    channel = SimulatedChannel(conn, channel_immutable)

    # this order of events is guaranteed by telepathy-spec (since 0.17.14)
    if ensure:
        q.dbus_return(cm_request_call.message, True, # <- Yours
                channel.object_path, channel.immutable, signature='boa{sv}')
    else:   # Create
        q.dbus_return(cm_request_call.message,
                channel.object_path, channel.immutable, signature='oa{sv}')
    channel.announce()

    if channel_type == cs.CHANNEL_TYPE_TEXT:
        # Observer should get told, processing waits for it
        e = q.expect('dbus-method-call',
                path=client.object_path,
                interface=cs.OBSERVER, method='ObserveChannels',
                handled=False)
        assert e.args[0] == account.object_path, e.args
        assert e.args[1] == conn.object_path, e.args
        assert e.args[3] == '/', e.args         # no dispatch operation
        assert e.args[4] == [request_path], e.args
        channels = e.args[2]
        assert len(channels) == 1, channels
        assert channels[0][0] == channel.object_path, channels
        assert channels[0][1] == channel_immutable, channels

        # Observer says "OK, go"
        q.dbus_return(e.message, signature='')

    # Handler is next
    e = q.expect('dbus-method-call',
            path=prefer.object_path,
            interface=cs.HANDLER, method='HandleChannels',
            handled=False)
    assert e.args[0] == account.object_path, e.args
    assert e.args[1] == conn.object_path, e.args
    channels = e.args[2]
    assert len(channels) == 1, channels
    assert channels[0][0] == channel.object_path, channels
    assert channels[0][1] == channel_immutable, channels
    assert e.args[3] == [request_path], e.args
    assert e.args[4] == user_action_time
    assert isinstance(e.args[5], dict)
    assertContains('request-properties', e.args[5])
    assertContains(request_path, e.args[5]['request-properties'])
    assertLength(1, e.args[5]['request-properties'])
    assertEquals(request_props, e.args[5]['request-properties'][request_path])
    assert len(e.args) == 6

    # Handler accepts the Channels
    q.dbus_return(e.message, signature='')

    e = q.expect('dbus-signal', path=request_path, interface=cs.CR,
        signal='Succeeded')

    assertEquals(conn.object_path, e.args[0])
    assert isinstance(e.args[1], dict), e.args[1]
    assertEquals(channel.object_path, e.args[2])
    assertEquals(channel_immutable, e.args[3])

    # Close the channel
    channel.close()

if __name__ == '__main__':
    exec_test(test, {})
