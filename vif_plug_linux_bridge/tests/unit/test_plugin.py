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

from os_vif import objects

from vif_plug_linux_bridge import constants
from vif_plug_linux_bridge import linux_bridge
from vif_plug_linux_bridge import linux_net


class PluginTest(testtools.TestCase):

    def __init__(self, *args, **kwargs):
        super(PluginTest, self).__init__(*args, **kwargs)

        objects.register_all()

        self.instance = objects.instance_info.InstanceInfo(
            name='demo',
            uuid='f0000000-0000-0000-0000-000000000001')

    @mock.patch.object(linux_net, 'ensure_vlan_bridge')
    @mock.patch.object(linux_net, 'ensure_bridge')
    def test_plug_bridge(self, mock_ensure_bridge,
                         mock_ensure_vlan_bridge):
        network = objects.network.Network(
            id='437c6db5-4e6f-4b43-b64b-ed6a11ee5ba7',
            bridge='br0')

        vif = objects.vif.VIFBridge(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=network,
            dev_name='tap-xxx-yyy-zzz',
            bridge_name="br0")

        plugin = linux_bridge.LinuxBridgePlugin.load(constants.PLUGIN_NAME)
        plugin.plug(vif, self.instance)

        mock_ensure_bridge.assert_not_called()
        mock_ensure_vlan_bridge.assert_not_called()

    def test_plug_bridge_create_br_mtu_in_model(self):
        self._test_plug_bridge_create_br(mtu=1234)

    def test_plug_bridge_create_br_mtu_from_config(self):
        self._test_plug_bridge_create_br()

    @mock.patch.object(linux_net, 'ensure_vlan_bridge')
    @mock.patch.object(linux_net, 'ensure_bridge')
    def _test_plug_bridge_create_br(self, mock_ensure_bridge,
                                   mock_ensure_vlan_bridge,
                                   mtu=None):
        network = objects.network.Network(
            id='437c6db5-4e6f-4b43-b64b-ed6a11ee5ba7',
            bridge='br0',
            bridge_interface='eth0',
            should_provide_bridge=True,
            mtu=mtu)

        vif = objects.vif.VIFBridge(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=network,
            dev_name='tap-xxx-yyy-zzz',
            has_traffic_filtering=True,
            bridge_name="br0")

        plugin = linux_bridge.LinuxBridgePlugin.load(constants.PLUGIN_NAME)
        plugin.plug(vif, self.instance)

        mock_ensure_bridge.assert_called_with("br0", "eth0",
                                              filtering=False,
                                              mtu=mtu or 1500)
        mock_ensure_vlan_bridge.assert_not_called()

        mock_ensure_bridge.reset_mock()
        vif.has_traffic_filtering = False
        plugin.plug(vif, self.instance)
        mock_ensure_bridge.assert_called_with("br0", "eth0",
                                              filtering=True,
                                              mtu=mtu or 1500)

    def test_plug_bridge_create_br_vlan_mtu_in_model(self):
        self._test_plug_bridge_create_br_vlan(mtu=1234)

    def test_plug_bridge_create_br_vlan_mtu_from_config(self):
        self._test_plug_bridge_create_br_vlan()

    @mock.patch.object(linux_net, 'ensure_vlan_bridge')
    @mock.patch.object(linux_net, 'ensure_bridge')
    def _test_plug_bridge_create_br_vlan(self, mock_ensure_bridge,
                                         mock_ensure_vlan_bridge,
                                         mtu=None):
        network = objects.network.Network(
            id='437c6db5-4e6f-4b43-b64b-ed6a11ee5ba7',
            bridge='br0',
            bridge_interface='eth0',
            vlan=99,
            should_provide_bridge=True,
            should_provide_vlan=True,
            mtu=mtu)

        vif = objects.vif.VIFBridge(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=network,
            dev_name='tap-xxx-yyy-zzz',
            bridge_name="br0")

        plugin = linux_bridge.LinuxBridgePlugin.load(constants.PLUGIN_NAME)
        plugin.plug(vif, self.instance)

        mock_ensure_bridge.assert_not_called()
        mock_ensure_vlan_bridge.assert_called_with(
            99, "br0", "eth0", mtu=mtu or 1500)
