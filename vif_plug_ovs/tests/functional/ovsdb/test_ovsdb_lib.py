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

import random

from unittest import mock

import testscenarios

from oslo_concurrency import processutils
from oslo_config import cfg
from oslo_utils import uuidutils
from ovsdbapp.schema.open_vswitch import impl_idl

from vif_plug_ovs import constants
from vif_plug_ovs import linux_net
from vif_plug_ovs import ovs
from vif_plug_ovs.ovsdb import ovsdb_lib
from vif_plug_ovs import privsep
from vif_plug_ovs.tests.functional import base


CONF = cfg.CONF


@privsep.vif_plug.entrypoint
def run_privileged(*full_args):
    return processutils.execute(*full_args)[0].rstrip()


class TestOVSDBLib(testscenarios.WithScenarios,
                   base.VifPlugOvsBaseFunctionalTestCase):

    scenarios = [
        ('native', {'interface': 'native'}),
        ('vsctl', {'interface': 'vsctl'})
    ]

    def setUp(self):
        super(TestOVSDBLib, self).setUp()
        run_privileged('ovs-vsctl', 'set-manager', 'ptcp:6640')

        # NOTE: (ralonsoh) load default configuration variables "CONFIG_OPTS"
        ovs.OvsPlugin.load('ovs')
        self.flags(ovsdb_interface=self.interface, group='os_vif_ovs')

        self.ovs = ovsdb_lib.BaseOVS(CONF.os_vif_ovs)
        self._ovsdb = self.ovs.ovsdb
        self.brname = ('br' + str(random.randint(1000, 9999)) + '-' +
                       self.interface)

        # Make sure exceptions pass through by calling do_post_commit directly
        mock.patch.object(
            impl_idl.OvsVsctlTransaction, 'post_commit',
            side_effect=impl_idl.OvsVsctlTransaction.do_post_commit).start()

    def _check_parameter(self, table, port, parameter, expected_value):
        def check_value():
            return (self._ovsdb.db_get(
                table, port, parameter).execute() == expected_value)

        self.assertTrue(base.wait_until_true(check_value, timeout=2,
                                             sleep=0.5))

    def _add_port(self, bridge, port, may_exist=True):
        with self._ovsdb.transaction() as txn:
            txn.add(self._ovsdb.add_port(bridge, port, may_exist=may_exist))
            txn.add(self._ovsdb.db_set('Interface', port,
                                       ('type', 'internal')))
        self.assertIn(port, self._list_ports_in_bridge(bridge))

    def _list_ports_in_bridge(self, bridge):
        return self._ovsdb.list_ports(bridge).execute()

    def test__set_mtu_request(self):
        port_name = 'port1-' + self.interface
        self._add_bridge(self.brname)
        self.addCleanup(self._del_bridge, self.brname)
        self._add_port(self.brname, port_name)
        if self.ovs._ovs_supports_mtu_requests():
            self.ovs._set_mtu_request(port_name, 1000)
            self._check_parameter('Interface', port_name, 'mtu', 1000)
            self.ovs._set_mtu_request(port_name, 1500)
            self._check_parameter('Interface', port_name, 'mtu', 1500)
        else:
            self.skipTest('Current version of Open vSwitch does not support '
                          '"mtu_request" parameter')

    def test_create_ovs_vif_port(self):
        port_name = 'port2-' + self.interface
        iface_id = 'iface_id'
        mac = 'ca:fe:ca:fe:ca:fe'
        instance_id = uuidutils.generate_uuid()
        interface_type = constants.OVS_VHOSTUSER_INTERFACE_TYPE
        vhost_server_path = '/fake/path'
        mtu = 1500
        self._add_bridge(self.brname)
        self.addCleanup(self._del_bridge, self.brname)

        self.ovs.create_ovs_vif_port(self.brname, port_name, iface_id, mac,
                                     instance_id, mtu=mtu,
                                     interface_type=interface_type,
                                     vhost_server_path=vhost_server_path,
                                     tag=2000)

        expected_external_ids = {'iface-status': 'active',
                                 'iface-id': iface_id,
                                 'attached-mac': mac,
                                 'vm-uuid': instance_id}
        self._check_parameter('Interface', port_name, 'external_ids',
                              expected_external_ids)
        self._check_parameter('Interface', port_name, 'type', interface_type)
        expected_vhost_server_path = {'vhost-server-path': vhost_server_path}
        self._check_parameter('Interface', port_name, 'options',
                              expected_vhost_server_path)
        self._check_parameter('Interface', port_name, 'options',
                              expected_vhost_server_path)
        self._check_parameter('Port', port_name, 'tag', 2000)

    @mock.patch.object(linux_net, 'delete_net_dev')
    def test_delete_ovs_vif_port(self, *mock):
        port_name = 'port3-' + self.interface
        self._add_bridge(self.brname)
        self.addCleanup(self._del_bridge, self.brname)

        self._add_port(self.brname, port_name)
        self.ovs.delete_ovs_vif_port(self.brname, port_name)
        self.assertNotIn(port_name, self._list_ports_in_bridge(self.brname))

    def test_ensure_ovs_bridge(self):
        bridge_name = 'bridge2-' + self.interface
        self.ovs.ensure_ovs_bridge(bridge_name, constants.OVS_DATAPATH_SYSTEM)
        self.assertTrue(self._check_bridge(bridge_name))
        self.addCleanup(self._del_bridge, bridge_name)

    def test_create_patch_port_pair(self):
        port_bridge = 'fake-pb'
        port_bridge_port = 'fake-pbp'
        int_bridge = 'pb-int'
        int_bridge_port = 'fake-ibp'
        iface_id = 'iface_id'
        mac = 'ca:fe:ca:fe:ca:fe'
        instance_id = uuidutils.generate_uuid()

        # deleting a bridge deletes all ports on bridges so we register the
        # bridge cleanup first so if we fail anywhere it runs.
        self.addCleanup(self._del_bridge, port_bridge)
        self.addCleanup(self._del_bridge, int_bridge)
        self.ovs.ensure_ovs_bridge(port_bridge, constants.OVS_DATAPATH_SYSTEM)
        self.ovs.ensure_ovs_bridge(int_bridge, constants.OVS_DATAPATH_SYSTEM)
        self.ovs.create_patch_port_pair(
            port_bridge, port_bridge_port, int_bridge, int_bridge_port,
            iface_id, mac, instance_id, tag=2000)
        self.assertTrue(self._check_bridge(port_bridge))
        self.assertTrue(self._check_bridge(int_bridge))

        expected_external_ids = {'iface-status': 'active',
                                 'iface-id': iface_id,
                                 'attached-mac': mac,
                                 'vm-uuid': instance_id}
        self._check_parameter(
            'Interface', int_bridge_port, 'external_ids',
            expected_external_ids)
        self._check_parameter('Interface', int_bridge_port, 'type', 'patch')
        port_opts = {'peer': port_bridge_port}
        self._check_parameter(
            'Interface', int_bridge_port, 'options', port_opts)
        self._check_parameter('Port', int_bridge_port, 'tag', 2000)
        port_opts = {'peer': int_bridge_port}
        self._check_parameter(
            'Interface', port_bridge_port, 'options', port_opts)
