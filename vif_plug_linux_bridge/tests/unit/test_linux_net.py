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

import fixtures
import testtools

from oslo_concurrency import lockutils
from oslo_concurrency import processutils
from oslo_config import cfg
from oslo_config import fixture as config_fixture
from oslo_log.fixture import logging_error as log_fixture

from os_vif.internal.ip.api import ip as ip_lib

from vif_plug_linux_bridge import linux_net
from vif_plug_linux_bridge import privsep

CONF = cfg.CONF


class LinuxNetTest(testtools.TestCase):

    def setUp(self):
        super(LinuxNetTest, self).setUp()

        privsep.vif_plug.set_client_mode(False)
        lock_path = self.useFixture(fixtures.TempDir()).path
        self.fixture = self.useFixture(
            config_fixture.Config(lockutils.CONF))
        self.fixture.config(lock_path=lock_path,
                            group='oslo_concurrency')
        self.useFixture(log_fixture.get_logging_handle_error_fixture())

    @mock.patch.object(ip_lib, "set")
    def test_set_device_mtu(self, mock_ip_set):
        linux_net._set_device_mtu(dev='fakedev', mtu=1500)
        mock_ip_set.assert_called_once_with('fakedev', mtu=1500,
                                            check_exit_code=[0, 2, 254])

    @mock.patch.object(processutils, "execute")
    def test_set_device_invalid_mtu(self, mock_exec):
        linux_net._set_device_mtu(dev='fakedev', mtu=None)
        mock_exec.assert_not_called()

    @mock.patch.object(ip_lib, "add")
    @mock.patch.object(ip_lib, "set")
    @mock.patch.object(ip_lib, "exists", return_value=False)
    @mock.patch.object(linux_net, "_set_device_mtu")
    def test_ensure_vlan(self, mock_set_mtu, mock_dev_exists, mock_ip_set,
                         mock_ip_add):
        linux_net._ensure_vlan_privileged(123, 'fake-bridge',
                                          mac_address='fake-mac',
                                          mtu=1500)
        self.assertTrue(mock_dev_exists.called)
        set_calls = [mock.call('vlan123', address='fake-mac',
                               check_exit_code=[0, 2, 254]),
                     mock.call('vlan123', state='up',
                               check_exit_code=[0, 2, 254])]
        mock_ip_add.assert_called_once_with(
            'vlan123', 'vlan', link='fake-bridge', vlan_id=123,
            check_exit_code=[0, 2, 254])
        mock_ip_set.assert_has_calls(set_calls)
        mock_set_mtu.assert_called_once_with('vlan123', 1500)

    @mock.patch.object(linux_net, "_ensure_bridge_privileged")
    @mock.patch.object(linux_net, "_ensure_bridge_filtering")
    def test_ensure_bridge(self, mock_filtering, mock_priv):
        linux_net.ensure_bridge("br0", None, filtering=False)

        mock_priv.assert_called_once_with("br0", None, None, True,
                                          filtering=False, mtu=None)
        mock_filtering.assert_not_called()

        linux_net.ensure_bridge("br0", None, filtering=True)
        mock_filtering.assert_called_once_with("br0", True)

    @mock.patch.object(ip_lib, "exists", return_value=False)
    @mock.patch.object(ip_lib, "add")
    def test_ensure_bridge_addbr_exception(self, mock_add, mock_dev_exists):
        mock_add.side_effect = ValueError()
        with testtools.ExpectedException(ValueError):
            linux_net.ensure_bridge("br0", None, filtering=False)

    @mock.patch.object(ip_lib, "add")
    @mock.patch.object(ip_lib, "set")
    @mock.patch.object(linux_net, "_arp_filtering")
    @mock.patch.object(linux_net, "_set_device_mtu")
    @mock.patch.object(linux_net, "_disable_ipv6")
    @mock.patch.object(linux_net, "_update_bridge_routes")
    @mock.patch.object(ip_lib, "exists")
    def test_ensure_bridge_priv_mtu_not_called(self, mock_dev_exists,
            mock_routes, mock_disable_ipv6, mock_set_mtu, mock_arp_filtering,
            mock_ip_set, mock_add):
        """This test validates that mtus are updated only if an interface
           is added to the bridge
        """
        mock_dev_exists.return_value = False
        linux_net._ensure_bridge_privileged("fake-bridge", None,
                                            None, False, mtu=1500)
        mock_set_mtu.assert_not_called()
        mock_ip_set.assert_called_once_with('fake-bridge', state='up')

    @mock.patch.object(ip_lib, "add")
    @mock.patch.object(ip_lib, "set")
    @mock.patch.object(linux_net, "_arp_filtering")
    @mock.patch.object(linux_net, "_set_device_mtu")
    @mock.patch.object(linux_net, "_disable_ipv6")
    @mock.patch.object(linux_net, "_update_bridge_routes")
    @mock.patch.object(ip_lib, "exists")
    def test_ensure_bridge_priv_mtu_order(self, mock_dev_exists, mock_routes,
            mock_disable_ipv6, mock_set_mtu, mock_arp_filtering, mock_ip_set,
            mock_add):
        """This test validates that when adding an interface
           to a bridge, the interface mtu is updated first
           followed by the bridge. This is required to work around
           https://bugs.launchpad.net/ubuntu/+source/linux/+bug/1399064
        """
        mock_dev_exists.side_effect = [False, True]
        linux_net._ensure_bridge_privileged("fake-bridge", "fake-interface",
                                            None, False, mtu=1500)
        calls = [mock.call('fake-interface', 1500),
                 mock.call('fake-bridge', 1500)]
        mock_set_mtu.assert_has_calls(calls)
        calls = [mock.call('fake-bridge', state='up'),
                 mock.call('fake-interface', master='fake-bridge', state='up',
                 check_exit_code=[0, 2, 254])]
        mock_ip_set.assert_has_calls(calls)

    @mock.patch('builtins.open')
    @mock.patch("os.path.exists")
    def test__disable_ipv6(self, mock_exists, mock_open):

        exists_path = "/proc/sys/net/ipv6/conf/br0/disable_ipv6"
        mock_exists.return_value = False

        linux_net._disable_ipv6("br0")
        mock_exists.assert_called_once_with(exists_path)
        mock_open.assert_not_called()

        mock_exists.reset_mock()
        mock_exists.return_value = True
        linux_net._disable_ipv6("br0")
        mock_exists.assert_called_once_with(exists_path)
        mock_open.assert_called_once_with(exists_path, 'w')
