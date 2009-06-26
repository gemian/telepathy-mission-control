"""Feature test for signing in and setting an avatar, on CMs like Gabble where
the avatar is stored by the server.
"""

import os

import dbus
import dbus.service

from servicetest import EventPattern, tp_name_prefix, tp_path_prefix, \
        call_async
from mctest import exec_test, SimulatedConnection, create_fakecm_account
import constants as cs

cm_name_ref = dbus.service.BusName(
        cs.tp_name_prefix + '.ConnectionManager.fakecm', bus=dbus.SessionBus())

account_id = 'fakecm/fakeprotocol/jc_2edenton_40unatco_2eint'

def preseed():

    accounts_dir = os.environ['MC_ACCOUNT_DIR']

    accounts_cfg = open(accounts_dir + '/accounts.cfg', 'w')
    accounts_cfg.write("""# Telepathy accounts
[%s]
manager=fakecm
protocol=fakeprotocol
DisplayName=Work account
NormalizedName=jc.denton@unatco.int
param-account=jc.denton@unatco.int
param-password=ionstorm
Enabled=1
ConnectAutomatically=1
AutomaticPresenceType=2
AutomaticPresenceStatus=available
AutomaticPresenceMessage=My vision is augmented
Nickname=JC
AvatarMime=image/jpeg
avatar_token=Deus Ex
""" % account_id)
    accounts_cfg.close()

    os.makedirs(accounts_dir + '/' + account_id)
    avatar_bin = open(accounts_dir + '/' + account_id + '/avatar.bin', 'w')
    avatar_bin.write('Deus Ex')
    avatar_bin.close()

    account_connections_file = open(accounts_dir + '/.mc_connections', 'w')
    account_connections_file.write("")
    account_connections_file.close()

def test(q, bus, mc):
    expected_params = {
            'account': 'jc.denton@unatco.int',
            'password': 'ionstorm',
            }

    e = q.expect('dbus-method-call', method='RequestConnection',
            args=['fakeprotocol', expected_params],
            destination=cs.tp_name_prefix + '.ConnectionManager.fakecm',
            path=cs.tp_path_prefix + '/ConnectionManager/fakecm',
            interface=cs.tp_name_prefix + '.ConnectionManager',
            handled=False)

    conn = SimulatedConnection(q, bus, 'fakecm', 'fakeprotocol', '_',
            'myself', has_avatars=True, avatars_persist=True)
    conn.avatar = dbus.Struct((dbus.ByteArray('MJ12'), 'image/png'),
            signature='ays')

    q.dbus_return(e.message, conn.bus_name, conn.object_path, signature='so')

    account_path = (cs.tp_path_prefix + '/Account/' + account_id)

    e, _ = q.expect_many(
            EventPattern('dbus-signal', signal='AccountPropertyChanged',
                path=account_path, interface=cs.ACCOUNT,
                predicate=(lambda e: e.args[0].get('ConnectionStatus') ==
                    cs.CONN_STATUS_CONNECTING)),
            EventPattern('dbus-method-call', method='Connect',
                path=conn.object_path, handled=True, interface=cs.CONN),
            )
    assert e.args[0].get('Connection') in (conn.object_path, None)
    assert e.args[0]['ConnectionStatus'] == cs.CONN_STATUS_CONNECTING
    assert e.args[0]['ConnectionStatusReason'] == \
            cs.CONN_STATUS_REASON_REQUESTED

    conn.StatusChanged(cs.CONN_STATUS_CONNECTED, cs.CONN_STATUS_REASON_NONE)

    # We haven't changed the avatar since we last signed in, so we don't set
    # it - on the contrary, we pick up the remote avatar (which has changed
    # since we were last here) to store it in the Account
    _, request_avatars_call, e = q.expect_many(
            EventPattern('dbus-method-call',
                interface=cs.CONN_IFACE_AVATARS, method='GetKnownAvatarTokens',
                args=[[conn.self_handle]],
                handled=True),
            EventPattern('dbus-method-call',
                interface=cs.CONN_IFACE_AVATARS, method='RequestAvatars',
                args=[[conn.self_handle]],
                handled=False),
            EventPattern('dbus-signal', signal='AccountPropertyChanged',
                path=account_path, interface=cs.ACCOUNT,
                predicate=lambda e: 'ConnectionStatus' in e.args[0]),
            )

    assert e.args[0]['ConnectionStatus'] == cs.CONN_STATUS_CONNECTED

    q.dbus_return(request_avatars_call.message, signature='')

    q.dbus_emit(conn.object_path, cs.CONN_IFACE_AVATARS, 'AvatarRetrieved',
            conn.self_handle, str(conn.avatar[0]),
            dbus.ByteArray(conn.avatar[0]), conn.avatar[1], signature='usays')

    q.expect('dbus-signal', path=account_path,
            interface=cs.ACCOUNT_IFACE_AVATAR, signal='AvatarChanged'),

    account = bus.get_object(cs.AM, account_path)
    account_props = dbus.Interface(account, cs.PROPERTIES_IFACE)
    assert account_props.Get(cs.ACCOUNT_IFACE_AVATAR, 'Avatar',
            byte_arrays=True) == conn.avatar

if __name__ == '__main__':
    preseed()
    exec_test(test, {})