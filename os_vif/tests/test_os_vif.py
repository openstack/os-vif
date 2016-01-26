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

import mock

import os_vif
from os_vif import exception
from os_vif import objects
from os_vif import plugin
from os_vif.tests import base


class DemoPlugin(plugin.PluginBase):

    def describe(self):
        pass

    def plug(self, vif, instance_info):
        pass

    def unplug(self, vif, instance_info):
        pass


class TestOSVIF(base.TestCase):

    def setUp(self):
        super(TestOSVIF, self).setUp()
        os_vif._EXT_MANAGER = None

    @mock.patch('stevedore.extension.ExtensionManager')
    def test_initialize(self, mock_EM):
        self.assertEqual(None, os_vif._EXT_MANAGER)
        os_vif.initialize()
        os_vif.initialize()
        mock_EM.assert_called_once_with(
            invoke_args={}, invoke_on_load=True, namespace='os_vif')
        self.assertNotEqual(None, os_vif._EXT_MANAGER)

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
        plg = DemoPlugin()
        with mock.patch('stevedore.extension.ExtensionManager',
                        return_value={'foobar': plg}):
            os_vif.initialize()
            info = objects.instance_info.InstanceInfo()
            vif = objects.vif.VIFBridge(id='uniq',
                                        plugin='foobar')
            os_vif.plug(vif, info)
            mock_plug.assert_called_once_with(vif, info)

    @mock.patch.object(DemoPlugin, "unplug")
    def test_unplug(self, mock_unplug):
        plg = DemoPlugin()
        with mock.patch('stevedore.extension.ExtensionManager',
                        return_value={'foobar': plg}):
            os_vif.initialize()
            info = objects.instance_info.InstanceInfo()
            vif = objects.vif.VIFBridge(id='uniq',
                                        plugin='foobar')
            os_vif.unplug(vif, info)
            mock_unplug.assert_called_once_with(vif, info)
