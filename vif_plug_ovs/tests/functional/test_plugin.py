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

import testscenarios
import time
from unittest import mock

from oslo_concurrency import processutils
from oslo_config import cfg
from oslo_utils import uuidutils

from os_vif import objects

from vif_plug_ovs import constants
from vif_plug_ovs import ovs
from vif_plug_ovs.ovsdb import ovsdb_lib
from vif_plug_ovs import privsep
from vif_plug_ovs.tests.functional import base


CONF = cfg.CONF


@privsep.vif_plug.entrypoint
def run_privileged(*full_args):
    return processutils.execute(*full_args)[0].rstrip()


# derived from test_impl_pyroute2

def exist_device(device):
    try:
        run_privileged('ip', 'link', 'show', device)
        return True
    except processutils.ProcessExecutionError as e:
        if e.exit_code == 1:
            return False
        raise


def add_device(device, dev_type, peer=None, link=None,
                   vlan_id=None):
    if 'vlan' == dev_type:
        run_privileged('ip', 'link', 'add', 'link', link,
                         'name', device, 'type', dev_type, 'vlan', 'id',
                         vlan_id)
    elif 'veth' == dev_type:
        run_privileged('ip', 'link', 'add', device, 'type', dev_type,
                         'peer', 'name', peer)
    elif 'dummy' == dev_type:
        run_privileged('ip', 'link', 'add', device, 'type', dev_type)
    # ensure that the device exists to prevent racing with other ip commands
    for _ in range(10):
        if exist_device(device):
            return
        time.sleep(0.1)


def del_device(device):
    if exist_device(device):
        run_privileged('ip', 'link', 'del', device)


class TestOVSPlugin(testscenarios.WithScenarios,
                    base.VifPlugOvsBaseFunctionalTestCase):

    scenarios = [
        ('native', {'interface': 'native'}),
        ('vsctl', {'interface': 'vsctl'})
    ]

    def setUp(self):
        super(TestOVSPlugin, self).setUp()
        run_privileged('ovs-vsctl', 'set-manager', 'ptcp:6640')
        self.plugin = ovs.OvsPlugin.load(constants.PLUGIN_NAME)
        self.flags(ovsdb_interface=self.interface, group='os_vif_ovs')

        self.ovs = ovsdb_lib.BaseOVS(CONF.os_vif_ovs)
        self._ovsdb = self.ovs.ovsdb

        self.profile_ovs = objects.vif.VIFPortProfileOpenVSwitch(
            interface_id='e65867e0-9340-4a7f-a256-09af6eb7a3aa',
            datapath_type='netdev')

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

        self.network_ovs_trunk = objects.network.Network(
            id='437c6db5-4e6f-4b43-b64b-ed6a11ee5ba7',
            bridge='%s01' % constants.TRUNK_BR_PREFIX,
            subnets=self.subnets,
            vlan=99)

        self.vif_vhostuser_trunk = objects.vif.VIFVHostUser(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=self.network_ovs_trunk,
            path='/var/run/openvswitch/vhub679325f-ca',
            mode='client',
            port_profile=self.profile_ovs)

        self.profile_ovs_system = objects.vif.VIFPortProfileOpenVSwitch(
            interface_id='e65867e0-9340-4a7f-a256-09af6eb7a3aa',
            datapath_type='system',
            create_port=True)

        self.network_ovs = objects.network.Network(
            id='437c6db5-4e6f-4b43-b64b-ed6a11ee5ba7',
            bridge='br-qos-' + self.interface,
            subnets=self.subnets,
            vlan=99)

        self.vif_ovs_port = objects.vif.VIFOpenVSwitch(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=self.network_ovs,
            port_profile=self.profile_ovs_system,
            vif_name="qos-port-" + self.interface)

        self.instance = objects.instance_info.InstanceInfo(
            name='demo',
            uuid='f0000000-0000-0000-0000-000000000001')

    def test_plug_unplug_ovs_vhostuser_trunk(self):
        trunk_bridge = '%s01' % constants.TRUNK_BR_PREFIX
        self.plugin.plug(self.vif_vhostuser_trunk, self.instance)
        self.addCleanup(self._del_bridge, trunk_bridge)
        self.assertTrue(self._check_bridge(trunk_bridge))

        other_bridge = 'br-%s' % uuidutils.generate_uuid()
        self._add_bridge(other_bridge)
        self.addCleanup(self._del_bridge, other_bridge)
        self.plugin.unplug(self.vif_vhostuser_trunk, self.instance)
        self.assertTrue(self._check_bridge(other_bridge))
        self.assertFalse(self._check_bridge(trunk_bridge))

    def test_plug_unplug_ovs_port_with_qos(self):
        bridge = 'br-qos-' + self.interface
        vif_name = "qos-port-" + self.interface
        qos_type = CONF.os_vif_ovs.default_qos_type
        self.addCleanup(self._del_bridge, bridge)
        self.addCleanup(
            self.ovs.delete_ovs_vif_port, bridge, vif_name,
            delete_netdev=False, qos_type=qos_type
        )
        self.addCleanup(del_device, vif_name)
        add_device(vif_name, 'dummy')
        # pluging a vif will create the port and bridge
        # if either does not exist
        self.plugin.plug(self.vif_ovs_port, self.instance)
        self.assertTrue(self._check_bridge(bridge))
        self.assertTrue(self._check_port(vif_name, bridge))
        qos_uuid = self.ovs.get_qos(
            vif_name, qos_type
        )[0]['_uuid']
        self._check_parameter('Port', vif_name, 'qos', qos_uuid)
        self._check_parameter(
            'QoS', str(qos_uuid), 'type', qos_type
        )
        # unpluging a port will not delete the bridge.
        self.plugin.unplug(self.vif_ovs_port, self.instance)
        self.assertTrue(self._check_bridge(bridge))
        self.assertFalse(self._check_port(vif_name, bridge))
        self._check_parameter(
            'QoS', str(qos_uuid), 'type', None
        )

    def test_plug_br_int_isolate_vif_dead_vlan(self):
        with mock.patch.object(self.plugin.config, 'isolate_vif', True):
            network = objects.network.Network(
                id='5449523c-3a08-11ef-86d6-17149687aa4d',
                bridge='br-5449523c',
                subnets=self.subnets,
                vlan=99)
            vif = objects.vif.VIFOpenVSwitch(
                id='85cb9bc6-3a08-11ef-b2d4-9b7c38edd677',
                address='ca:fe:de:ad:be:ef',
                network=network,
                port_profile=self.profile_ovs_system,
                vif_name="port-85cb9bc6")
            self.plugin.plug(vif, self.instance)
            self.addCleanup(self._del_bridge, 'br-5449523c')
            self._check_parameter('Port', vif.vif_name, 'tag', 4095)

    def test_plug_trunk_bridge_ignores_isolate_vif(self):
        with mock.patch.object(self.plugin.config, 'isolate_vif', True):
            network = objects.network.Network(
                id='ef98b384-3a0f-11ef-9009-47345fca266f',
                bridge='tbr-ef98b384',
                subnets=self.subnets,
                vlan=99)
            vif = objects.vif.VIFOpenVSwitch(
                id='631f52bc-3a07-11ef-a006-1319ef9d6edd',
                address='ca:fe:de:ad:be:ef',
                network=network,
                port_profile=self.profile_ovs_system,
                vif_name='port-631f52bc')
            self.plugin.plug(vif, self.instance)
            self.addCleanup(self._del_bridge, 'tbr-ef98b384')
            self._check_parameter('Port', vif.vif_name, 'tag', [])
