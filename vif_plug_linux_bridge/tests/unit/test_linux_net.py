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
import os.path
import testtools

import fixtures
from oslo_concurrency import lockutils
from oslo_concurrency import processutils
from oslo_config import cfg
from oslo_config import fixture as config_fixture
from oslo_log.fixture import logging_error as log_fixture

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

    @mock.patch.object(processutils, "execute")
    def test_set_device_mtu(self, execute):
        linux_net._set_device_mtu(dev='fakedev', mtu=1500)
        expected = ['ip', 'link', 'set', 'fakedev', 'mtu', 1500]
        execute.assert_called_with(*expected, check_exit_code=mock.ANY)

    @mock.patch.object(processutils, "execute")
    def test_set_device_invalid_mtu(self, mock_exec):
        linux_net._set_device_mtu(dev='fakedev', mtu=None)
        mock_exec.assert_not_called()

    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=False)
    @mock.patch.object(linux_net, "_set_device_mtu")
    def test_ensure_vlan(self, mock_set_mtu,
                         mock_dev_exists, mock_exec):
        linux_net._ensure_vlan_privileged(123, 'fake-bridge',
                                          mac_address='fake-mac',
                                          mtu=1500)
        self.assertTrue(mock_dev_exists.called)
        calls = [mock.call('ip', 'link', 'add', 'link',
                           'fake-bridge', 'name', 'vlan123', 'type',
                           'vlan', 'id', 123,
                           check_exit_code=[0, 2, 254]),
                 mock.call('ip', 'link', 'set', 'vlan123',
                           'address', 'fake-mac',
                           check_exit_code=[0, 2, 254]),
                 mock.call('ip', 'link', 'set', 'vlan123', 'up',
                           check_exit_code=[0, 2, 254])]
        mock_exec.assert_has_calls(calls)
        mock_set_mtu.assert_called_once_with('vlan123', 1500)

    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=True)
    def test_ensure_bridge_exists(self, mock_dev_exists, mock_exec):
        linux_net.ensure_bridge("br0", None, filtering=False)

        mock_exec.assert_not_called()
        mock_dev_exists.assert_called_once_with("br0")

    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=False)
    def test_ensure_bridge_addbr_exception(self, mock_dev_exists, mock_exec):
        mock_exec.side_effect = ValueError()
        with testtools.ExpectedException(ValueError):
            linux_net.ensure_bridge("br0", None, filtering=False)

    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", side_effect=[False, True])
    def test_ensure_bridge_concurrent_add(self, mock_dev_exists, mock_exec):
        mock_exec.side_effect = [ValueError(), 0, 0, 0]
        linux_net.ensure_bridge("br0", None, filtering=False)

        calls = [mock.call('brctl', 'addbr', 'br0'),
                 mock.call('brctl', 'setfd', 'br0', 0),
                 mock.call('brctl', 'stp', 'br0', "off"),
                 mock.call('ip', 'link', 'set', 'br0', "up")]
        mock_exec.assert_has_calls(calls)
        mock_dev_exists.assert_has_calls([mock.call("br0"), mock.call("br0")])

    @mock.patch.object(linux_net, "_set_device_mtu")
    @mock.patch.object(os.path, "exists", return_value=False)
    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=False)
    def test_ensure_bridge_mtu_not_called(self, mock_dev_exists, mock_exec,
                                          mock_path_exists, mock_set_mtu):
        """This test validates that mtus are updated only if an interface
           is added to the bridge
        """
        linux_net._ensure_bridge_privileged("fake-bridge", None,
                                            None, False, mtu=1500)
        mock_set_mtu.assert_not_called()

    @mock.patch.object(linux_net, "_set_device_mtu")
    @mock.patch.object(os.path, "exists", return_value=False)
    @mock.patch.object(processutils, "execute", return_value=("", ""))
    @mock.patch.object(linux_net, "device_exists", return_value=False)
    def test_ensure_bridge_mtu_order(self, mock_dev_exists, mock_exec,
                                          mock_path_exists, mock_set_mtu):
        """This test validates that when adding an interface
           to a bridge, the interface mtu is updated first
           followed by the bridge. This is required to work around
           https://bugs.launchpad.net/ubuntu/+source/linux/+bug/1399064
        """
        linux_net._ensure_bridge_privileged("fake-bridge", "fake-interface",
                                            None, False, mtu=1500)
        calls = [mock.call('fake-interface', 1500),
                 mock.call('fake-bridge', 1500)]
        mock_set_mtu.assert_has_calls(calls)

    @mock.patch.object(os.path, "exists", return_value=False)
    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=False)
    def test_ensure_bridge_new_ipv4(self, mock_dev_exists, mock_exec,
                                    mock_path_exists):
        linux_net.ensure_bridge("br0", None, filtering=False)

        calls = [mock.call('brctl', 'addbr', 'br0'),
                 mock.call('brctl', 'setfd', 'br0', 0),
                 mock.call('brctl', 'stp', 'br0', "off"),
                 mock.call('ip', 'link', 'set', 'br0', "up")]
        mock_exec.assert_has_calls(calls)
        mock_dev_exists.assert_called_once_with("br0")

    @mock.patch.object(os.path, "exists", return_value=True)
    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=False)
    def test_ensure_bridge_new_ipv6(self, mock_dev_exists, mock_exec,
                                    mock_path_exists):
        linux_net.ensure_bridge("br0", None, filtering=False)

        calls = [mock.call('brctl', 'addbr', 'br0'),
                 mock.call('brctl', 'setfd', 'br0', 0),
                 mock.call('brctl', 'stp', 'br0', "off"),
                 mock.call('tee', '/proc/sys/net/ipv6/conf/br0/disable_ipv6',
                           check_exit_code=[0, 1], process_input='1'),
                 mock.call('ip', 'link', 'set', 'br0', "up")]
        mock_exec.assert_has_calls(calls)
        mock_dev_exists.assert_called_once_with("br0")
