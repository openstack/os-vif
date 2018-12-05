# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import glob
import mock
import os.path
import testtools

from oslo_concurrency import processutils

from vif_plug_ovs import constants
from vif_plug_ovs import exception
from vif_plug_ovs import linux_net
from vif_plug_ovs import privsep


class LinuxNetTest(testtools.TestCase):

    def setUp(self):
        super(LinuxNetTest, self).setUp()

        privsep.vif_plug.set_client_mode(False)

    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=True)
    def test_ensure_bridge_exists(self, mock_dev_exists, mock_execute):
        linux_net.ensure_bridge("br0")

        mock_execute.assert_has_calls([
            mock.call('ip', 'link', 'set', 'br0', 'up',
                      check_exit_code=[0, 2, 254])])
        mock_dev_exists.assert_has_calls([mock.call("br0")])

    @mock.patch.object(os.path, "exists", return_value=False)
    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=False)
    def test_ensure_bridge_new_ipv4(self, mock_dev_exists, mock_execute,
                                    mock_path_exists):
        linux_net.ensure_bridge("br0")

        calls = [
            mock.call('brctl', 'addbr', 'br0'),
            mock.call('brctl', 'setfd', 'br0', 0),
            mock.call('brctl', 'stp', 'br0', "off"),
            mock.call('brctl', 'setageing', 'br0', 0),
            mock.call('tee', '/sys/class/net/br0/bridge/multicast_snooping',
                      check_exit_code=[0, 1], process_input='0'),
            mock.call('ip', 'link', 'set', 'br0', 'up',
                      check_exit_code=[0, 2, 254])
        ]
        mock_execute.assert_has_calls(calls)
        mock_dev_exists.assert_has_calls([mock.call("br0")])

    @mock.patch.object(os.path, "exists", return_value=True)
    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=False)
    def test_ensure_bridge_new_ipv6(self, mock_dev_exists, mock_execute,
                                    mock_path_exists):
        linux_net.ensure_bridge("br0")

        calls = [
            mock.call('brctl', 'addbr', 'br0'),
            mock.call('brctl', 'setfd', 'br0', 0),
            mock.call('brctl', 'stp', 'br0', "off"),
            mock.call('brctl', 'setageing', 'br0', 0),
            mock.call('tee', '/sys/class/net/br0/bridge/multicast_snooping',
                      check_exit_code=[0, 1], process_input='0'),
            mock.call('tee', '/proc/sys/net/ipv6/conf/br0/disable_ipv6',
                      check_exit_code=[0, 1], process_input='1'),
            mock.call('ip', 'link', 'set', 'br0', 'up',
                      check_exit_code=[0, 2, 254])
        ]
        mock_execute.assert_has_calls(calls)
        mock_dev_exists.assert_has_calls([mock.call("br0")])

    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=False)
    @mock.patch.object(linux_net, "interface_in_bridge", return_value=False)
    def test_delete_bridge_none(self, mock_interface_br, mock_dev_exists,
                                mock_execute,):
        linux_net.delete_bridge("br0", "vnet1")

        mock_execute.assert_not_called()
        mock_dev_exists.assert_has_calls([mock.call("br0")])
        mock_interface_br.assert_not_called()

    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=True)
    @mock.patch.object(linux_net, "interface_in_bridge", return_value=True)
    def test_delete_bridge_exists(self, mock_interface_br, mock_dev_exists,
                                  mock_execute):
        linux_net.delete_bridge("br0", "vnet1")

        calls = [
            mock.call('brctl', 'delif', 'br0', 'vnet1'),
            mock.call('ip', 'link', 'set', 'br0', 'down'),
            mock.call('brctl', 'delbr', 'br0')]
        mock_execute.assert_has_calls(calls)
        mock_dev_exists.assert_has_calls([mock.call("br0")])
        mock_interface_br.assert_called_once_with("br0", "vnet1")

    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=True)
    @mock.patch.object(linux_net, "interface_in_bridge", return_value=False)
    def test_delete_interface_not_present(self, mock_interface_br,
                                          mock_dev_exists, mock_execute):
        linux_net.delete_bridge("br0", "vnet1")

        calls = [
            mock.call('ip', 'link', 'set', 'br0', 'down'),
            mock.call('brctl', 'delbr', 'br0')]
        mock_execute.assert_has_calls(calls)
        mock_dev_exists.assert_has_calls([mock.call("br0")])
        mock_interface_br.assert_called_once_with("br0", "vnet1")

    @mock.patch.object(processutils, "execute")
    def test_add_bridge_port(self, mock_execute):
        linux_net.add_bridge_port("br0", "vnet1")

        mock_execute.assert_has_calls([
            mock.call('brctl', 'addif', 'br0', 'vnet1')])

    def test_ovs_vif_port_cmd(self):
        expected = ['--', '--may-exist', 'add-port',
                    'fake-bridge', 'fake-dev',
                    '--', 'set', 'Interface', 'fake-dev',
                    'external-ids:iface-id=fake-iface-id',
                    'external-ids:iface-status=active',
                    'external-ids:attached-mac=fake-mac',
                    'external-ids:vm-uuid=fake-instance-uuid']
        cmd = linux_net._create_ovs_vif_cmd('fake-bridge', 'fake-dev',
                                            'fake-iface-id', 'fake-mac',
                                            'fake-instance-uuid')

        self.assertEqual(expected, cmd)

        expected += ['type=fake-type']
        cmd = linux_net._create_ovs_vif_cmd('fake-bridge', 'fake-dev',
                                            'fake-iface-id', 'fake-mac',
                                            'fake-instance-uuid',
                                            'fake-type')
        self.assertEqual(expected, cmd)

        expected += ['options:vhost-server-path=/fake/path']
        cmd = linux_net._create_ovs_vif_cmd('fake-bridge', 'fake-dev',
                                            'fake-iface-id', 'fake-mac',
                                            'fake-instance-uuid',
                                            'fake-type',
                                            vhost_server_path='/fake/path')
        self.assertEqual(expected, cmd)

    @mock.patch.object(linux_net, '_create_ovs_bridge_cmd')
    @mock.patch.object(linux_net, '_ovs_vsctl')
    def test_ensure_ovs_bridge(self, mock_vsctl, mock_create_ovs_bridge):
        bridge = 'fake-bridge'
        dp_type = 'fake-type'
        linux_net.ensure_ovs_bridge(bridge, dp_type)
        mock_create_ovs_bridge.assert_called_once_with(bridge, dp_type)
        self.assertTrue(mock_vsctl.called)

    def test_create_ovs_bridge_cmd(self):
        bridge = 'fake-bridge'
        dp_type = 'fake-type'
        expected = ['--', '--may-exist', 'add-br', bridge,
                    '--', 'set', 'Bridge', bridge,
                    'datapath_type=%s' % dp_type]
        actual = linux_net._create_ovs_bridge_cmd(bridge, dp_type)
        self.assertEqual(expected, actual)

    @mock.patch.object(linux_net, '_ovs_supports_mtu_requests')
    @mock.patch.object(linux_net, '_ovs_vsctl')
    @mock.patch.object(linux_net, '_create_ovs_vif_cmd')
    @mock.patch.object(linux_net, '_set_device_mtu')
    def test_ovs_vif_port_with_type_vhostuser(self, mock_set_device_mtu,
                                              mock_create_cmd, mock_vsctl,
                                              mock_ovs_supports_mtu_requests):
        mock_ovs_supports_mtu_requests.return_value = True
        linux_net.create_ovs_vif_port(
            'fake-bridge',
            'fake-dev', 'fake-iface-id', 'fake-mac',
            "fake-instance-uuid", mtu=1500,
            interface_type=constants.OVS_VHOSTUSER_INTERFACE_TYPE)
        mock_create_cmd.assert_called_once_with('fake-bridge',
            'fake-dev', 'fake-iface-id', 'fake-mac',
            "fake-instance-uuid", constants.OVS_VHOSTUSER_INTERFACE_TYPE,
             None)
        self.assertFalse(mock_set_device_mtu.called)
        self.assertTrue(mock_vsctl.called)

    @mock.patch.object(linux_net, '_ovs_supports_mtu_requests')
    @mock.patch.object(linux_net, '_ovs_vsctl')
    @mock.patch.object(linux_net, '_create_ovs_vif_cmd')
    @mock.patch.object(linux_net, '_set_device_mtu')
    def test_ovs_vif_port_with_type_vhostuserclient(self,
        mock_set_device_mtu, mock_create_cmd,
        mock_vsctl, mock_ovs_supports_mtu_requests):
        mock_ovs_supports_mtu_requests.return_value = True
        linux_net.create_ovs_vif_port(
            'fake-bridge',
            'fake-dev', 'fake-iface-id', 'fake-mac',
            "fake-instance-uuid", mtu=1500,
            interface_type=constants.OVS_VHOSTUSER_CLIENT_INTERFACE_TYPE,
            vhost_server_path="/fake/path")
        mock_create_cmd.assert_called_once_with('fake-bridge',
            'fake-dev', 'fake-iface-id', 'fake-mac',
            "fake-instance-uuid",
            constants.OVS_VHOSTUSER_CLIENT_INTERFACE_TYPE,
            "/fake/path")
        self.assertFalse(mock_set_device_mtu.called)
        self.assertTrue(mock_vsctl.called)

    @mock.patch.object(linux_net, '_ovs_supports_mtu_requests')
    @mock.patch.object(linux_net, '_ovs_vsctl')
    @mock.patch.object(linux_net, '_create_ovs_vif_cmd')
    @mock.patch.object(linux_net, '_set_device_mtu')
    def test_ovs_vif_port_with_no_mtu(self, mock_set_device_mtu,
                                      mock_create_cmd, mock_vsctl,
                                      mock_ovs_supports_mtu_requests):
        mock_ovs_supports_mtu_requests.return_value = True
        linux_net.create_ovs_vif_port(
            'fake-bridge',
            'fake-dev', 'fake-iface-id', 'fake-mac',
            "fake-instance-uuid")
        mock_create_cmd.assert_called_once_with('fake-bridge',
            'fake-dev', 'fake-iface-id', 'fake-mac',
            "fake-instance-uuid", None, None)
        self.assertFalse(mock_set_device_mtu.called)
        self.assertTrue(mock_vsctl.called)

    @mock.patch.object(linux_net, '_ovs_supports_mtu_requests')
    @mock.patch.object(linux_net, '_set_mtu_request')
    @mock.patch.object(linux_net, '_ovs_vsctl')
    @mock.patch.object(linux_net, '_create_ovs_vif_cmd',
                       return_value='ovs_command')
    @mock.patch.object(linux_net, '_set_device_mtu')
    def test_ovs_vif_port_with_timeout(self, mock_set_device_mtu,
                                       mock_create_cmd, mock_vsctl,
                                       mock_set_mtu_request,
                                       mock_ovs_supports_mtu_requests):
        mock_ovs_supports_mtu_requests.return_value = True

        linux_net.create_ovs_vif_port(
            'fake-bridge',
            'fake-dev', 'fake-iface-id', 'fake-mac',
            "fake-instance-uuid", timeout=42)
        self.assertTrue(mock_create_cmd.called)
        self.assertFalse(mock_set_device_mtu.called)
        mock_vsctl.assert_called_with('ovs_command', timeout=42)

    @mock.patch.object(linux_net, '_ovs_supports_mtu_requests')
    @mock.patch.object(linux_net, '_set_mtu_request')
    @mock.patch.object(linux_net, '_ovs_vsctl')
    @mock.patch.object(linux_net, '_create_ovs_vif_cmd',
                       return_value='ovs_command')
    @mock.patch.object(linux_net, '_set_device_mtu')
    def test_ovs_vif_port_with_no_timeout(self, mock_set_device_mtu,
                                          mock_create_cmd, mock_vsctl,
                                          mock_set_mtu_request,
                                          mock_ovs_supports_mtu_requests):
        mock_ovs_supports_mtu_requests.return_value = True
        linux_net.create_ovs_vif_port(
            'fake-bridge',
            'fake-dev', 'fake-iface-id', 'fake-mac',
            "fake-instance-uuid")
        self.assertTrue(mock_create_cmd.called)
        self.assertFalse(mock_set_device_mtu.called)
        mock_vsctl.assert_called_with('ovs_command', timeout=None)

    @mock.patch.object(processutils, "execute")
    def test_ovs_vsctl(self, mock_execute):
        args = ['fake-args', 42]
        timeout = 42
        linux_net._ovs_vsctl(args)
        linux_net._ovs_vsctl(args, timeout=timeout)
        mock_execute.assert_has_calls([
            mock.call('ovs-vsctl', *args),
            mock.call('ovs-vsctl', '--timeout=%s' % timeout, *args)])

    @mock.patch.object(linux_net, '_ovs_vsctl')
    def test_set_mtu_request(self, mock_vsctl):
        dev = 'fake-dev'
        mtu = 'fake-mtu'
        timeout = 120
        linux_net._set_mtu_request(dev, mtu, timeout=timeout)
        args = ['--', 'set', 'interface', dev,
                'mtu_request=%s' % mtu]
        mock_vsctl.assert_called_with(args, timeout=timeout)

    @mock.patch.object(linux_net, '_delete_net_dev')
    @mock.patch.object(linux_net, '_ovs_vsctl')
    def test_delete_ovs_vif_port_delete_netdev(
            self, mock_vsctl, mock_delete_net_dev):
        bridge = 'fake-bridge'
        dev = 'fake-dev'
        timeout = 120
        linux_net.delete_ovs_vif_port(bridge, dev, timeout=timeout)
        args = ['--', '--if-exists', 'del-port', bridge, dev]
        mock_vsctl.assert_called_with(args, timeout=timeout)
        mock_delete_net_dev.assert_called()

    @mock.patch.object(linux_net, '_delete_net_dev')
    @mock.patch.object(linux_net, '_ovs_vsctl')
    def test_delete_ovs_vif_port(self, mock_vsctl, mock_delete_net_dev):
        bridge = 'fake-bridge'
        dev = 'fake-dev'
        timeout = 120
        linux_net.delete_ovs_vif_port(
            bridge, dev, timeout=timeout, delete_netdev=False)
        args = ['--', '--if-exists', 'del-port', bridge, dev]
        mock_vsctl.assert_called_with(args, timeout=timeout)
        mock_delete_net_dev.assert_not_called()

    @mock.patch.object(linux_net, '_ovs_vsctl')
    def test_ovs_supports_mtu_requests(self, mock_vsctl):
        args = ['--columns=mtu_request', 'list', 'interface']
        timeout = 120
        msg = 'ovs-vsctl: Interface does not contain' + \
              ' a column whose name matches "mtu_request"'

        mock_vsctl.return_value = (None, msg)
        result = linux_net._ovs_supports_mtu_requests(timeout=timeout)
        mock_vsctl.assert_called_with(args, timeout=timeout)
        self.assertFalse(result)

        mock_vsctl.return_value = (None, None)
        result = linux_net._ovs_supports_mtu_requests(timeout=timeout)
        mock_vsctl.assert_called_with(args, timeout=timeout)
        self.assertTrue(result)

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    def test_is_switchdev_ioerror(self, mock_isfile, mock_open):
        mock_isfile.side_effect = [True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
            [IOError()])
        test_switchdev = linux_net._is_switchdev('pf_ifname')
        self.assertEqual(test_switchdev, False)

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    def test_is_switchdev_empty(self, mock_isfile, mock_open):
        mock_isfile.side_effect = [True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
            [''])
        open_calls = (
            [mock.call('/sys/class/net/pf_ifname/phys_switch_id', 'r'),
             mock.call().readline(),
             mock.call().__exit__(None, None, None)])
        test_switchdev = linux_net._is_switchdev('pf_ifname')
        mock_open.assert_has_calls(open_calls)
        self.assertEqual(test_switchdev, False)

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    def test_is_switchdev_positive(self, mock_isfile, mock_open):
        mock_isfile.side_effect = [True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
            ['pf_sw_id'])
        open_calls = (
            [mock.call('/sys/class/net/pf_ifname/phys_switch_id', 'r'),
             mock.call().readline(),
             mock.call().__exit__(None, None, None)])
        test_switchdev = linux_net._is_switchdev('pf_ifname')
        mock_open.assert_has_calls(open_calls)
        self.assertEqual(test_switchdev, True)

    def test_parse_vf_number(self):
        self.assertEqual(linux_net._parse_vf_number("0"), "0")
        self.assertEqual(linux_net._parse_vf_number("pf13vf42"), "42")
        self.assertEqual(linux_net._parse_vf_number("VF19@PF13"), "19")
        self.assertEqual(linux_net._parse_vf_number("p7"), None)
        self.assertEqual(linux_net._parse_vf_number("pf31"), None)
        self.assertEqual(linux_net._parse_vf_number("g4rbl3d"), None)

    def test_parse_pf_number(self):
        self.assertEqual(linux_net._parse_pf_number("0"), None)
        self.assertEqual(linux_net._parse_pf_number("pf13vf42"), "13")
        self.assertEqual(linux_net._parse_pf_number("VF19@PF13"), "13")
        self.assertEqual(linux_net._parse_pf_number("p7"), None)
        self.assertEqual(linux_net._parse_pf_number("pf31"), "31")
        self.assertEqual(linux_net._parse_pf_number("g4rbl3d"), None)

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    @mock.patch.object(os, 'listdir')
    def test_get_representor_port(self, mock_listdir, mock_isfile, mock_open):
        mock_listdir.return_value = [
            'pf_ifname', 'rep_vf_1', 'rep_vf_2'
        ]
        mock_isfile.side_effect = [True, True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
            ['pf_sw_id', 'pf_sw_id', '1', 'pf_sw_id', 'pf0vf2'])
        open_calls = (
            [mock.call('/sys/class/net/pf_ifname/phys_switch_id', 'r'),
             mock.call().readline(),
             mock.call().__exit__(None, None, None),
             mock.call('/sys/class/net/rep_vf_1/phys_switch_id', 'r'),
             mock.call().readline(),
             mock.call().__exit__(None, None, None),
             mock.call('/sys/class/net/rep_vf_1/phys_port_name', 'r'),
             mock.call().readline(),
             mock.call().__exit__(None, None, None),
             mock.call('/sys/class/net/rep_vf_2/phys_switch_id', 'r'),
             mock.call().readline(),
             mock.call().__exit__(None, None, None),
             mock.call('/sys/class/net/rep_vf_2/phys_port_name', 'r'),
             mock.call().readline(),
             mock.call().__exit__(None, None, None)])
        ifname = linux_net.get_representor_port('pf_ifname', '2')
        mock_open.assert_has_calls(open_calls)
        self.assertEqual('rep_vf_2', ifname)

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    @mock.patch.object(os, 'listdir')
    def test_get_representor_port_2_pfs(
            self, mock_listdir, mock_isfile, mock_open):
        mock_listdir.return_value = [
            'pf_ifname1', 'pf_ifname2', 'rep_pf1_vf_1', 'rep_pf1_vf_2',
            'rep_pf2_vf_1', 'rep_pf2_vf_2',
        ]
        mock_isfile.side_effect = [True, True, True, True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
            ['pf1_sw_id', 'pf1_sw_id', 'pf2_sw_id', '1', 'pf1_sw_id', '2'])
        ifname = linux_net.get_representor_port('pf_ifname1', '2')
        self.assertEqual('rep_pf1_vf_2', ifname)

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    @mock.patch.object(os, 'listdir')
    def test_get_representor_port_not_found(
            self, mock_listdir, mock_isfile, mock_open):
        mock_listdir.return_value = [
            'pf_ifname', 'rep_vf_1', 'rep_vf_2'
        ]
        mock_isfile.side_effect = [True, True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
            ['pf_sw_id', 'pf_sw_id', '1', 'pf_sw_id', '2'])
        self.assertRaises(
            exception.RepresentorNotFound,
            linux_net.get_representor_port,
            'pf_ifname', '3'),

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    @mock.patch.object(os, 'listdir')
    def test_get_representor_port_exception_io_error(
            self, mock_listdir, mock_isfile, mock_open):
        mock_listdir.return_value = [
            'pf_ifname', 'rep_vf_1', 'rep_vf_2'
        ]
        mock_isfile.side_effect = [True, True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
            ['pf_sw_id', 'pf_sw_id', IOError(), 'pf_sw_id', '2'])
        self.assertRaises(
            exception.RepresentorNotFound,
            linux_net.get_representor_port,
            'pf_ifname', '3')

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    @mock.patch.object(os, 'listdir')
    def test_get_representor_port_exception_value_error(
            self, mock_listdir, mock_isfile, mock_open):
        mock_listdir.return_value = [
            'pf_ifname', 'rep_vf_1', 'rep_vf_2'
        ]
        mock_isfile.side_effect = [True, True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
            ['pf_sw_id', 'pf_sw_id', '1', 'pf_sw_id', 'a'])
        self.assertRaises(
            exception.RepresentorNotFound,
            linux_net.get_representor_port,
            'pf_ifname', '3')

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    @mock.patch.object(os, 'listdir')
    def test_physical_function_inferface_name(
            self, mock_listdir, mock_isfile, mock_open):
        mock_listdir.return_value = ['foo', 'bar']
        mock_isfile.side_effect = [True, True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
            ['', 'valid_switch'])
        ifname = linux_net.get_ifname_by_pci_address(
            '0000:00:00.1', pf_interface=True, switchdev=False)
        self.assertEqual(ifname, 'foo')

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    @mock.patch.object(os, 'listdir')
    def test_physical_function_inferface_name_with_switchdev(
            self, mock_listdir, mock_isfile, mock_open):
        mock_listdir.return_value = ['foo', 'bar']
        mock_isfile.side_effect = [True, True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
            ['', 'valid_switch'])
        ifname = linux_net.get_ifname_by_pci_address(
            '0000:00:00.1', pf_interface=True, switchdev=True)
        self.assertEqual(ifname, 'bar')

    @mock.patch.object(os, 'listdir')
    def test_get_ifname_by_pci_address_exception(self, mock_listdir):
        mock_listdir.side_effect = OSError('No such file or directory')
        self.assertRaises(
            exception.PciDeviceNotFoundById,
            linux_net.get_ifname_by_pci_address,
            '0000:00:00.1'
        )

    @mock.patch.object(os, 'readlink')
    @mock.patch.object(glob, 'iglob')
    def test_vf_number_found(self, mock_iglob, mock_readlink):
        mock_iglob.return_value = [
            '/sys/bus/pci/devices/0000:00:00.1/physfn/virtfn3',
        ]
        mock_readlink.return_value = '../../0000:00:00.1'
        vf_num = linux_net.get_vf_num_by_pci_address('0000:00:00.1')
        self.assertEqual(vf_num, '3')

    @mock.patch.object(os, 'readlink')
    @mock.patch.object(glob, 'iglob')
    def test_vf_number_not_found(self, mock_iglob, mock_readlink):
        mock_iglob.return_value = [
            '/sys/bus/pci/devices/0000:00:00.1/physfn/virtfn3',
        ]
        mock_readlink.return_value = '../../0000:00:00.2'
        self.assertRaises(
            exception.PciDeviceNotFoundById,
            linux_net.get_vf_num_by_pci_address,
            '0000:00:00.1'
        )

    @mock.patch.object(os, 'readlink')
    @mock.patch.object(glob, 'iglob')
    def test_get_vf_num_by_pci_address_exception(
            self, mock_iglob, mock_readlink):
        mock_iglob.return_value = [
            '/sys/bus/pci/devices/0000:00:00.1/physfn/virtfn3',
        ]
        mock_readlink.side_effect = OSError('No such file or directory')
        self.assertRaises(
            exception.PciDeviceNotFoundById,
            linux_net.get_vf_num_by_pci_address,
            '0000:00:00.1'
        )
