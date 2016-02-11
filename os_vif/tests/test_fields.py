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

from oslo_versionedobjects.tests import test_fields

from os_vif.objects import fields


class TestPCIAddress(test_fields.TestField):
    def setUp(self):
        super(TestPCIAddress, self).setUp()
        self.field = fields.PCIAddressField()
        self.coerce_good_values = [
            ('0000:02:00.0', '0000:02:00.0'),
            ('FFFF:FF:1F.7', 'ffff:ff:1f.7'),
            ('fFfF:fF:1F.7', 'ffff:ff:1f.7'),
        ]
        self.coerce_bad_values = [
            '000:02:00.0',  # Too short
            '00000:02:00.0',  # Too long
            'FFFF:FF:2F.7',  # Bad slot
            'FFFF:GF:1F.7',  # Bad octal
            1123123,  # Number
            {},  # dict
        ]
        self.to_primitive_values = self.coerce_good_values[0:1]
        self.from_primitive_values = self.coerce_good_values[0:1]
