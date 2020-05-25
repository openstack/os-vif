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

from oslo_concurrency import processutils
from oslo_config import cfg
from oslo_utils import uuidutils

from vif_plug_ovs import constants
from vif_plug_ovs import linux_net
from vif_plug_ovs.ovsdb import ovsdb_lib


CONF = cfg.CONF


class BaseOVSTest(testtools.TestCase):

    def setUp(self):
        super(BaseOVSTest, self).setUp()
        test_vif_plug_ovs_group = cfg.OptGroup('test_vif_plug_ovs')
        CONF.register_group(test_vif_plug_ovs_group)
        CONF.register_opt(cfg.IntOpt('ovs_vsctl_timeout', default=1500),
                          test_vif_plug_ovs_group)
        CONF.register_opt(cfg.StrOpt('ovsdb_interface', default='vsctl'),
                          test_vif_plug_ovs_group)
        CONF.register_opt(cfg.StrOpt('ovsdb_connection', default=None),
                          test_vif_plug_ovs_group)
        self.br = ovsdb_lib.BaseOVS(cfg.CONF.test_vif_plug_ovs)
        self.mock_db_set = mock.patch.object(self.br.ovsdb, 'db_set').start()
        self.mock_del_port = mock.patch.object(self.br.ovsdb,
                                               'del_port').start()
        self.mock_add_port = mock.patch.object(self.br.ovsdb,
                                               'add_port').start()
        self.mock_add_br = mock.patch.object(self.br.ovsdb, 'add_br').start()
        self.mock_transaction = mock.patch.object(self.br.ovsdb,
                                                  'transaction').start()

    def test__set_mtu_request(self):
        self.br._set_mtu_request('device', 1500)
        calls = [mock.call('Interface', 'device', ('mtu_request', 1500))]
        self.mock_db_set.assert_has_calls(calls)

    @mock.patch('sys.platform', constants.PLATFORM_LINUX)
    @mock.patch.object(linux_net, 'set_device_mtu')
    def test__update_device_mtu_interface_not_vhostuser_linux(self,
            mock_set_device_mtu):
        self.br.update_device_mtu('device', 1500, 'not_vhost')
        mock_set_device_mtu.assert_has_calls([mock.call('device', 1500)])

    @mock.patch('sys.platform', constants.PLATFORM_WIN32)
    @mock.patch.object(linux_net, 'set_device_mtu')
    def test__update_device_mtu_interface_not_vhostuser_windows(self,
            mock_set_device_mtu):
        self.br.update_device_mtu('device', 1500, 'not_vhost')
        mock_set_device_mtu.assert_not_called()

    def test__update_device_mtu_interface_vhostuser_supports_mtu_req(self):
        with mock.patch.object(self.br, '_ovs_supports_mtu_requests',
                return_value=True), \
                mock.patch.object(self.br, '_set_mtu_request') as \
                mock_set_mtu_request:
            self.br.update_device_mtu('device', 1500,
                                       constants.OVS_VHOSTUSER_INTERFACE_TYPE)
            mock_set_mtu_request.assert_has_calls([mock.call('device', 1500)])

    def test__update_device_mtu_interface_vhostuser_not_supports_mtu_req(self):
        with mock.patch.object(self.br, '_ovs_supports_mtu_requests',
                return_value=False), \
                mock.patch.object(self.br, '_set_mtu_request') as \
                mock_set_mtu_request:
            self.br.update_device_mtu('device', 1500,
                                       constants.OVS_VHOSTUSER_INTERFACE_TYPE)
            mock_set_mtu_request.assert_not_called()

    def test_create_ovs_vif_port(self):
        iface_id = 'iface_id'
        mac = 'ca:fe:ca:fe:ca:fe'
        instance_id = uuidutils.generate_uuid()
        interface_type = constants.OVS_VHOSTUSER_INTERFACE_TYPE
        vhost_server_path = '/fake/path'
        device = 'device'
        bridge = 'bridge'
        mtu = 1500
        external_ids = {'iface-id': iface_id,
                        'iface-status': 'active',
                        'attached-mac': mac,
                        'vm-uuid': instance_id}
        values = [('external_ids', external_ids),
                  ('type', interface_type),
                  ('options', {'vhost-server-path': vhost_server_path})
                  ]
        with mock.patch.object(self.br, 'update_device_mtu',
                               return_value=True) as mock_update_device_mtu, \
                mock.patch.object(self.br, '_ovs_supports_mtu_requests',
                                  return_value=True):
            self.br.create_ovs_vif_port(bridge, device, iface_id, mac,
                                        instance_id, mtu=mtu,
                                        interface_type=interface_type,
                                        vhost_server_path=vhost_server_path,
                                        tag=4000)
            self.mock_add_port.assert_has_calls([mock.call(bridge, device)])
            self.mock_db_set.assert_has_calls(
                [mock.call('Port', device, ('tag', 4000)),
                 mock.call('Interface', device, *values)])
            mock_update_device_mtu.assert_has_calls(
                [mock.call(device, mtu, interface_type=interface_type)])

    def test_create_ovs_vif_port_type_dpdk(self):
        iface_id = 'iface_id'
        mac = 'ca:fe:ca:fe:ca:fe'
        instance_id = uuidutils.generate_uuid()
        interface_type = constants.OVS_DPDK_INTERFACE_TYPE
        device = 'device'
        bridge = 'bridge'
        mtu = 1500
        pf_pci = '0000:02:00.1'
        vf_num = '0'
        external_ids = {'iface-id': iface_id,
                        'iface-status': 'active',
                        'attached-mac': mac,
                        'vm-uuid': instance_id}
        values = [('external_ids', external_ids),
                  ('type', interface_type),
                  ('options', {'dpdk-devargs':
                               '0000:02:00.1,representor=[0]'})]
        with mock.patch.object(self.br, 'update_device_mtu',
                               return_value=True) as mock_update_device_mtu, \
                mock.patch.object(self.br, '_ovs_supports_mtu_requests',
                                  return_value=True):
            self.br.create_ovs_vif_port(bridge, device, iface_id, mac,
                                        instance_id, mtu=mtu,
                                        interface_type=interface_type,
                                        pf_pci=pf_pci, vf_num=vf_num)
            self.mock_add_port.assert_has_calls([mock.call(bridge, device)])
            self.mock_db_set.assert_has_calls(
                [mock.call('Interface', device, *values)])
            mock_update_device_mtu.assert_has_calls(
                [mock.call(device, mtu, interface_type=interface_type)])

    def test_update_ovs_vif_port(self):
        with mock.patch.object(self.br, 'update_device_mtu') as \
                mock_update_device_mtu:
            self.br.update_ovs_vif_port('device', mtu=1500,
                interface_type=constants.OVS_VHOSTUSER_INTERFACE_TYPE)
            mock_update_device_mtu.assert_has_calls(
                [mock.call(
                    'device', 1500,
                    interface_type=constants.OVS_VHOSTUSER_INTERFACE_TYPE)])

    @mock.patch.object(linux_net, 'delete_net_dev')
    def test_delete_ovs_vif_port(self, mock_delete_net_dev):
        self.br.delete_ovs_vif_port('bridge', 'device')
        self.mock_del_port.assert_has_calls(
            [mock.call('device', bridge='bridge', if_exists=True)])
        mock_delete_net_dev.assert_has_calls([mock.call('device')])

    @mock.patch.object(linux_net, 'delete_net_dev')
    def test_delete_ovs_vif_port_no_delete_netdev(self, mock_delete_net_dev):
        self.br.delete_ovs_vif_port('bridge', 'device', delete_netdev=False)
        self.mock_del_port.assert_has_calls(
            [mock.call('device', bridge='bridge', if_exists=True)])
        mock_delete_net_dev.assert_not_called()

    def test_ensure_ovs_bridge(self):
        self.br.ensure_ovs_bridge('bridge', constants.OVS_DATAPATH_SYSTEM)
        self.mock_add_br('bridge', may_exist=True,
                         datapath_type=constants.OVS_DATAPATH_SYSTEM)

    def test__ovs_supports_mtu_requests(self):
        with mock.patch.object(self.br.ovsdb, 'db_list') as mock_db_list:
            self.assertTrue(self.br._ovs_supports_mtu_requests())
            mock_db_list.assert_called_once_with('Interface',
                                                 columns=['mtu_request'])

    def test__ovs_supports_mtu_requests_not_supported(self):
        with mock.patch.object(self.br.ovsdb, 'db_list') as mock_db_list:
            mock_db_list.side_effect = processutils.ProcessExecutionError(
                stderr='ovs-vsctl: Interface does not contain a column whose '
                       'name matches "mtu_request"')
            self.assertFalse(self.br._ovs_supports_mtu_requests())
            mock_db_list.assert_called_once_with('Interface',
                                                 columns=['mtu_request'])

    def test__ovs_supports_mtu_requests_other_error(self):
        with mock.patch.object(self.br.ovsdb, 'db_list') as mock_db_list:
            mock_db_list.side_effect = processutils.ProcessExecutionError(
                stderr='other error')
            self.assertRaises(processutils.ProcessExecutionError,
                              self.br._ovs_supports_mtu_requests)
            mock_db_list.assert_called_once_with('Interface',
                                                 columns=['mtu_request'])
