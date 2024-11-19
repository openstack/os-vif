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

import fixtures
import random


from unittest import mock

import testscenarios

from oslo_concurrency import processutils
from oslo_config import cfg
from oslo_utils import uuidutils

from vif_plug_ovs import constants
from vif_plug_ovs import linux_net
from vif_plug_ovs import ovs
from vif_plug_ovs.ovsdb import ovsdb_lib
from vif_plug_ovs import privsep
from vif_plug_ovs.tests.functional import base


CONF = cfg.CONF


@privsep.vif_plug_test.entrypoint
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
        post_commit = (
            'ovsdbapp.schema.open_vswitch.impl_idl.'
            'OvsVsctlTransaction.post_commit'
        )
        # "this" is the self parmater which is a reference to the
        # OvsVsctlTransaction instance on which do_post_commit is defiend.

        def direct_post_commit(this, transaction):
            this.do_post_commit(transaction)

        self.useFixture(fixtures.MonkeyPatch(post_commit, direct_post_commit))

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
            with self._ovsdb.transaction() as txn:
                self.ovs._set_mtu_request(txn, port_name, 1000)
            self._check_parameter('Interface', port_name, 'mtu', 1000)
            with self._ovsdb.transaction() as txn:
                self.ovs._set_mtu_request(txn, port_name, 1500)
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
        self._check_parameter(
            'Interface', port_name, 'options', expected_vhost_server_path
        )
        self._check_parameter('Port', port_name, 'tag', 2000)
        self._check_parameter('Port', port_name, 'qos', [])

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

    def test_create_ovs_vif_port_with_default_qos(self):
        if self.interface == 'native':
            self.skipTest(
                'test_create_ovs_vif_port_with_default_qos is unstable '
                'when run with the native driver, see: '
                'https://bugs.launchpad.net/os-vif/+bug/2087982')
        port_name = 'qos-port-' + self.interface
        iface_id = 'iface_id'
        mac = 'ca:fe:ca:fe:ca:fe'
        instance_id = uuidutils.generate_uuid()
        mtu = 1500
        interface_type = 'internal'
        qos_type = CONF.os_vif_ovs.default_qos_type

        self.addCleanup(self._del_bridge, self.brname)
        self._add_bridge(self.brname)

        self.addCleanup(
            self.ovs.delete_ovs_vif_port, self.brname, port_name,
            delete_netdev=False, qos_type=qos_type
        )
        self.ovs.create_ovs_vif_port(
            self.brname, port_name, iface_id, mac,
            instance_id, mtu=mtu, interface_type=interface_type,
            tag=2000, qos_type=qos_type
        )

        # first we assert that the standard parameters are set correctly
        expected_external_ids = {'iface-status': 'active',
                                 'iface-id': iface_id,
                                 'attached-mac': mac,
                                 'vm-uuid': instance_id}
        self._check_parameter('Interface', port_name, 'external_ids',
                              expected_external_ids)
        self._check_parameter('Interface', port_name, 'type', interface_type)
        self._check_parameter('Port', port_name, 'tag', 2000)

        # now we check that the port has a qos policy attached
        qos_uuid = self.ovs.get_qos(
            port_name, qos_type
        )[0]['_uuid']
        self._check_parameter('Port', port_name, 'qos', qos_uuid)

        # finally we check that the qos policy has the correct parameters
        self._check_parameter(
            'QoS', str(qos_uuid), 'type', qos_type
        )

    def test_delete_qos_if_exists(self):
        port_name = 'del-qos-port-' + self.interface
        iface_id = 'iface_id'
        mac = 'ca:fe:ca:fe:ca:fe'
        instance_id = uuidutils.generate_uuid()
        interface_type = 'internal'
        qos_type = CONF.os_vif_ovs.default_qos_type

        # setup test by creating a bridge and port, and register
        # cleanup funcitons to avoid leaking them.
        self.addCleanup(self._del_bridge, self.brname)
        self._add_bridge(self.brname)
        self.addCleanup(
            self.ovs.delete_ovs_vif_port, self.brname, port_name,
            delete_netdev=False, qos_type=qos_type
        )
        self.ovs.create_ovs_vif_port(
            self.brname, port_name, iface_id, mac,
            instance_id, interface_type=interface_type,
            qos_type=qos_type
        )

        # now we check that the port has a qos policy attached
        qos_uuid = self.ovs.get_qos(
            port_name, CONF.os_vif_ovs.default_qos_type
        )[0]['_uuid']
        self._check_parameter('Port', port_name, 'qos', qos_uuid)

        # finally we check that the qos policy has the correct parameters
        self._check_parameter(
            'QoS', str(qos_uuid), 'type', qos_type
        )

        # we need to delete the port directly in the db to remove
        # any references to the qos policy
        self.ovs.ovsdb.del_port(
            port_name, bridge=self.brname, if_exists=True).execute()
        # then we can delete the qos policy
        self.ovs.delete_qos_if_exists(port_name, qos_type)
        self._check_parameter(
            'QoS', str(qos_uuid), 'type', None
        )
        # invoking the delete when the policy does not exist
        # should not result in an error
        self.ovs.delete_qos_if_exists(port_name, qos_type)
        self._check_parameter(
            'QoS', str(qos_uuid), 'type', None
        )

    def test_get_qos(self):
        port_name = 'get-qos-' + self.interface
        iface_id = 'iface_id'
        mac = 'ca:fe:ca:fe:ca:fe'
        instance_id = uuidutils.generate_uuid()
        interface_type = 'internal'
        qos_type = CONF.os_vif_ovs.default_qos_type
        # initally no qos policy should exist
        self.assertEqual(0, len(self.ovs.get_qos(port_name, qos_type)))

        # if we create a port with a qos policy get_qos should
        # return the policy
        self.addCleanup(self._del_bridge, self.brname)
        self._add_bridge(self.brname)
        self.addCleanup(
            self.ovs.delete_ovs_vif_port, self.brname, port_name,
            delete_netdev=False, qos_type=qos_type
        )
        self.ovs.create_ovs_vif_port(
            self.brname, port_name, iface_id, mac,
            instance_id, interface_type=interface_type,
            qos_type=qos_type
        )
        # result should be a list of lenght 1 containing the
        # qos policy created for the port we defied.
        result = self.ovs.get_qos(port_name, qos_type)
        self.assertEqual(1, len(result))
        self.assertIn('_uuid', result[0])
        self._check_parameter(
            'Port', port_name, 'qos', result[0]['_uuid']
        )
        # if we delete the port and its qos policy get_qos should
        # not return it.
        self.ovs.delete_ovs_vif_port(
            self.brname, port_name,
            delete_netdev=False, qos_type=qos_type
        )
        self.assertEqual(0, len(self.ovs.get_qos(port_name, qos_type)))

    def test_port_exists(self):
        port_name = 'port-exists-' + self.interface
        iface_id = 'iface_id'
        mac = 'ca:fe:ca:fe:ca:fe'
        instance_id = uuidutils.generate_uuid()
        interface_type = 'internal'

        self.assertFalse(self.ovs.port_exists(port_name, self.brname))

        self.addCleanup(self._del_bridge, self.brname)
        self._add_bridge(self.brname)
        self.addCleanup(
            self.ovs.delete_ovs_vif_port, self.brname, port_name,
            delete_netdev=False,
        )
        self.ovs.create_ovs_vif_port(
            self.brname, port_name, iface_id, mac,
            instance_id, interface_type=interface_type,
        )

        self.assertTrue(self.ovs.port_exists(port_name, self.brname))
