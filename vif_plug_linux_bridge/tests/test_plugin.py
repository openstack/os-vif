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

import contextlib
import mock
import six
import testtools

from os_vif import objects

from vif_plug_linux_bridge import linux_bridge
from vif_plug_linux_bridge import linux_net


if six.PY2:
    nested = contextlib.nested
else:
    @contextlib.contextmanager
    def nested(*contexts):
        with contextlib.ExitStack() as stack:
            yield [stack.enter_context(c) for c in contexts]


class PluginTest(testtools.TestCase):

    def __init__(self, *args, **kwargs):
        super(PluginTest, self).__init__(*args, **kwargs)

        objects.register_all()

        self.instance = objects.instance_info.InstanceInfo(
            name='demo',
            uuid='f0000000-0000-0000-0000-000000000001')

    def test_plug_bridge(self):
        network = objects.network.Network(
            id='437c6db5-4e6f-4b43-b64b-ed6a11ee5ba7',
            bridge='br0')

        vif = objects.vif.VIFBridge(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=network,
            dev_name='tap-xxx-yyy-zzz',
            bridge_name="br0")

        with nested(
                mock.patch.object(linux_net, 'ensure_bridge'),
                mock.patch.object(linux_net, 'ensure_vlan_bridge')
        ) as (mock_ensure_bridge, mock_ensure_vlan_bridge):
            plugin = linux_bridge.LinuxBridgePlugin.load("linux_bridge")
            plugin.plug(vif, self.instance)

            self.assertEqual(len(mock_ensure_bridge.calls), 0)
            self.assertEqual(len(mock_ensure_vlan_bridge.calls), 0)

    def test_plug_bridge_create_br(self):
        network = objects.network.Network(
            id='437c6db5-4e6f-4b43-b64b-ed6a11ee5ba7',
            bridge='br0',
            bridge_interface='eth0',
            should_provide_bridge=True)

        vif = objects.vif.VIFBridge(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=network,
            dev_name='tap-xxx-yyy-zzz',
            bridge_name="br0")

        with nested(
                mock.patch.object(linux_net, 'ensure_bridge'),
                mock.patch.object(linux_net, 'ensure_vlan_bridge')
        ) as (mock_ensure_bridge, mock_ensure_vlan_bridge):
            plugin = linux_bridge.LinuxBridgePlugin.load("linux_bridge")
            plugin.plug(vif, self.instance)

            mock_ensure_bridge.assert_called_with("br0", "eth0")
            self.assertEqual(len(mock_ensure_vlan_bridge.calls), 0)

    def test_plug_bridge_create_br_vlan(self):
        network = objects.network.Network(
            id='437c6db5-4e6f-4b43-b64b-ed6a11ee5ba7',
            bridge='br0',
            bridge_interface='eth0',
            vlan=99,
            should_provide_bridge=True,
            should_provide_vlan=True)

        vif = objects.vif.VIFBridge(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=network,
            dev_name='tap-xxx-yyy-zzz',
            bridge_name="br0")

        with nested(
                mock.patch.object(linux_net, 'ensure_bridge'),
                mock.patch.object(linux_net, 'ensure_vlan_bridge')
        ) as (mock_ensure_bridge, mock_ensure_vlan_bridge):
            plugin = linux_bridge.LinuxBridgePlugin.load("linux_bridge")
            plugin.plug(vif, self.instance)

            self.assertEqual(len(mock_ensure_bridge.calls), 0)
            mock_ensure_vlan_bridge.assert_called_with(
                99, "br0", "eth0", mtu=1500)
