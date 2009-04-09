"""Regression test for the unofficial Account.Interface.Requests API, when
an account is deleted while requesting a channel from that account.
"""

import dbus
import dbus.service

from servicetest import EventPattern, tp_name_prefix, tp_path_prefix, \
        call_async
from mctest import exec_test, SimulatedConnection, SimulatedClient, \
        create_fakecm_account, enable_fakecm_account, SimulatedChannel
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

    # wait for MC to download the properties
    q.expect_many(
            EventPattern('dbus-method-call',
                interface=cs.PROPERTIES_IFACE, method='Get',
                args=[cs.CLIENT, 'Interfaces'],
                path=client.object_path),
            EventPattern('dbus-method-call',
                interface=cs.PROPERTIES_IFACE, method='Get',
                args=[cs.APPROVER, 'ApproverChannelFilter'],
                path=client.object_path),
            EventPattern('dbus-method-call',
                interface=cs.PROPERTIES_IFACE, method='Get',
                args=[cs.HANDLER, 'HandlerChannelFilter'],
                path=client.object_path),
            EventPattern('dbus-method-call',
                interface=cs.PROPERTIES_IFACE, method='Get',
                args=[cs.OBSERVER, 'ObserverChannelFilter'],
                path=client.object_path),
            )

    user_action_time = dbus.Int64(1238582606)

    # chat UI calls ChannelDispatcher.CreateChannel
    # (or in this case, an equivalent non-standard method on the Account)
    request = dbus.Dictionary({
            cs.CHANNEL + '.ChannelType': cs.CHANNEL_TYPE_TEXT,
            cs.CHANNEL + '.TargetHandleType': cs.HT_CONTACT,
            cs.CHANNEL + '.TargetID': 'juliet',
            }, signature='sv')
    account_requests = dbus.Interface(account,
            cs.ACCOUNT_IFACE_NOKIA_REQUESTS)
    call_async(q, account_requests, 'Create',
            request, user_action_time, client.bus_name)

    # chat UI connects to signals and calls ChannelRequest.Proceed() - but not
    # in this non-standard API, which fires off the request instantly
    ret, cm_request_call = q.expect_many(
            EventPattern('dbus-return',
                method='Create'),
            EventPattern('dbus-method-call',
                interface=cs.CONN_IFACE_REQUESTS,
                method='CreateChannel',
                path=conn.object_path, args=[request], handled=False),
            )

    request_path = ret.value[0]

    e = q.expect('dbus-method-call', handled=False,
        interface=cs.HANDLER, method='AddRequest', path=client.object_path)
    assert e.args[0] == request_path

    q.dbus_return(e.message, signature='')

    # Before the channel is returned, we delete the account

    account_iface = dbus.Interface(account, cs.ACCOUNT)
    assert account_iface.Remove() is None
    account_event, account_manager_event = q.expect_many(
        EventPattern('dbus-signal',
            path=account.object_path,
            signal='Removed',
            interface=cs.ACCOUNT,
            args=[]
            ),
        EventPattern('dbus-signal',
            path=cs.AM_PATH,
            signal='AccountRemoved',
            interface=cs.AM,
            args=[account.object_path]
            ),
        )

    # You know that request I told you about? Not going to happen.
    remove_failed_request = q.expect('dbus-method-call',
            interface=cs.HANDLER,
            method='RemoveFailedRequest',
            handled=False)
    assert remove_failed_request.args[0] == request_path
    # FIXME: the spec should maybe define what error this will be. Currently,
    # it's Disconnected
    assert remove_failed_request.args[1].startswith(tp_name_prefix + '.Error.')

    q.expect_many(
            EventPattern('dbus-signal',
                path=request_path,
                interface=cs.CR + '.DRAFT',
                signal='Failed',
                args=remove_failed_request.args[1:]),
            EventPattern('dbus-signal',
                path=account.object_path,
                interface=cs.ACCOUNT_IFACE_NOKIA_REQUESTS,
                signal='Failed',
                args=remove_failed_request.args),
            )

    q.dbus_return(remove_failed_request.message, signature='')

    # ... and the Connection is told to disconnect, hopefully before the
    # Channel has actually been established
    e = q.expect('dbus-method-call',
            path=conn.object_path,
            interface=cs.CONN,
            method='Disconnect',
            args=[],
            handled=True)

if __name__ == '__main__':
    exec_test(test, {})