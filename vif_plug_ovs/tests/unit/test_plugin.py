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
import testtools

from os_vif import objects
from os_vif.objects import fields

from vif_plug_ovs import constants
from vif_plug_ovs import linux_net
from vif_plug_ovs import ovs


class PluginTest(testtools.TestCase):

    def __init__(self, *args, **kwargs):
        super(PluginTest, self).__init__(*args, **kwargs)

        objects.register_all()

        self.subnet_bridge_4 = objects.subnet.Subnet(
            cidr='101.168.1.0/24',
            dns=['8.8.8.8'],
            gateway='101.168.1.1',
            dhcp_server='191.168.1.1')

        self.subnet_bridge_6 = objects.subnet.Subnet(
            cidr='101:1db9::/64',
            gateway='101:1db9::1')

        self.subnets = objects.subnet.SubnetList(
            objects=[self.subnet_bridge_4,
                     self.subnet_bridge_6])

        self.network_ovs = objects.network.Network(
            id='437c6db5-4e6f-4b43-b64b-ed6a11ee5ba7',
            bridge='br0',
            subnets=self.subnets,
            vlan=99)

        self.network_ovs_mtu = objects.network.Network(
            id='437c6db5-4e6f-4b43-b64b-ed6a11ee5ba7',
            bridge='br0',
            subnets=self.subnets,
            vlan=99,
            mtu=1234)

        self.profile_ovs = objects.vif.VIFPortProfileOpenVSwitch(
            interface_id='e65867e0-9340-4a7f-a256-09af6eb7a3aa')

        self.vif_ovs_hybrid = objects.vif.VIFBridge(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=self.network_ovs,
            dev_name='tap-xxx-yyy-zzz',
            bridge_name="qbrvif-xxx-yyy",
            port_profile=self.profile_ovs)

        self.vif_ovs = objects.vif.VIFOpenVSwitch(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=self.network_ovs,
            dev_name='tap-xxx-yyy-zzz',
            port_profile=self.profile_ovs)

        self.vif_vhostuser = objects.vif.VIFVHostUser(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=self.network_ovs,
            path='/var/run/openvswitch/vhub679325f-ca',
            mode='client',
            port_profile=self.profile_ovs)

        self.vif_vhostuser_client = objects.vif.VIFVHostUser(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=self.network_ovs,
            path='/var/run/openvswitch/vhub679325f-ca',
            mode='server',  # qemu server mode <=> ovs client mode
            port_profile=self.profile_ovs)

        self.vif_ovs_vf_passthrough = objects.vif.VIFHostDevice(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=self.network_ovs,
            dev_type=fields.VIFHostDeviceDevType.ETHERNET,
            dev_address='0002:24:12.3',
            bridge_name='br-int',
            port_profile=self.profile_ovs)

        self.instance = objects.instance_info.InstanceInfo(
            name='demo',
            uuid='f0000000-0000-0000-0000-000000000001')

    @mock.patch.object(linux_net, 'create_ovs_vif_port')
    def test_create_vif_port(self, mock_create_ovs_vif_port):
        plugin = ovs.OvsPlugin.load('ovs')
        plugin._create_vif_port(
            self.vif_ovs, mock.sentinel.vif_name, self.instance,
            interface_type=constants.OVS_VHOSTUSER_INTERFACE_TYPE)
        mock_create_ovs_vif_port.assert_called_once_with(
            self.vif_ovs.network.bridge, mock.sentinel.vif_name,
            self.vif_ovs.port_profile.interface_id,
            self.vif_ovs.address, self.instance.uuid,
            plugin.config.network_device_mtu,
            timeout=plugin.config.ovs_vsctl_timeout,
            interface_type=constants.OVS_VHOSTUSER_INTERFACE_TYPE)

    @mock.patch.object(linux_net, 'create_ovs_vif_port')
    def test_create_vif_port_mtu_in_model(self, mock_create_ovs_vif_port):
        self.vif_ovs.network = self.network_ovs_mtu
        plugin = ovs.OvsPlugin.load('ovs')
        plugin._create_vif_port(
            self.vif_ovs, mock.sentinel.vif_name, self.instance,
            interface_type=constants.OVS_VHOSTUSER_INTERFACE_TYPE)
        mock_create_ovs_vif_port.assert_called_once_with(
            self.vif_ovs.network.bridge, mock.sentinel.vif_name,
            self.vif_ovs.port_profile.interface_id,
            self.vif_ovs.address, self.instance.uuid,
            self.network_ovs_mtu.mtu,
            timeout=plugin.config.ovs_vsctl_timeout,
            interface_type=constants.OVS_VHOSTUSER_INTERFACE_TYPE)

    @mock.patch.object(ovs, 'sys')
    @mock.patch.object(linux_net, 'ensure_ovs_bridge')
    def test_plug_ovs(self, ensure_ovs_bridge, mock_sys):
        mock_sys.platform = 'linux'
        plug_bridge_mock = mock.Mock()
        plugin = ovs.OvsPlugin.load("ovs")
        plugin._plug_bridge = plug_bridge_mock
        plugin.plug(self.vif_ovs, self.instance)
        plug_bridge_mock.assert_not_called()
        ensure_ovs_bridge.assert_called_once_with(
            self.vif_ovs.network.bridge, constants.OVS_DATAPATH_SYSTEM)

    @mock.patch.object(linux_net, 'set_interface_state')
    @mock.patch.object(linux_net, 'ensure_ovs_bridge')
    @mock.patch.object(ovs.OvsPlugin, '_update_vif_port')
    @mock.patch.object(ovs.OvsPlugin, '_create_vif_port')
    @mock.patch.object(linux_net, 'add_bridge_port')
    @mock.patch.object(linux_net, 'update_veth_pair')
    @mock.patch.object(linux_net, 'create_veth_pair')
    @mock.patch.object(linux_net, 'device_exists')
    @mock.patch.object(linux_net, 'ensure_bridge')
    @mock.patch.object(ovs, 'sys')
    def test_plug_ovs_bridge(self, mock_sys, ensure_bridge, device_exists,
                             create_veth_pair, update_veth_pair,
                             add_bridge_port, _create_vif_port,
                             _update_vif_port, ensure_ovs_bridge,
                             set_interface_state):
        calls = {
            'device_exists': [mock.call('qvob679325f-ca')],
            'create_veth_pair': [mock.call('qvbb679325f-ca',
                                           'qvob679325f-ca',
                                           1500)],
            'update_veth_pair': [mock.call('qvbb679325f-ca',
                                           'qvob679325f-ca',
                                           1500)],
            'ensure_bridge': [mock.call('qbrvif-xxx-yyy')],
            'set_interface_state': [mock.call('qbrvif-xxx-yyy',
                                              'up')],
            'add_bridge_port': [mock.call('qbrvif-xxx-yyy',
                                          'qvbb679325f-ca')],
            '_update_vif_port': [mock.call(self.vif_ovs_hybrid,
                                           'qvob679325f-ca')],
            '_create_vif_port': [mock.call(self.vif_ovs_hybrid,
                                           'qvob679325f-ca',
                                           self.instance)],
            'ensure_ovs_bridge': [mock.call('br0',
                                            constants.OVS_DATAPATH_SYSTEM)]
        }

        # plugging new devices should result in devices being created

        device_exists.return_value = False
        mock_sys.platform = 'linux'
        plugin = ovs.OvsPlugin.load('ovs')
        plugin.plug(self.vif_ovs_hybrid, self.instance)
        ensure_bridge.assert_has_calls(calls['ensure_bridge'])
        device_exists.assert_has_calls(calls['device_exists'])
        create_veth_pair.assert_has_calls(calls['create_veth_pair'])
        update_veth_pair.assert_not_called()
        _update_vif_port.assert_not_called()
        add_bridge_port.assert_has_calls(calls['add_bridge_port'])
        _create_vif_port.assert_has_calls(calls['_create_vif_port'])
        ensure_ovs_bridge.assert_has_calls(calls['ensure_ovs_bridge'])

        # reset call stacks

        create_veth_pair.reset_mock()
        _create_vif_port.reset_mock()

        # plugging existing devices should result in devices being updated

        device_exists.return_value = True
        self.assertTrue(linux_net.device_exists('test'))
        plugin.plug(self.vif_ovs_hybrid, self.instance)
        create_veth_pair.assert_not_called()
        _create_vif_port.assert_not_called()
        update_veth_pair.assert_has_calls(calls['update_veth_pair'])
        _update_vif_port.assert_has_calls(calls['_update_vif_port'])

    @mock.patch.object(linux_net, 'ensure_ovs_bridge')
    @mock.patch.object(ovs.OvsPlugin, '_create_vif_port')
    @mock.patch.object(linux_net, 'device_exists', return_value=False)
    @mock.patch.object(ovs, 'sys')
    def _check_plug_ovs_windows(self, vif, mock_sys, device_exists,
                                _create_vif_port, ensure_ovs_bridge):
        calls = {
            'device_exists': [mock.call(vif.id)],
            '_create_vif_port': [mock.call(vif, vif.id, self.instance)],
            'ensure_ovs_bridge': [mock.call('br0',
                                            constants.OVS_DATAPATH_SYSTEM)]
        }

        mock_sys.platform = constants.PLATFORM_WIN32
        plugin = ovs.OvsPlugin.load("ovs")
        plugin.plug(vif, self.instance)
        device_exists.assert_has_calls(calls['device_exists'])
        _create_vif_port.assert_has_calls(calls['_create_vif_port'])
        ensure_ovs_bridge.assert_has_calls(calls['ensure_ovs_bridge'])

    def test_plug_ovs_windows(self):
        self._check_plug_ovs_windows(self.vif_ovs)

    def test_plug_ovs_bridge_windows(self):
        self._check_plug_ovs_windows(self.vif_ovs_hybrid)

    def test_unplug_ovs(self):
        unplug_bridge_mock = mock.Mock()
        plugin = ovs.OvsPlugin.load("ovs")
        plugin._unplug_bridge = unplug_bridge_mock
        plugin.unplug(self.vif_ovs, self.instance)
        unplug_bridge_mock.assert_not_called()

    @mock.patch.object(linux_net, 'delete_ovs_vif_port')
    @mock.patch.object(linux_net, 'delete_bridge')
    @mock.patch.object(ovs, 'sys')
    def test_unplug_ovs_bridge(self, mock_sys, delete_bridge,
                               delete_ovs_vif_port):
        calls = {
            'delete_bridge': [mock.call('qbrvif-xxx-yyy', 'qvbb679325f-ca')],
            'delete_ovs_vif_port': [mock.call('br0', 'qvob679325f-ca',
                                    timeout=120)]
        }
        mock_sys.platform = 'linux'
        plugin = ovs.OvsPlugin.load("ovs")
        plugin.unplug(self.vif_ovs_hybrid, self.instance)
        delete_bridge.assert_has_calls(calls['delete_bridge'])
        delete_ovs_vif_port.assert_has_calls(calls['delete_ovs_vif_port'])

    @mock.patch.object(linux_net, 'delete_ovs_vif_port')
    @mock.patch.object(ovs, 'sys')
    def _check_unplug_ovs_windows(self, vif, mock_sys, delete_ovs_vif_port):
        mock_sys.platform = constants.PLATFORM_WIN32
        plugin = ovs.OvsPlugin.load("ovs")
        plugin.unplug(vif, self.instance)
        delete_ovs_vif_port.assert_called_once_with('br0', vif.id, timeout=120)

    def test_unplug_ovs_windows(self):
        self._check_unplug_ovs_windows(self.vif_ovs)

    def test_unplug_ovs_bridge_windows(self):
        self._check_unplug_ovs_windows(self.vif_ovs_hybrid)

    @mock.patch.object(linux_net, 'ensure_ovs_bridge')
    @mock.patch.object(ovs.OvsPlugin, '_create_vif_port')
    def test_plug_ovs_vhostuser(self, _create_vif_port, ensure_ovs_bridge):
        calls = {

            '_create_vif_port': [mock.call(
                                 self.vif_vhostuser, 'vhub679325f-ca',
                                 self.instance,
                                 interface_type='dpdkvhostuser')],
            'ensure_ovs_bridge': [mock.call('br0',
                                            constants.OVS_DATAPATH_NETDEV)]
        }

        plugin = ovs.OvsPlugin.load("ovs")
        plugin.plug(self.vif_vhostuser, self.instance)
        _create_vif_port.assert_has_calls(calls['_create_vif_port'])
        ensure_ovs_bridge.assert_has_calls(calls['ensure_ovs_bridge'])

    @mock.patch.object(linux_net, 'ensure_ovs_bridge')
    @mock.patch.object(linux_net, 'create_ovs_vif_port')
    def test_plug_ovs_vhostuser_client(self, create_ovs_vif_port,
                                       ensure_ovs_bridge):
        calls = {
            'create_ovs_vif_port': [
                 mock.call(
                     'br0', 'vhub679325f-ca',
                     'e65867e0-9340-4a7f-a256-09af6eb7a3aa',
                     'ca:fe:de:ad:be:ef',
                     'f0000000-0000-0000-0000-000000000001',
                     1500, interface_type='dpdkvhostuserclient',
                     vhost_server_path='/var/run/openvswitch/vhub679325f-ca',
                     timeout=120)],
            'ensure_ovs_bridge': [mock.call('br0',
                                            constants.OVS_DATAPATH_NETDEV)]
        }

        plugin = ovs.OvsPlugin.load("ovs")
        plugin.plug(self.vif_vhostuser_client, self.instance)
        create_ovs_vif_port.assert_has_calls(calls['create_ovs_vif_port'])
        ensure_ovs_bridge.assert_has_calls(calls['ensure_ovs_bridge'])

    @mock.patch.object(linux_net, 'delete_ovs_vif_port')
    def test_unplug_ovs_vhostuser(self, delete_ovs_vif_port):
        calls = {
            'delete_ovs_vif_port': [mock.call('br0', 'vhub679325f-ca',
                                    timeout=120)]
        }
        plugin = ovs.OvsPlugin.load("ovs")
        plugin.unplug(self.vif_vhostuser, self.instance)
        delete_ovs_vif_port.assert_has_calls(calls['delete_ovs_vif_port'])

    @mock.patch.object(linux_net, 'ensure_ovs_bridge')
    @mock.patch.object(linux_net, 'get_ifname_by_pci_address')
    @mock.patch.object(linux_net, 'get_vf_num_by_pci_address')
    @mock.patch.object(linux_net, 'get_representor_port')
    @mock.patch.object(linux_net, 'set_interface_state')
    @mock.patch.object(ovs.OvsPlugin, '_create_vif_port')
    def test_plug_ovs_vf_passthrough(self, _create_vif_port,
                                   set_interface_state,
                                   get_representor_port,
                                   get_vf_num_by_pci_address,
                                   get_ifname_by_pci_address,
                                   ensure_ovs_bridge):

        get_ifname_by_pci_address.return_value = 'eth0'
        get_vf_num_by_pci_address.return_value = '2'
        get_representor_port.return_value = 'eth0_2'
        calls = {

            'ensure_ovs_bridge': [mock.call('br0',
                                  constants.OVS_DATAPATH_SYSTEM)],
            'get_ifname_by_pci_address': [mock.call('0002:24:12.3',
                                          pf_interface=True,
                                          switchdev=True)],
            'get_vf_num_by_pci_address': [mock.call('0002:24:12.3')],
            'get_representor_port': [mock.call('eth0', '2')],
            'set_interface_state': [mock.call('eth0_2', 'up')],
            '_create_vif_port': [mock.call(
                                 self.vif_ovs_vf_passthrough, 'eth0_2',
                                 self.instance)]
        }

        plugin = ovs.OvsPlugin.load("ovs")
        plugin.plug(self.vif_ovs_vf_passthrough, self.instance)
        ensure_ovs_bridge.assert_has_calls(calls['ensure_ovs_bridge'])
        get_ifname_by_pci_address.assert_has_calls(
            calls['get_ifname_by_pci_address'])
        get_vf_num_by_pci_address.assert_has_calls(
            calls['get_vf_num_by_pci_address'])
        get_representor_port.assert_has_calls(
            calls['get_representor_port'])
        set_interface_state.assert_has_calls(calls['set_interface_state'])
        _create_vif_port.assert_has_calls(calls['_create_vif_port'])

    @mock.patch.object(linux_net, 'get_ifname_by_pci_address')
    @mock.patch.object(linux_net, 'get_vf_num_by_pci_address')
    @mock.patch.object(linux_net, 'get_representor_port')
    @mock.patch.object(linux_net, 'set_interface_state')
    @mock.patch.object(linux_net, 'delete_ovs_vif_port')
    def test_unplug_ovs_vf_passthrough(self, delete_ovs_vif_port,
                                     set_interface_state,
                                     get_representor_port,
                                     get_vf_num_by_pci_address,
                                     get_ifname_by_pci_address):
        calls = {

            'get_ifname_by_pci_address': [mock.call('0002:24:12.3',
                                          pf_interface=True,
                                          switchdev=True)],
            'get_vf_num_by_pci_address': [mock.call('0002:24:12.3')],
            'get_representor_port': [mock.call('eth0', '2')],
            'set_interface_state': [mock.call('eth0_2', 'down')],
            'delete_ovs_vif_port': [mock.call('br0', 'eth0_2',
                                    delete_netdev=False)]
        }

        get_ifname_by_pci_address.return_value = 'eth0'
        get_vf_num_by_pci_address.return_value = '2'
        get_representor_port.return_value = 'eth0_2'
        plugin = ovs.OvsPlugin.load("ovs")
        plugin.unplug(self.vif_ovs_vf_passthrough, self.instance)
        get_ifname_by_pci_address.assert_has_calls(
            calls['get_ifname_by_pci_address'])
        get_vf_num_by_pci_address.assert_has_calls(
            calls['get_vf_num_by_pci_address'])
        get_representor_port.assert_has_calls(
            calls['get_representor_port'])
        delete_ovs_vif_port.assert_has_calls(calls['delete_ovs_vif_port'])
        set_interface_state.assert_has_calls(calls['set_interface_state'])
