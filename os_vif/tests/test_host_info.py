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

from os_vif import exception
from os_vif import objects
from os_vif.tests import base


class TestHostInfo(base.TestCase):

    def setUp(self):
        super(TestHostInfo, self).setUp()

        self.host_info = objects.host_info.HostInfo(
            plugin_info=[
                objects.host_info.HostPluginInfo(
                    plugin_name="linux_brige",
                    vif_info=[
                        objects.host_info.HostVIFInfo(
                            vif_object_name="VIFBridge",
                            min_version="1.0",
                            max_version="3.0"
                        ),
                    ]),
                objects.host_info.HostPluginInfo(
                    plugin_name="ovs",
                    vif_info=[
                        objects.host_info.HostVIFInfo(
                            vif_object_name="VIFBridge",
                            min_version="2.0",
                            max_version="7.0"
                        ),
                        objects.host_info.HostVIFInfo(
                            vif_object_name="VIFOpenVSwitch",
                            min_version="1.0",
                            max_version="2.0"
                        ),
                        objects.host_info.HostVIFInfo(
                            vif_object_name="VIFVHostUser",
                            min_version="1.0",
                            max_version="2.0"
                        ),
                    ])
            ])

    def test_serialization(self):
        json = self.host_info.obj_to_primitive()

        host_info = objects.host_info.HostInfo.obj_from_primitive(json)

        self.assertEqual(self.host_info, host_info)

    def test_plugin_existance(self):
        self.assertTrue(self.host_info.has_plugin("ovs"))
        self.assertFalse(self.host_info.has_plugin("fishfood"))

    def test_plugin_fetch(self):
        plugin = self.host_info.get_plugin("ovs")
        self.assertEqual("ovs", plugin.plugin_name)

        self.assertRaises(exception.NoMatchingPlugin,
                          self.host_info.get_plugin,
                          "fishfood")

    def test_vif_existance(self):
        plugin = self.host_info.get_plugin("ovs")
        self.assertTrue(plugin.has_vif("VIFOpenVSwitch"))
        self.assertFalse(plugin.has_vif("VIFFishFood"))

    def test_vif_fetch(self):
        plugin = self.host_info.get_plugin("ovs")

        vif = plugin.get_vif("VIFOpenVSwitch")
        self.assertEqual("VIFOpenVSwitch", vif.vif_object_name)

        self.assertRaises(exception.NoMatchingVIFClass,
                          plugin.get_vif,
                          "VIFFishFood")
