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

import importlib

from unittest import mock

from os_vif.internal.ip import api
from os_vif.tests.unit import base


class TestIpApi(base.TestCase):

    @staticmethod
    def _reload_original_os_module():
        importlib.reload(api)

    def test_get_impl_windows(self):
        self.addCleanup(self._reload_original_os_module)
        with mock.patch('os.name', 'nt'):
            importlib.reload(api)
            from os_vif.internal.ip.windows import impl_netifaces
            self.assertIsInstance(api.ip, impl_netifaces.Netifaces)

    def test_get_impl_linux(self):
        self.addCleanup(self._reload_original_os_module)
        with mock.patch('os.name', 'posix'):
            importlib.reload(api)
            from os_vif.internal.ip.linux import impl_pyroute2
            self.assertIsInstance(api.ip, impl_pyroute2.PyRoute2)
