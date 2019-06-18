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

from os_vif.tests.unit import base
from vif_plug_ovs.ovsdb import impl_vsctl


class TestModuleLevelMethods(base.TestCase):

    def test__set_colval_args(self):
        col_values = [('mac', "aa:aa:aa:aa:aa:aa")]
        args = impl_vsctl._set_colval_args(*col_values)
        self.assertEqual(['mac=aa\:aa\:aa\:aa\:aa\:aa'], args)
