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
import random

from os_vif.tests.unit import base
from os_vif import utils


class TestGetRandomMac(base.TestCase):

    @mock.patch.object(random, 'getrandbits', return_value=0xa2)
    def test_random_mac_generated(self, mock_rnd):
        mac = utils.get_random_mac(['aa', 'bb', '00', 'dd', 'ee', 'ff'])
        self.assertEqual('aa:bb:00:a2:a2:a2', mac)
        mock_rnd.assert_called_with(8)
