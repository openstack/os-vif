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
        self.plugin = noop.NoOpPlugin.load("noop")

    def test_plug_noop(self):
        self.assertIn("plug", dir(self.plugin))
        self.plugin.plug(None, None)

    def test_unplug_noop(self):
        self.assertIn("unplug", dir(self.plugin))
        self.plugin.unplug(None, None)

    def test_describe_noop(self):
        self.assertIn("describe", dir(self.plugin))
        self.assertTrue(len(self.plugin.describe().vif_info) > 0)
