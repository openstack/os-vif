#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from os_vif.tests.functional import base as os_vif_base


wait_until_true = os_vif_base.wait_until_true


class VifPlugOvsBaseFunctionalTestCase(os_vif_base.BaseFunctionalTestCase):
    """Base class for vif_plug_ovs functional tests."""

    COMPONENT_NAME = 'vif_plug_ovs'
    PRIVILEGED_GROUP = 'vif_plug_ovs_privileged'

    def _check_bridge(self, name):
        return self._ovsdb.br_exists(name).execute()

    def _add_bridge(self, name, may_exist=True, datapath_type=None):
        self._ovsdb.add_br(name, may_exist=may_exist,
                           datapath_type=datapath_type).execute()
        self.assertTrue(self._check_bridge(name))

    def _del_bridge(self, name):
        self._ovsdb.del_br(name).execute()
