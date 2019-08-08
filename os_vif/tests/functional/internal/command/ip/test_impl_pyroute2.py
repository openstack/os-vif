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

import os
import re

from oslo_concurrency import processutils
from oslo_utils import excutils

from os_vif.internal.ip.api import ip as ip_lib
from os_vif.tests.functional import base
from os_vif.tests.functional import privsep


@privsep.os_vif_pctxt.entrypoint
def _execute_command(*args):
    return processutils.execute(*args)


class ShellIpCommands(object):

    def add_device(self, device, dev_type, peer=None, link=None,
                   vlan_id=None):
        if 'vlan' == dev_type:
            _execute_command('ip', 'link', 'add', 'link', link,
                             'name', device, 'type', dev_type, 'vlan', 'id',
                             vlan_id)
        elif 'veth' == dev_type:
            _execute_command('ip', 'link', 'add', device, 'type', dev_type,
                             'peer', 'name', peer)
        elif 'dummy' == dev_type:
            _execute_command('ip', 'link', 'add', device, 'type', dev_type)

    def del_device(self, device):
        if self.exist_device(device):
            _execute_command('ip', 'link', 'del', device)

    def set_status_up(self, device):
        _execute_command('ip', 'link', 'set', device, 'up')

    def set_status_down(self, device):
        _execute_command('ip', 'link', 'set', device, 'down')

    def set_device_mtu(self, device, mtu):
        _execute_command('ip', 'link', 'set', device, 'mtu', mtu)

    def show_device(self, device):
        val, err = _execute_command('ip', 'link', 'show', device)
        return val.splitlines()

    def exist_device(self, device):
        try:
            _execute_command('ip', 'link', 'show', device)
            return True
        except processutils.ProcessExecutionError as e:
            with excutils.save_and_reraise_exception() as saved_exception:
                if e.exit_code == 1:
                    saved_exception.reraise = False
                    return False

    def show_state(self, device):
        regex = re.compile(r".*state (?P<state>\w+)")
        match = regex.match(self.show_device(device)[0])
        if match is None:
            return
        return match.group('state')

    def show_promisc(self, device):
        regex = re.compile(r".*(PROMISC)")
        match = regex.match(self.show_device(device)[0])
        return True if match else False

    def show_mac(self, device):
        exp = r".*link/ether (?P<mac>([0-9A-Fa-f]{2}[:]){5}[0-9A-Fa-f]{2})"
        regex = re.compile(exp)
        match = regex.match(self.show_device(device)[1])
        if match is None:
            return
        return match.group('mac')

    def show_mtu(self, device):
        regex = re.compile(r".*mtu (?P<mtu>\d+)")
        match = regex.match(self.show_device(device)[0])
        if match is None:
            return
        return int(match.group('mtu'))


@privsep.os_vif_pctxt.entrypoint
def _ip_cmd_set(*args, **kwargs):
    ip_lib.set(*args, **kwargs)


@privsep.os_vif_pctxt.entrypoint
def _ip_cmd_add(*args, **kwargs):
    ip_lib.add(*args, **kwargs)


@privsep.os_vif_pctxt.entrypoint
def _ip_cmd_delete(*args, **kwargs):
    ip_lib.delete(*args, **kwargs)


@privsep.os_vif_pctxt.entrypoint
def _ip_cmd_exists(*args, **kwargs):
    return ip_lib.exists(*args, **kwargs)


