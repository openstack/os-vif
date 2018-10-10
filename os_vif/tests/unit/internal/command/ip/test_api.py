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

import mock

from os_vif.tests.unit import base

from os_vif.internal.command.ip import api
from os_vif.internal.command.ip.linux import impl_pyroute2 as linux_ip_lib
from os_vif.internal.command.ip.windows import impl_netifaces as win_ip_lib


class TestIpApi(base.TestCase):

    @mock.patch("os.name", "nt")
    def test_get_impl_windows(self):
        ip_lib = api._get_impl()
        self.assertIsInstance(ip_lib, win_ip_lib.Netifaces)

    @mock.patch("os.name", "posix")
    def test_get_impl_linux(self):
        ip_lib = api._get_impl()
        self.assertIsInstance(ip_lib, linux_ip_lib.PyRoute2)
