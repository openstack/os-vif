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

import testtools

from os_vif import objects

from vif_plug_noop import noop


class PluginTest(testtools.TestCase):

    def __init__(self, *args, **kwargs):
        super(PluginTest, self).__init__(*args, **kwargs)
        objects.register_all()

        self.subnet_bridge = objects.subnet.Subnet(
            cidr='101.168.1.0/24',
            dns=['8.8.8.8'],
            gateway='101.168.1.1',
            dhcp_server='191.168.1.1')

        self.subnets = objects.subnet.SubnetList(
            objects=[self.subnet_bridge])

        self.network_ovs = objects.network.Network(
            id='437c6db5-4e6f-4b43-b64b-ed6a11ee5ba7',
            bridge='br0',
            subnets=self.subnets,
            vlan=99)

        self.vif = objects.vif.VIFBridge(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=self.network_ovs,
            vif_name='tap-xxx-yyy-zzz',
            bridge_name="qbrvif-xxx-yyy")

        self.instance = objects.instance_info.InstanceInfo(
            name='demo',
            uuid='f0000000-0000-0000-0000-000000000001')

        self.plugin = noop.NoOpPlugin.load("noop")

    def test_plug_noop(self):
        self.assertIn("plug", dir(self.plugin))
        self.plugin.plug(self.vif, self.instance)

    def test_unplug_noop(self):
        self.assertIn("unplug", dir(self.plugin))
        self.plugin.unplug(self.vif, self.instance)

    def test_describe_noop(self):
        self.assertIn("describe", dir(self.plugin))
        self.assertTrue(len(self.plugin.describe().vif_info) > 0)
