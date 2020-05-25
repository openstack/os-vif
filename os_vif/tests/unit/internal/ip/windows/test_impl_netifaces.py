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

from unittest import mock

import netifaces

from os_vif.internal.ip.windows import impl_netifaces as ip_lib
from os_vif.tests.unit import base


class TestIPDevice(base.TestCase):

    def setUp(self):
        super(TestIPDevice, self).setUp()
        self.device_name = 'test_device'
        self.mock_log = mock.patch.object(ip_lib, "LOG").start()
        self.ip_lib = ip_lib.Netifaces()

    @mock.patch.object(netifaces, 'ifaddresses', return_value=True)
    def test_exists(self, mock_ifaddresses):
        self.assertTrue(self.ip_lib.exists(self.device_name))
        mock_ifaddresses.assert_called_once_with(self.device_name)

    @mock.patch.object(netifaces, 'ifaddresses', side_effect=ValueError())
    def test_exists_not_found(self, mock_ifaddresses):
        self.assertFalse(self.ip_lib.exists(self.device_name))
        mock_ifaddresses.assert_called_once_with(self.device_name)
        self.mock_log.warning.assert_called_once_with(
            "The device does not exist on the system: %s", self.device_name)

    @mock.patch.object(netifaces, 'ifaddresses', side_effect=OSError())
    def test_exists_os_error_exception(self, mock_ifaddresses):
        self.assertFalse(self.ip_lib.exists(self.device_name))
        mock_ifaddresses.assert_called_once_with(self.device_name)
        self.mock_log.error.assert_called_once_with(
            "Failed to get interface addresses: %s", self.device_name)
