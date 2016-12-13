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

import mock
import os.path
import testtools

from oslo_concurrency import processutils

from vif_plug_ovs import constants
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

        self.assertEqual(mock_execute.mock_calls, [])
        self.assertEqual(mock_dev_exists.mock_calls, [
            mock.call("br0")
        ])

    @mock.patch.object(os.path, "exists", return_value=False)
    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=False)
    def test_ensure_bridge_new_ipv4(self, mock_dev_exists, mock_execute,
                                    mock_path_exists):
        linux_net.ensure_bridge("br0")

        self.assertEqual(mock_execute.mock_calls, [
            mock.call('brctl', 'addbr', 'br0'),
            mock.call('brctl', 'setfd', 'br0', 0),
            mock.call('brctl', 'stp', 'br0', "off"),
            mock.call('tee', '/sys/class/net/br0/bridge/multicast_snooping',
                      check_exit_code=[0, 1], process_input='0'),
        ])
        self.assertEqual(mock_dev_exists.mock_calls, [
            mock.call("br0")
        ])

    @mock.patch.object(os.path, "exists", return_value=True)
    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=False)
    def test_ensure_bridge_new_ipv6(self, mock_dev_exists, mock_execute,
                                    mock_path_exists):
        linux_net.ensure_bridge("br0")

        self.assertEqual(mock_execute.mock_calls, [
            mock.call('brctl', 'addbr', 'br0'),
            mock.call('brctl', 'setfd', 'br0', 0),
            mock.call('brctl', 'stp', 'br0', "off"),
            mock.call('tee', '/sys/class/net/br0/bridge/multicast_snooping',
                      check_exit_code=[0, 1], process_input='0'),
            mock.call('tee', '/proc/sys/net/ipv6/conf/br0/disable_ipv6',
                      check_exit_code=[0, 1], process_input='1'),
        ])
        self.assertEqual(mock_dev_exists.mock_calls, [
            mock.call("br0")
        ])

    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=False)
    def test_delete_bridge_none(self, mock_dev_exists, mock_execute):
        linux_net.delete_bridge("br0", "vnet1")

        self.assertEqual(mock_execute.mock_calls, [])
        self.assertEqual(mock_dev_exists.mock_calls, [
            mock.call("br0")
        ])

    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=True)
    def test_delete_bridge_exists(self, mock_dev_exists, mock_execute):
        linux_net.delete_bridge("br0", "vnet1")

        self.assertEqual(mock_execute.mock_calls, [
            mock.call('brctl', 'delif', 'br0', 'vnet1'),
            mock.call('ip', 'link', 'set', 'br0', 'down'),
            mock.call('brctl', 'delbr', 'br0'),
        ])
        self.assertEqual(mock_dev_exists.mock_calls, [
            mock.call("br0")
        ])

    @mock.patch.object(processutils, "execute")
    def test_add_bridge_port(self, mock_execute):
        linux_net.add_bridge_port("br0", "vnet1")

        self.assertEqual(mock_execute.mock_calls, [
            mock.call('ip', 'link', 'set', 'br0', 'up'),
            mock.call('brctl', 'addif', 'br0', 'vnet1'),
        ])

    def test_ovs_vif_port_cmd(self):
        expected = ['--', '--if-exists',
                    'del-port', 'fake-dev', '--', 'add-port',
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
        self.assertEqual(
            [mock.call('ovs-vsctl', *args),
             mock.call('ovs-vsctl', '--timeout=%s' % timeout, *args)],
            mock_execute.mock_calls)

    @mock.patch.object(linux_net, '_ovs_vsctl')
    def test_set_mtu_request(self, mock_vsctl):
        dev = 'fake-dev'
        mtu = 'fake-mtu'
        timeout = 120
        linux_net._set_mtu_request(dev, mtu, timeout=timeout)
        args = ['--', 'set', 'interface', dev,
                'mtu_request=%s' % mtu]
        mock_vsctl.assert_called_with(args, timeout=timeout)

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
