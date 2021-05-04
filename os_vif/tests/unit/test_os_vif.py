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

from oslo_config import cfg
from stevedore import extension

import os_vif
from os_vif import exception
from os_vif import objects
from os_vif import opts
from os_vif import plugin
from os_vif.tests.unit import base


class DemoPlugin(plugin.PluginBase):

    CONFIG_OPTS = (
        cfg.BoolOpt("make_it_work",
                    default=False,
                    help="Make everything work correctly by setting this"),
        cfg.IntOpt("sleep_time",
                   default=0,
                   help="How long to artifically sleep")
    )

    def describe(self):
        pass

    def plug(self, vif, instance_info, config):
        pass

    def unplug(self, vif, instance_info, config):
        pass


class DemoPluginNoConfig(plugin.PluginBase):

    def describe(self):
        pass

    def plug(self, vif, instance_info, config):
        pass

    def unplug(self, vif, instance_info, config):
        pass


class TestOSVIF(base.TestCase):

    def setUp(self):
        super(TestOSVIF, self).setUp()
        os_vif._EXT_MANAGER = None

    @mock.patch('stevedore.extension.ExtensionManager')
    def test_initialize(self, mock_EM):
        self.assertIsNone(os_vif._EXT_MANAGER)
        # Note: the duplicate call for initialize is to validate
        # that the extension manager is only initialized once
        os_vif.initialize()
        os_vif.initialize()
        mock_EM.assert_called_once_with(
            invoke_on_load=False, namespace='os_vif')
        self.assertIsNotNone(os_vif._EXT_MANAGER)

    def test_load_plugin(self):
        obj = DemoPlugin.load("demo")
        self.assertTrue(hasattr(cfg.CONF, "os_vif_demo"))
        self.assertTrue(hasattr(cfg.CONF.os_vif_demo, "make_it_work"))
        self.assertTrue(hasattr(cfg.CONF.os_vif_demo, "sleep_time"))
        self.assertEqual(cfg.CONF.os_vif_demo.make_it_work, False)
        self.assertEqual(cfg.CONF.os_vif_demo.sleep_time, 0)

        self.assertEqual(obj.config, cfg.CONF.os_vif_demo)

    def test_load_plugin_no_config(self):
        obj = DemoPluginNoConfig.load("demonocfg")
        self.assertFalse(hasattr(cfg.CONF, "os_vif_demonocfg"))

        self.assertIsNone(obj.config)

    def test_plug_not_initialized(self):
        self.assertRaises(
            exception.LibraryNotInitialized,
            os_vif.plug, None, None)

    def test_unplug_not_initialized(self):
        self.assertRaises(
            exception.LibraryNotInitialized,
            os_vif.plug, None, None)

    @mock.patch.object(DemoPlugin, "plug")
    def test_plug(self, mock_plug):
        plg = extension.Extension(name="demo",
                                  entry_point="os-vif",
                                  plugin=DemoPlugin,
                                  obj=None)
        with mock.patch('stevedore.extension.ExtensionManager.names',
                        return_value=['foobar']),\
                mock.patch('stevedore.extension.ExtensionManager.__getitem__',
                           return_value=plg):
            os_vif.initialize()
            info = objects.instance_info.InstanceInfo()
            vif = objects.vif.VIFBridge(
                id='9a12694f-f95e-49fa-9edb-70239aee5a2c',
                plugin='foobar')
            os_vif.plug(vif, info)
            mock_plug.assert_called_once_with(vif, info)

    @mock.patch.object(DemoPlugin, "unplug")
    def test_unplug(self, mock_unplug):
        plg = extension.Extension(name="demo",
                                  entry_point="os-vif",
                                  plugin=DemoPlugin,
                                  obj=None)
        with mock.patch('stevedore.extension.ExtensionManager.names',
                        return_value=['foobar']),\
                mock.patch('stevedore.extension.ExtensionManager.__getitem__',
                           return_value=plg):
            os_vif.initialize()
            info = objects.instance_info.InstanceInfo()
            vif = objects.vif.VIFBridge(
                id='9a12694f-f95e-49fa-9edb-70239aee5a2c',
                plugin='foobar')
            os_vif.unplug(vif, info)
            mock_unplug.assert_called_once_with(vif, info)

    def test_host_info_all(self):
        os_vif.initialize()
        info = os_vif.host_info()
        # NOTE(sean-k-mooney): as out of tree plugins could be
        # visable in path assert only at at least all the in
        # intree plugins are loaded instead of an exact match.
        self.assertTrue(len(info.plugin_info) >= 3)

        plugins = {p.plugin_name: p for p in info.plugin_info}
        in_tree_plugin_names = ("linux_bridge", "ovs", "noop")
        self.assertTrue(all(name in plugins for name in in_tree_plugin_names))
        lb = plugins["linux_bridge"]
        self.assertTrue(any("VIFBridge" == vif.vif_object_name
                            for vif in lb.vif_info))

        ovs = plugins["ovs"]
        self.assertTrue(len(ovs.vif_info) >= 4)
        vif_names = (vif.vif_object_name for vif in ovs.vif_info)
        ovs_vifs = ("VIFBridge", "VIFOpenVSwitch",
                    "VIFVHostUser", "VIFHostDevice")
        self.assertTrue(all(name in ovs_vifs for name in vif_names))

        noop = plugins["noop"]
        self.assertTrue(any("VIFVHostUser" == vif.vif_object_name
                            for vif in noop.vif_info))

    def test_host_info_filtered(self):
        os_vif.initialize()
        info = os_vif.host_info(permitted_vif_type_names=["VIFOpenVSwitch"])

        self.assertEqual(len(info.plugin_info), 1)

        self.assertEqual(info.plugin_info[0].plugin_name, "ovs")
        vif_info = info.plugin_info[0].vif_info
        self.assertEqual(len(vif_info), 1)
        self.assertEqual(vif_info[0].vif_object_name, "VIFOpenVSwitch")

    def test_list_opts_entrypoints(self):
        list_opts = opts.list_plugins_opts()
        for group in list_opts:
            for opt in group[1]:
                self.assertTrue("oslo_config.cfg" == opt.__module__)
        self.assertGreaterEqual(len(list_opts), 3)
