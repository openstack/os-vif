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

from unittest import mock

import testtools

from os_vif.internal.ip.api import ip as ip_lib
from os_vif import objects
from os_vif.objects import fields

from vif_plug_ovs import constants
from vif_plug_ovs import linux_net
from vif_plug_ovs import ovs
from vif_plug_ovs.ovsdb import ovsdb_lib


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

        self.network_ovs_trunk = objects.network.Network(
            id='437c6db5-4e6f-4b43-b64b-ed6a11ee5ba7',
            bridge='%s01' % constants.TRUNK_BR_PREFIX,
            subnets=self.subnets,
            vlan=99)

        self.network_ovs_mtu = objects.network.Network(
            id='437c6db5-4e6f-4b43-b64b-ed6a11ee5ba7',
            bridge='br0',
            subnets=self.subnets,
            vlan=99,
            mtu=1234)

        self.profile_ovs = objects.vif.VIFPortProfileOpenVSwitch(
            interface_id='e65867e0-9340-4a7f-a256-09af6eb7a3aa',
            datapath_type='netdev')

        self.profile_ovs_system = objects.vif.VIFPortProfileOpenVSwitch(
            interface_id='e65867e0-9340-4a7f-a256-09af6eb7a3aa',
            datapath_type='system')

        # This is used for ironic with vif_type=smartnic
        self.profile_ovs_smart_nic = objects.vif.VIFPortProfileOpenVSwitch(
            interface_id='e65867e0-9340-4a7f-a256-09af6eb7a3aa',
            create_port=True)

        self.profile_ovs_no_datatype = objects.vif.VIFPortProfileOpenVSwitch(
            interface_id='e65867e0-9340-4a7f-a256-09af6eb7a3aa',
            datapath_type='')

        self.vif_ovs_hybrid = objects.vif.VIFBridge(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=self.network_ovs,
            vif_name='tap-xxx-yyy-zzz',
            bridge_name="qbrvif-xxx-yyy",
            port_profile=self.profile_ovs_no_datatype)

        self.vif_ovs = objects.vif.VIFOpenVSwitch(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=self.network_ovs,
            vif_name='tap-xxx-yyy-zzz',
            port_profile=self.profile_ovs)

        # This is used for ironic with vif_type=smartnic
        self.vif_ovs_smart_nic = objects.vif.VIFOpenVSwitch(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=self.network_ovs,
            vif_name='rep0-0',
            port_profile=self.profile_ovs_smart_nic)

        self.vif_vhostuser = objects.vif.VIFVHostUser(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=self.network_ovs,
            path='/var/run/openvswitch/vhub679325f-ca',
            mode='client',
            port_profile=self.profile_ovs)

        self.vif_vhostuser_trunk = objects.vif.VIFVHostUser(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=self.network_ovs_trunk,
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
            port_profile=self.profile_ovs_system)

        self.vif_ovs_vf_dpdk = objects.vif.VIFHostDevice(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=self.network_ovs,
            dev_type=fields.VIFHostDeviceDevType.ETHERNET,
            dev_address='0002:24:12.3',
            port_profile=self.profile_ovs)

        self.instance = objects.instance_info.InstanceInfo(
            name='demo',
            uuid='f0000000-0000-0000-0000-000000000001')

    def test__get_vif_datapath_type(self):
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        dp_type = plugin._get_vif_datapath_type(
            self.vif_ovs, datapath=constants.OVS_DATAPATH_SYSTEM)
        self.assertEqual(self.profile_ovs.datapath_type, dp_type)

        dp_type = plugin._get_vif_datapath_type(
            self.vif_ovs_hybrid, datapath=constants.OVS_DATAPATH_SYSTEM)
        self.assertEqual(constants.OVS_DATAPATH_SYSTEM, dp_type)

    @mock.patch.object(ovsdb_lib.BaseOVS, 'create_ovs_vif_port')
    def test_create_vif_port(self, mock_create_ovs_vif_port):
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        plugin._create_vif_port(
            self.vif_ovs, mock.sentinel.vif_name, self.instance,
            interface_type=constants.OVS_VHOSTUSER_INTERFACE_TYPE)
        mock_create_ovs_vif_port.assert_called_once_with(
            self.vif_ovs.network.bridge, mock.sentinel.vif_name,
            self.vif_ovs.port_profile.interface_id,
            self.vif_ovs.address, self.instance.uuid,
            mtu=plugin.config.network_device_mtu,
            interface_type=constants.OVS_VHOSTUSER_INTERFACE_TYPE)

    @mock.patch.object(ovsdb_lib.BaseOVS, 'create_ovs_vif_port')
    def test_create_vif_port_mtu_in_model(self, mock_create_ovs_vif_port):
        self.vif_ovs.network = self.network_ovs_mtu
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        plugin._create_vif_port(
            self.vif_ovs, mock.sentinel.vif_name, self.instance,
            interface_type=constants.OVS_VHOSTUSER_INTERFACE_TYPE)
        mock_create_ovs_vif_port.assert_called_once_with(
            self.vif_ovs.network.bridge, mock.sentinel.vif_name,
            self.vif_ovs.port_profile.interface_id,
            self.vif_ovs.address, self.instance.uuid,
            mtu=self.network_ovs_mtu.mtu,
            interface_type=constants.OVS_VHOSTUSER_INTERFACE_TYPE)

    @mock.patch.object(ovsdb_lib.BaseOVS, 'create_ovs_vif_port')
    def test_create_vif_port_isolate(self, mock_create_ovs_vif_port):
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        with mock.patch.object(plugin.config, 'isolate_vif', True):
            plugin._create_vif_port(
                self.vif_ovs, mock.sentinel.vif_name, self.instance,
                interface_type=constants.OVS_VHOSTUSER_INTERFACE_TYPE)
            mock_create_ovs_vif_port.assert_called_once_with(
                self.vif_ovs.network.bridge, mock.sentinel.vif_name,
                self.vif_ovs.port_profile.interface_id,
                self.vif_ovs.address, self.instance.uuid,
                mtu=plugin.config.network_device_mtu,
                interface_type=constants.OVS_VHOSTUSER_INTERFACE_TYPE,
                tag=constants.DEAD_VLAN)

    @mock.patch.object(ovs, 'sys')
    @mock.patch.object(ovs.OvsPlugin, '_plug_vif_generic')
    def test_plug_ovs_port_bridge_false(self, plug_vif_generic, mock_sys):
        mock_sys.platform = 'linux'
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        with mock.patch.object(plugin.config, 'per_port_bridge', False):
            plugin.plug(self.vif_ovs, self.instance)
            plug_vif_generic.assert_called_once_with(
                self.vif_ovs, self.instance)

    @mock.patch.object(ovs, 'sys')
    @mock.patch.object(ovs.OvsPlugin, '_plug_port_bridge')
    def test_plug_ovs_port_bridge_true(self, plug_vif, mock_sys):
        mock_sys.platform = 'linux'
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        with mock.patch.object(plugin.config, 'per_port_bridge', True):
            plugin.plug(self.vif_ovs, self.instance)
            plug_vif.assert_called_once_with(self.vif_ovs, self.instance)

    @mock.patch.object(ovsdb_lib.BaseOVS, 'ensure_ovs_bridge')
    @mock.patch.object(ovs.OvsPlugin, "_create_vif_port")
    def test_plug_vif_generic(self, create_port, ensure_bridge):
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        plugin._plug_vif_generic(self.vif_ovs, self.instance)
        ensure_bridge.assert_called_once()
        # NOTE(sean-k-mooney): the interface will be plugged
        # by libvirt so we assert _create_vif_port is not called.
        create_port.assert_not_called()

    @mock.patch.object(linux_net, 'set_interface_state')
    @mock.patch.object(ovsdb_lib.BaseOVS, 'ensure_ovs_bridge')
    @mock.patch.object(ovs.OvsPlugin, '_update_vif_port')
    @mock.patch.object(ovs.OvsPlugin, '_create_vif_port')
    @mock.patch.object(linux_net, 'add_bridge_port')
    @mock.patch.object(linux_net, 'update_veth_pair')
    @mock.patch.object(linux_net, 'create_veth_pair')
    @mock.patch.object(ip_lib, 'exists')
    @mock.patch.object(linux_net, 'ensure_bridge')
    @mock.patch.object(ovs, 'sys')
    def test_plug_ovs_bridge(self, mock_sys, ensure_bridge, device_exists,
                             create_veth_pair, update_veth_pair,
                             add_bridge_port, _create_vif_port,
                             _update_vif_port, ensure_ovs_bridge,
                             set_interface_state):
        dp_type = ovs.OvsPlugin._get_vif_datapath_type(self.vif_ovs_hybrid)
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
            'ensure_ovs_bridge': [mock.call('br0', dp_type)]
        }

        # plugging new devices should result in devices being created

        device_exists.return_value = False
        mock_sys.platform = 'linux'
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
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
        plugin.plug(self.vif_ovs_hybrid, self.instance)
        create_veth_pair.assert_not_called()
        _create_vif_port.assert_not_called()
        update_veth_pair.assert_has_calls(calls['update_veth_pair'])
        _update_vif_port.assert_has_calls(calls['_update_vif_port'])

    @mock.patch.object(ovsdb_lib.BaseOVS, 'ensure_ovs_bridge')
    @mock.patch.object(ovs.OvsPlugin, '_create_vif_port')
    @mock.patch.object(ip_lib, 'exists', return_value=False)
    @mock.patch.object(ovs, 'sys')
    def _check_plug_ovs_windows(self, vif, mock_sys, mock_exists,
                                _create_vif_port, ensure_ovs_bridge):
        dp_type = ovs.OvsPlugin._get_vif_datapath_type(vif)
        calls = {
            'exists': [mock.call(vif.id)],
            '_create_vif_port': [mock.call(vif, vif.id, self.instance)],
            'ensure_ovs_bridge': [mock.call('br0', dp_type)]
        }

        mock_sys.platform = constants.PLATFORM_WIN32
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        plugin.plug(vif, self.instance)
        mock_exists.assert_has_calls(calls['exists'])
        _create_vif_port.assert_has_calls(calls['_create_vif_port'])
        ensure_ovs_bridge.assert_has_calls(calls['ensure_ovs_bridge'])

    def test_plug_ovs_windows(self):
        self._check_plug_ovs_windows(self.vif_ovs)

    def test_plug_ovs_bridge_windows(self):
        self._check_plug_ovs_windows(self.vif_ovs_hybrid)

    @mock.patch.object(ovsdb_lib.BaseOVS, 'delete_ovs_bridge')
    @mock.patch.object(ovs, 'sys')
    @mock.patch.object(ovs.OvsPlugin, '_unplug_vif_generic')
    def test_unplug_ovs_port_bridge_false(self, unplug, mock_sys,
                                          delete_ovs_bridge):
        mock_sys.platform = 'linux'
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        with mock.patch.object(plugin.config, 'per_port_bridge', False):
            plugin.unplug(self.vif_ovs, self.instance)
            unplug.assert_called_once_with(self.vif_ovs, self.instance)
        delete_ovs_bridge.assert_not_called()

    @mock.patch.object(ovsdb_lib.BaseOVS, 'delete_ovs_bridge')
    @mock.patch.object(ovs, 'sys')
    @mock.patch.object(ovs.OvsPlugin, '_unplug_port_bridge')
    def test_unplug_ovs_port_bridge_true(self, unplug, mock_sys,
                                         delete_ovs_bridge):
        mock_sys.platform = 'linux'
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        with mock.patch.object(plugin.config, 'per_port_bridge', True):
            plugin.unplug(self.vif_ovs, self.instance)
            unplug.assert_called_once_with(self.vif_ovs, self.instance)
        delete_ovs_bridge.assert_not_called()

    @mock.patch.object(ovsdb_lib.BaseOVS, 'delete_ovs_bridge')
    @mock.patch.object(ovs.OvsPlugin, '_unplug_vif_generic')
    def test_unplug_vif_generic(self, delete_port, delete_ovs_bridge):
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        plugin._unplug_vif_generic(self.vif_ovs, self.instance)
        delete_port.assert_called_once()
        delete_ovs_bridge.assert_not_called()

    @mock.patch.object(ovsdb_lib.BaseOVS, 'delete_ovs_bridge')
    @mock.patch.object(ovsdb_lib.BaseOVS, 'delete_ovs_vif_port')
    @mock.patch.object(linux_net, 'delete_bridge')
    @mock.patch.object(ovs, 'sys')
    def test_unplug_ovs_bridge(self, mock_sys, delete_bridge,
                               delete_ovs_vif_port, delete_ovs_bridge):
        calls = {
            'delete_bridge': [mock.call('qbrvif-xxx-yyy', 'qvbb679325f-ca')],
            'delete_ovs_vif_port': [mock.call('br0', 'qvob679325f-ca')]
        }
        mock_sys.platform = 'linux'
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        plugin.unplug(self.vif_ovs_hybrid, self.instance)
        delete_bridge.assert_has_calls(calls['delete_bridge'])
        delete_ovs_vif_port.assert_has_calls(calls['delete_ovs_vif_port'])
        delete_ovs_bridge.assert_not_called()

    @mock.patch.object(ovsdb_lib.BaseOVS, 'delete_ovs_vif_port')
    @mock.patch.object(ovs, 'sys')
    def _check_unplug_ovs_windows(self, vif, mock_sys, delete_ovs_vif_port):
        mock_sys.platform = constants.PLATFORM_WIN32
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        plugin.unplug(vif, self.instance)
        delete_ovs_vif_port.assert_called_once_with('br0', vif.id,
                                                    delete_netdev=False)

    @mock.patch.object(ovsdb_lib.BaseOVS, 'delete_ovs_bridge')
    def test_unplug_ovs_windows(self, delete_ovs_bridge):
        self._check_unplug_ovs_windows(self.vif_ovs)
        delete_ovs_bridge.assert_not_called()

    @mock.patch.object(ovsdb_lib.BaseOVS, 'delete_ovs_bridge')
    def test_unplug_ovs_bridge_windows(self, delete_ovs_bridge):
        self._check_unplug_ovs_windows(self.vif_ovs_hybrid)
        delete_ovs_bridge.assert_not_called()

    @mock.patch.object(ovs.OvsPlugin, '_create_vif_port')
    def test_plug_ovs_vhostuser(self, _create_vif_port):
        dp_type = ovs.OvsPlugin._get_vif_datapath_type(self.vif_vhostuser)
        calls = [mock.call(
                self.vif_vhostuser, 'vhub679325f-ca',
                self.instance,
                interface_type='dpdkvhostuser',
                datapath_type=dp_type)]

        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        plugin.plug(self.vif_vhostuser, self.instance)
        _create_vif_port.assert_has_calls(calls)

    @mock.patch.object(ovsdb_lib.BaseOVS, 'create_ovs_vif_port')
    def test_plug_ovs_vhostuser_client(self, create_ovs_vif_port):
        dp_type = ovs.OvsPlugin._get_vif_datapath_type(
            self.vif_vhostuser_client)
        calls = [
                 mock.call(
                     'br0', 'vhub679325f-ca',
                     'e65867e0-9340-4a7f-a256-09af6eb7a3aa',
                     'ca:fe:de:ad:be:ef',
                     'f0000000-0000-0000-0000-000000000001',
                     mtu=1500, interface_type='dpdkvhostuserclient',
                     vhost_server_path='/var/run/openvswitch/vhub679325f-ca',
                     datapath_type=dp_type
                 )]

        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        plugin.plug(self.vif_vhostuser_client, self.instance)
        create_ovs_vif_port.assert_has_calls(calls)

    @mock.patch.object(ovsdb_lib.BaseOVS, 'delete_ovs_bridge')
    @mock.patch.object(ovsdb_lib.BaseOVS, 'delete_ovs_vif_port')
    def test_unplug_ovs_vhostuser(self, delete_ovs_vif_port,
                                  delete_ovs_bridge):
        calls = {
            'delete_ovs_vif_port': [mock.call('br0', 'vhub679325f-ca')]
        }
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        plugin.unplug(self.vif_vhostuser, self.instance)
        delete_ovs_vif_port.assert_has_calls(calls['delete_ovs_vif_port'])
        delete_ovs_bridge.assert_not_called()

    @mock.patch.object(ovsdb_lib.BaseOVS, 'delete_ovs_bridge')
    @mock.patch.object(ovsdb_lib.BaseOVS, 'delete_ovs_vif_port')
    def test_unplug_ovs_vhostuser_trunk(self, delete_ovs_vif_port,
                                        delete_ovs_bridge):
        bridge_name = '%s01' % constants.TRUNK_BR_PREFIX
        calls = {
            'delete_ovs_vif_port': [mock.call(bridge_name, 'vhub679325f-ca')]
        }
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        plugin.unplug(self.vif_vhostuser_trunk, self.instance)
        delete_ovs_vif_port.assert_has_calls(calls['delete_ovs_vif_port'])
        delete_ovs_bridge.assert_called_once_with(bridge_name)

    @mock.patch.object(ovsdb_lib.BaseOVS, 'ensure_ovs_bridge')
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

        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
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

    @mock.patch.object(ovsdb_lib.BaseOVS, 'delete_ovs_bridge')
    @mock.patch.object(linux_net, 'get_ifname_by_pci_address')
    @mock.patch.object(linux_net, 'get_vf_num_by_pci_address')
    @mock.patch.object(linux_net, 'get_representor_port')
    @mock.patch.object(linux_net, 'set_interface_state')
    @mock.patch.object(ovsdb_lib.BaseOVS, 'delete_ovs_vif_port')
    def test_unplug_ovs_vf_passthrough(self, delete_ovs_vif_port,
                                     set_interface_state,
                                     get_representor_port,
                                     get_vf_num_by_pci_address,
                                     get_ifname_by_pci_address,
                                     delete_ovs_bridge):
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
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        plugin.unplug(self.vif_ovs_vf_passthrough, self.instance)
        get_ifname_by_pci_address.assert_has_calls(
            calls['get_ifname_by_pci_address'])
        get_vf_num_by_pci_address.assert_has_calls(
            calls['get_vf_num_by_pci_address'])
        get_representor_port.assert_has_calls(
            calls['get_representor_port'])
        delete_ovs_vif_port.assert_has_calls(calls['delete_ovs_vif_port'])
        set_interface_state.assert_has_calls(calls['set_interface_state'])
        delete_ovs_bridge.assert_not_called()

    @mock.patch.object(ovsdb_lib.BaseOVS, 'ensure_ovs_bridge')
    @mock.patch.object(ovs.OvsPlugin, "_create_vif_port")
    def test_plug_vif_ovs_ironic_smart_nic(self, create_port, ensure_bridge):
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        with mock.patch.object(plugin.config, 'per_port_bridge', False):
            plugin.plug(self.vif_ovs_smart_nic, self.instance)
            ensure_bridge.assert_called_once()
            create_port.assert_called_once()

    @mock.patch.object(ovsdb_lib.BaseOVS, 'delete_ovs_bridge')
    @mock.patch.object(ovs.OvsPlugin, '_unplug_vif_generic')
    def test_unplug_vif_ovs_smart_nic(self, delete_port, delete_ovs_bridge):
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        with mock.patch.object(plugin.config, 'per_port_bridge', False):
            plugin.unplug(self.vif_ovs_smart_nic, self.instance)
            delete_port.assert_called_once()
        delete_ovs_bridge.assert_not_called()

    @mock.patch.object(linux_net, 'get_dpdk_representor_port_name')
    @mock.patch.object(ovsdb_lib.BaseOVS, 'ensure_ovs_bridge')
    @mock.patch.object(linux_net, 'get_vf_num_by_pci_address')
    @mock.patch.object(linux_net, 'get_pf_pci_from_vf')
    @mock.patch.object(ovs.OvsPlugin, '_create_vif_port')
    def test_plug_ovs_vf_dpdk(self, _create_vif_port,
                                   get_pf_pci_from_vf,
                                   get_vf_num_by_pci_address,
                                   ensure_ovs_bridge,
                                   get_dpdk_representor_port_name):

        pf_pci = self.vif_ovs_vf_dpdk.dev_address
        devname = 'vfrb679325f-ca'
        get_vf_num_by_pci_address.return_value = '2'
        get_pf_pci_from_vf.return_value = pf_pci
        get_dpdk_representor_port_name.return_value = devname
        calls = {
            'ensure_ovs_bridge': [mock.call('br0',
                                  constants.OVS_DATAPATH_NETDEV)],
            'get_vf_num_by_pci_address': [mock.call('0002:24:12.3')],
            'get_pf_pci_from_vf': [mock.call(pf_pci)],
            'get_dpdk_representor_port_name': [mock.call(
                self.vif_ovs_vf_dpdk.id)],
            '_create_vif_port': [mock.call(
                                 self.vif_ovs_vf_dpdk,
                                 devname,
                                 self.instance,
                                 interface_type='dpdk',
                                 pf_pci=pf_pci,
                                 vf_num='2')]}

        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        plugin.plug(self.vif_ovs_vf_dpdk, self.instance)
        ensure_ovs_bridge.assert_has_calls(
            calls['ensure_ovs_bridge'])
        get_vf_num_by_pci_address.assert_has_calls(
            calls['get_vf_num_by_pci_address'])
        get_pf_pci_from_vf.assert_has_calls(
            calls['get_pf_pci_from_vf'])
        get_dpdk_representor_port_name.assert_has_calls(
            calls['get_dpdk_representor_port_name'])
        _create_vif_port.assert_has_calls(
            calls['_create_vif_port'])

    @mock.patch.object(ovsdb_lib.BaseOVS, 'delete_ovs_bridge')
    @mock.patch.object(linux_net, 'get_dpdk_representor_port_name')
    @mock.patch.object(ovsdb_lib.BaseOVS, 'delete_ovs_vif_port')
    def test_unplug_ovs_vf_dpdk(self, delete_ovs_vif_port,
                                get_dpdk_representor_port_name,
                                delete_ovs_bridge):
        devname = 'vfrb679325f-ca'
        get_dpdk_representor_port_name.return_value = devname
        calls = {
            'get_dpdk_representor_port_name': [mock.call(
                self.vif_ovs_vf_dpdk.id)],
            'delete_ovs_vif_port': [mock.call('br0', devname,
                                              delete_netdev=False)]}
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        plugin.unplug(self.vif_ovs_vf_dpdk, self.instance)
        get_dpdk_representor_port_name.assert_has_calls(
            calls['get_dpdk_representor_port_name'])
        delete_ovs_vif_port.assert_has_calls(calls['delete_ovs_vif_port'])
        delete_ovs_bridge.assert_not_called()

    @mock.patch.object(ovsdb_lib.BaseOVS, 'create_patch_port_pair')
    @mock.patch.object(ovsdb_lib.BaseOVS, 'ensure_ovs_bridge')
    @mock.patch.object(ovs.OvsPlugin, "_create_vif_port")
    def test_plug_port_bridge(
            self, create_port, ensure_bridge, create_patch_port_pair):
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        plugin._plug_port_bridge(self.vif_ovs, self.instance)
        calls = [
            mock.call('br0', 'netdev'),
            mock.call('pbb679325f-ca8', 'netdev')
        ]
        ensure_bridge.assert_has_calls(calls)
        create_port.assert_called_once()
        create_patch_port_pair.assert_called_once()

    @mock.patch.object(ovsdb_lib.BaseOVS, 'delete_ovs_vif_port')
    @mock.patch.object(ovsdb_lib.BaseOVS, 'delete_ovs_bridge')
    def test_unplug_port_bridge(
            self, delete_ovs_bridge, delete_ovs_vif_port):
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        plugin._unplug_port_bridge(self.vif_ovs, self.instance)
        calls = [
            mock.call('br0', 'ibpb679325f-ca89-4ee0-a8be-6db1409b69ea'),
            mock.call(
                'pbb679325f-ca8', 'pbpb679325f-ca89-4ee0-a8be-6db1409b69ea'),
            mock.call('pbb679325f-ca8', 'tap-xxx-yyy-zzz')
        ]
        delete_ovs_vif_port.assert_has_calls(calls)
        delete_ovs_bridge.assert_called_once_with('pbb679325f-ca8')

    @mock.patch.object(ip_lib, 'exists', return_value=True)
    @mock.patch.object(ovs.OvsPlugin, '_unplug_bridge')
    def test_unplug_hybrid_bridge(self, m_unplug_bridge, m_ip_lib_exists):
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        plugin.unplug(self.vif_ovs, self.instance)
        m_unplug_bridge.assert_called_once()

    @mock.patch.object(ip_lib, 'exists', return_value=False)
    @mock.patch.object(ovs.OvsPlugin, '_unplug_vif_generic')
    def test_unplug_ovs(self, m_unplug_generic, m_ip_lib_exists):
        plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        plugin.unplug(self.vif_ovs, self.instance)
        m_unplug_generic.assert_called_once()