class TestIpCommand(ShellIpCommands, base.BaseFunctionalTestCase):

    def setUp(self):
        super(TestIpCommand, self).setUp()

    def test_set_state(self):
        device1 = "test_dev_1"
        device2 = "test_dev_2"
        self.addCleanup(self.del_device, device1)
        self.add_device(device1, 'veth', peer=device2)
        _ip_cmd_set(device1, state='up')
        _ip_cmd_set(device2, state='up')
        self.assertEqual('UP', self.show_state(device1))
        self.assertEqual('UP', self.show_state(device2))
        _ip_cmd_set(device1, state='down')
        _ip_cmd_set(device2, state='down')
        self.assertEqual('DOWN', self.show_state(device1))
        self.assertEqual('DOWN', self.show_state(device2))

    def test_set_mtu(self):
        device = "test_dev_3"
        self.addCleanup(self.del_device, device)
        self.add_device(device, 'dummy')
        _ip_cmd_set(device, mtu=1200)
        self.assertEqual(1200, self.show_mtu(device))
        _ip_cmd_set(device, mtu=900)
        self.assertEqual(900, self.show_mtu(device))

    def test_set_address(self):
        device = "test_dev_4"
        address1 = "36:a7:e4:f9:01:01"
        address2 = "36:a7:e4:f9:01:01"
        self.addCleanup(self.del_device, device)
        self.add_device(device, 'dummy')
        _ip_cmd_set(device, address=address1)
        self.assertEqual(address1, self.show_mac(device))
        _ip_cmd_set(device, address=address2)
        self.assertEqual(address2, self.show_mac(device))

    def test_set_promisc(self):
        device = "test_dev_5"
        self.addCleanup(self.del_device, device)
        self.add_device(device, 'dummy')
        _ip_cmd_set(device, promisc=True)
        self.assertTrue(self.show_promisc(device))
        _ip_cmd_set(device, promisc=False)
        self.assertFalse(self.show_promisc(device))

    def test_add_vlan(self):
        device = "test_dev_6"
        link = "test_devlink"
        self.addCleanup(self.del_device, device)
        self.addCleanup(self.del_device, link)
        self.add_device(link, 'dummy')
        _ip_cmd_add(device, 'vlan', link=link, vlan_id=100)
        self.assertTrue(self.exist_device(device))

    def test_add_veth(self):
        device = "test_dev_7"
        peer = "test_devpeer"
        self.addCleanup(self.del_device, device)
        _ip_cmd_add(device, 'veth', peer=peer)
        self.assertTrue(self.exist_device(device))
        self.assertTrue(self.exist_device(peer))

    def test_delete(self):
        device = "test_dev_8"
        self.addCleanup(self.del_device, device)
        self.add_device(device, 'dummy')
        self.assertTrue(self.exist_device(device))
        _ip_cmd_delete(device)
        self.assertFalse(self.exist_device(device))

    def test_iproute_object_closes_correctly(self):
        # NOTE(ralonsoh): check https://bugs.launchpad.net/os-vif/+bug/1807949
        device = "test_dev_9"
        link = "test_devlink_2"
        self.add_device(link, 'dummy')
        self.addCleanup(self.del_device, device)
        self.addCleanup(self.del_device, link)
        for _ in range(300):
            _ip_cmd_add(device, 'vlan', link=link, vlan_id=100)
            _ip_cmd_delete(device)

    def test_exists(self):
        device = "test_dev_10"
        self.addCleanup(self.del_device, device)
        self.add_device(device, 'dummy')
        self.assertTrue(_ip_cmd_exists(device))
        self.del_device(device)
        self.assertFalse(_ip_cmd_exists(device))

    def test_add_bridge(self):
        device = "test_dev_11"
        self.addCleanup(self.del_device, device)
        _ip_cmd_add(device, 'bridge')
        self.assertTrue(self.exist_device(device))
        base_path = "/sys/class/net/test_dev_11/bridge/%s"
        with open(base_path % "forward_delay", "r") as f:
            self.assertEqual("0", f.readline().rstrip('\n'))
        with open(base_path % "stp_state", "r") as f:
            self.assertEqual("0", f.readline().rstrip('\n'))
        with open(base_path % "multicast_snooping", "r") as f:
            self.assertEqual("0", f.readline().rstrip('\n'))
        with open(base_path % "ageing_time", "r") as f:
            value = int(f.readline().rstrip('\n'))
            # NOTE(sean-k-mooney): IEEE 8021-Q recommends that the default
            # ageing should be 300 and the linux kernel defaults to 300
            # via an unconditional define. As such we expect this to be
            # 300 however since services like network-manager could change
            # the default on bridge creation we check that if it is not 300
            # then the value should not be 0.
            self.assertTrue(300 == value or value != 0)

    def test_add_bridge_with_mac_ageing_0(self):
        device = "test_dev_12"
        self.addCleanup(self.del_device, device)
        _ip_cmd_add(device, 'bridge', ageing=0)
        self.assertTrue(self.exist_device(device))
        base_path = "/sys/class/net/test_dev_12/bridge/%s"
        with open(base_path % "forward_delay", "r") as f:
            self.assertEqual("0", f.readline().rstrip('\n'))
        with open(base_path % "stp_state", "r") as f:
            self.assertEqual("0", f.readline().rstrip('\n'))
        with open(base_path % "ageing_time", "r") as f:
            self.assertEqual("0", f.readline().rstrip('\n'))
        with open(base_path % "multicast_snooping", "r") as f:
            self.assertEqual("0", f.readline().rstrip('\n'))

    def test_add_port_to_bridge(self):
        device = "test_dev_13"
        bridge = "test_dev_14"
        self.addCleanup(self.del_device, device)
        self.addCleanup(self.del_device, bridge)
        self.add_device(device, 'dummy')
        _ip_cmd_add(bridge, 'bridge')
        self.assertTrue(self.exist_device(device))
        self.assertTrue(self.exist_device(bridge))
        _ip_cmd_set(device, master=bridge)
        path = "/sys/class/net/{}/brif/{}".format(bridge, device)
        self.assertTrue(os.path.exists(path))
