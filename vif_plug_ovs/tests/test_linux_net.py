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

import contextlib
import mock
import os.path
import six
import testtools

from oslo_concurrency import processutils

from vif_plug_ovs import linux_net
from vif_plug_ovs import privsep


if six.PY2:
    nested = contextlib.nested
else:
    @contextlib.contextmanager
    def nested(*contexts):
        with contextlib.ExitStack() as stack:
            yield [stack.enter_context(c) for c in contexts]


class LinuxNetTest(testtools.TestCase):

    def setUp(self):
        super(LinuxNetTest, self).setUp()

        privsep.vif_plug.set_client_mode(False)

    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=True)
    def test_ensure_bridge_exists(self, mock_dev_exists, mock_execute):
        linux_net.ensure_bridge("br0")

        self.assertEqual(mock_execute.mock_calls, [])
        self.assertEqual(mock_dev_exists.mock_calls, [
            mock.call("br0")
        ])

    @mock.patch.object(os.path, "exists", return_value=False)
    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=False)
    def test_ensure_bridge_new_ipv4(self, mock_dev_exists, mock_execute,
                                    mock_path_exists):
        linux_net.ensure_bridge("br0")

        self.assertEqual(mock_execute.mock_calls, [
            mock.call('brctl', 'addbr', 'br0'),
            mock.call('brctl', 'setfd', 'br0', 0),
            mock.call('brctl', 'stp', 'br0', "off"),
            mock.call('tee', '/sys/class/net/br0/bridge/multicast_snooping',
                      check_exit_code=[0, 1], process_input='0'),
        ])
        self.assertEqual(mock_dev_exists.mock_calls, [
            mock.call("br0")
        ])

    @mock.patch.object(os.path, "exists", return_value=True)
    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=False)
    def test_ensure_bridge_new_ipv6(self, mock_dev_exists, mock_execute,
                                    mock_path_exists):
        linux_net.ensure_bridge("br0")

        self.assertEqual(mock_execute.mock_calls, [
            mock.call('brctl', 'addbr', 'br0'),
            mock.call('brctl', 'setfd', 'br0', 0),
            mock.call('brctl', 'stp', 'br0', "off"),
            mock.call('tee', '/sys/class/net/br0/bridge/multicast_snooping',
                      check_exit_code=[0, 1], process_input='0'),
            mock.call('tee', '/proc/sys/net/ipv6/conf/br0/disable_ipv6',
                      check_exit_code=[0, 1], process_input='1'),
        ])
        self.assertEqual(mock_dev_exists.mock_calls, [
            mock.call("br0")
        ])

    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=False)
    def test_delete_bridge_none(self, mock_dev_exists, mock_execute):
        linux_net.delete_bridge("br0", "vnet1")

        self.assertEqual(mock_execute.mock_calls, [])
        self.assertEqual(mock_dev_exists.mock_calls, [
            mock.call("br0")
        ])

    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=True)
    def test_delete_bridge_exists(self, mock_dev_exists, mock_execute):
        linux_net.delete_bridge("br0", "vnet1")

        self.assertEqual(mock_execute.mock_calls, [
            mock.call('brctl', 'delif', 'br0', 'vnet1'),
            mock.call('ip', 'link', 'set', 'br0', 'down'),
            mock.call('brctl', 'delbr', 'br0'),
        ])
        self.assertEqual(mock_dev_exists.mock_calls, [
            mock.call("br0")
        ])

    @mock.patch.object(processutils, "execute")
    def test_add_bridge_port(self, mock_execute):
        linux_net.add_bridge_port("br0", "vnet1")

        self.assertEqual(mock_execute.mock_calls, [
            mock.call('ip', 'link', 'set', 'br0', 'up'),
            mock.call('brctl', 'addif', 'br0', 'vnet1'),
        ])
