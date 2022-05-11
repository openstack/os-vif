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
