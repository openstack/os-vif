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

import glob
import mock
import os.path
import testtools

from os_vif.internal.ip.api import ip as ip_lib
from six.moves import builtins

from vif_plug_ovs import exception
from vif_plug_ovs import linux_net
from vif_plug_ovs import privsep


class LinuxNetTest(testtools.TestCase):

    def setUp(self):
        super(LinuxNetTest, self).setUp()

        privsep.vif_plug.set_client_mode(False)

    @mock.patch.object(linux_net, "_arp_filtering")
    @mock.patch.object(linux_net, "set_interface_state")
    @mock.patch.object(linux_net, "_disable_ipv6")
    @mock.patch.object(ip_lib, "add")
    @mock.patch.object(ip_lib, "exists", return_value=False)
    def test_ensure_bridge(self, mock_dev_exists, mock_add,
                           mock_disable_ipv6, mock_set_state,
                           mock_arp_filtering):
        linux_net.ensure_bridge("br0")

        mock_dev_exists.assert_called_once_with("br0")
        mock_add.assert_called_once_with("br0", "bridge")
        mock_disable_ipv6.assert_called_once_with("br0")
        mock_set_state.assert_called_once_with("br0", "up")
        mock_arp_filtering.assert_called_once_with("br0")

    @mock.patch.object(linux_net, "_arp_filtering")
    @mock.patch.object(linux_net, "set_interface_state")
    @mock.patch.object(linux_net, "_disable_ipv6")
    @mock.patch.object(ip_lib, "add")
    @mock.patch.object(ip_lib, "exists", return_value=True)
    def test_ensure_bridge_exists(self, mock_dev_exists, mock_add,
                                  mock_disable_ipv6, mock_set_state,
                                  mock_arp_filtering):
        linux_net.ensure_bridge("br0")

        mock_dev_exists.assert_called_once_with("br0")
        mock_add.assert_not_called()
        mock_disable_ipv6.assert_called_once_with("br0")
        mock_set_state.assert_called_once_with("br0", "up")
        mock_arp_filtering.assert_called_once_with("br0")

    @mock.patch('six.moves.builtins.open')
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

    @mock.patch.object(os.path, 'exists', return_value=True)
    @mock.patch.object(builtins, 'open')
    def test__arp_filtering(self, mock_open, *args):
        mock_open.side_effect = mock.mock_open(read_data=mock.Mock())
        linux_net._arp_filtering("br0")

        mock_open.assert_has_calls([
            mock.call('/proc/sys/net/ipv4/conf/br0/arp_ignore', 'w'),
            mock.call('/proc/sys/net/ipv4/conf/br0/arp_announce', 'w')])
        mock_open.side_effect.return_value.write.assert_has_calls([
            mock.call('1'),
            mock.call('2')])

    @mock.patch.object(ip_lib, "delete")
    @mock.patch.object(ip_lib, "exists", return_value=False)
    def test_delete_bridge_none(self, mock_dev_exists, mock_delete):
        linux_net.delete_bridge("br0", "vnet1")

        mock_delete.assert_not_called()
        mock_dev_exists.assert_called_once_with("br0")

    @mock.patch.object(linux_net, "set_interface_state")
    @mock.patch.object(ip_lib, "delete")
    @mock.patch.object(ip_lib, "exists", return_value=True)
    def test_delete_bridge_exists(self, mock_dev_exists, mock_delete,
                                  mock_set_state):
        linux_net.delete_bridge("br0", "vnet1")

        mock_dev_exists.assert_has_calls([mock.call("br0"),
                                          mock.call("vnet1")])
        mock_delete.assert_called_once_with("br0", check_exit_code=[0, 2, 254])
        mock_set_state.assert_called_once_with("vnet1", "down")

    @mock.patch.object(linux_net, "set_interface_state")
    @mock.patch.object(ip_lib, "delete")
    @mock.patch.object(ip_lib, "exists")
    def test_delete_interface_not_present(self, mock_dev_exists, mock_delete,
                                          mock_set_state):
        mock_dev_exists.return_value = next(lambda: (yield True),
                                            (yield False))

        linux_net.delete_bridge("br0", "vnet1")

        mock_dev_exists.assert_has_calls([mock.call("br0"),
                                          mock.call("vnet1")])
        mock_delete.assert_called_once_with("br0", check_exit_code=[0, 2, 254])
        mock_set_state.assert_not_called()

    @mock.patch.object(ip_lib, "set")
    def test_add_bridge_port(self, mock_set):
        linux_net.add_bridge_port("br0", "vnet1")
        mock_set.assert_called_once_with("vnet1", master="br0")

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    def test_is_switchdev_ioerror(self, mock_isfile, mock_open):
        mock_isfile.side_effect = [True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
            [IOError()])
        test_switchdev = linux_net._is_switchdev('pf_ifname')
        self.assertEqual(test_switchdev, False)

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    def test_is_switchdev_empty(self, mock_isfile, mock_open):
        mock_isfile.side_effect = [True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
            [''])
        open_calls = (
            [mock.call('/sys/class/net/pf_ifname/phys_switch_id', 'r'),
             mock.call().readline(),
             mock.call().__exit__(None, None, None)])
        test_switchdev = linux_net._is_switchdev('pf_ifname')
        mock_open.assert_has_calls(open_calls)
        self.assertEqual(test_switchdev, False)

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    def test_is_switchdev_positive(self, mock_isfile, mock_open):
        mock_isfile.side_effect = [True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
            ['pf_sw_id'])
        open_calls = (
            [mock.call('/sys/class/net/pf_ifname/phys_switch_id', 'r'),
             mock.call().readline(),
             mock.call().__exit__(None, None, None)])
        test_switchdev = linux_net._is_switchdev('pf_ifname')
        mock_open.assert_has_calls(open_calls)
        self.assertEqual(test_switchdev, True)

    def test_parse_vf_number(self):
        self.assertEqual(linux_net._parse_vf_number("0"), "0")
        self.assertEqual(linux_net._parse_vf_number("pf13vf42"), "42")
        self.assertEqual(linux_net._parse_vf_number("VF19@PF13"), "19")
        self.assertIsNone(linux_net._parse_vf_number("p7"))
        self.assertIsNone(linux_net._parse_vf_number("pf31"))
        self.assertIsNone(linux_net._parse_vf_number("g4rbl3d"))

    def test_parse_pf_number(self):
        self.assertIsNone(linux_net._parse_pf_number("0"))
        self.assertEqual(linux_net._parse_pf_number("pf13vf42"), "13")
        self.assertEqual(linux_net._parse_pf_number("VF19@PF13"), "13")
        self.assertIsNone(linux_net._parse_pf_number("p7"))
        self.assertEqual(linux_net._parse_pf_number("pf31"), "31")
        self.assertIsNone(linux_net._parse_pf_number("g4rbl3d"))

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    @mock.patch.object(os, 'listdir')
    @mock.patch.object(linux_net, "get_function_by_ifname")
    def test_get_representor_port(self, mock_get_function_by_ifname,
                                  mock_listdir, mock_isfile, mock_open):
        mock_listdir.return_value = [
            'pf_ifname', 'rep_vf_1', 'rep_vf_2'
        ]
        mock_isfile.side_effect = [True, True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
              ['pf_sw_id', 'pf_sw_id', '1', 'pf_sw_id', 'pf0vf2'])
        # PCI IDs mocked:
        # PF0:    0000:0a:00.0
        # PF0VF1: 0000:0a:02.1    PF0VF2: 0000:0a:02.2
        mock_get_function_by_ifname.side_effect = (
            [("0000:0a:00.0", True),
             ("0000:0a:02.1", False),
             ("0000:0a:02.2", False), ("0000:0a:00.0", True)])
        open_calls = (
            [mock.call('/sys/class/net/pf_ifname/phys_switch_id', 'r'),
             mock.call().readline(),
             mock.call().__exit__(None, None, None),
             mock.call('/sys/class/net/rep_vf_1/phys_switch_id', 'r'),
             mock.call().readline(),
             mock.call().__exit__(None, None, None),
             mock.call('/sys/class/net/rep_vf_1/phys_port_name', 'r'),
             mock.call().readline(),
             mock.call().__exit__(None, None, None),
             mock.call('/sys/class/net/rep_vf_2/phys_switch_id', 'r'),
             mock.call().readline(),
             mock.call().__exit__(None, None, None),
             mock.call('/sys/class/net/rep_vf_2/phys_port_name', 'r'),
             mock.call().readline(),
             mock.call().__exit__(None, None, None)])
        ifname = linux_net.get_representor_port('pf_ifname', '2')
        mock_open.assert_has_calls(open_calls)
        self.assertEqual('rep_vf_2', ifname)

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    @mock.patch.object(os, 'listdir')
    @mock.patch.object(linux_net, "get_function_by_ifname")
    def test_get_representor_port_2_pfs(
            self, mock_get_function_by_ifname, mock_listdir, mock_isfile,
            mock_open):
        mock_listdir.return_value = [
            'pf_ifname1', 'pf_ifname2', 'rep_pf1_vf_1', 'rep_pf1_vf_2',
            'rep_pf2_vf_1', 'rep_pf2_vf_2',
        ]
        mock_isfile.side_effect = [True, True, True, True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
            ['pf_sw_id',
             'pf_sw_id', 'VF1@PF1', 'pf_sw_id', 'vf2@pf1',
             'pf_sw_id', 'pf2vf1', 'pf_sw_id', 'pf2vf2'])
        # PCI IDs mocked:
        # PF1:    0000:0a:00.1    PF2:    0000:0a:00.2
        # PF1VF1: 0000:0a:02.1    PF1VF2: 0000:0a:02.2
        # PF2VF1: 0000:0a:04.1    PF2VF2: 0000:0a:04.2
        mock_get_function_by_ifname.side_effect = (
            [("0000:0a:00.1", True), ("0000:0a:00.2", True),
             ("0000:0a:02.1", False), ("0000:0a:00.2", True),
             ("0000:0a:02.2", False), ("0000:0a:00.2", True),
             ("0000:0a:04.1", False), ("0000:0a:00.2", True),
             ("0000:0a:04.2", False), ("0000:0a:00.2", True)])
        ifname = linux_net.get_representor_port('pf_ifname2', '2')
        self.assertEqual('rep_pf2_vf_2', ifname)

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    @mock.patch.object(os, 'listdir')
    @mock.patch.object(linux_net, "get_function_by_ifname")
    def test_get_representor_port_not_found(
            self, mock_get_function_by_ifname, mock_listdir, mock_isfile,
            mock_open):
        mock_listdir.return_value = [
            'pf_ifname', 'rep_vf_1', 'rep_vf_2'
        ]
        mock_isfile.side_effect = [True, True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
            ['pf_sw_id', 'pf_sw_id', '1', 'pf_sw_id', '2'])
        # PCI IDs mocked:
        # PF0:    0000:0a:00.0
        # PF0VF1: 0000:0a:02.1    PF0VF2: 0000:0a:02.2
        mock_get_function_by_ifname.side_effect = (
            [("0000:0a:00.0", True),
             ("0000:0a:02.1", False),
             ("0000:0a:02.2", False)])
        self.assertRaises(
            exception.RepresentorNotFound,
            linux_net.get_representor_port,
            'pf_ifname', '3'),

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    @mock.patch.object(os, 'listdir')
    @mock.patch.object(linux_net, "get_function_by_ifname")
    def test_get_representor_port_exception_io_error(
            self, mock_get_function_by_ifname, mock_listdir, mock_isfile,
            mock_open):
        mock_listdir.return_value = [
            'pf_ifname', 'rep_vf_1', 'rep_vf_2'
        ]
        mock_isfile.side_effect = [True, True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
            ['pf_sw_id', 'pf_sw_id', IOError(), 'pf_sw_id', '2'])
        # PCI IDs mocked:
        # PF0:    0000:0a:00.0
        # PF0VF1: 0000:0a:02.1    PF0VF2: 0000:0a:02.2
        mock_get_function_by_ifname.side_effect = (
            [("0000:0a:00.0", True),
             ("0000:0a:02.1", False),
             ("0000:0a:02.2", False), ("0000:0a:00.0", True)])
        self.assertRaises(
            exception.RepresentorNotFound,
            linux_net.get_representor_port,
            'pf_ifname', '3')

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    @mock.patch.object(os, 'listdir')
    @mock.patch.object(linux_net, "get_function_by_ifname")
    def test_get_representor_port_exception_value_error(
            self, mock_get_function_by_ifname, mock_listdir, mock_isfile,
            mock_open):
        mock_listdir.return_value = [
            'pf_ifname', 'rep_vf_1', 'rep_vf_2'
        ]
        mock_isfile.side_effect = [True, True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
            ['pf_sw_id', 'pf_sw_id', '1', 'pf_sw_id', 'a'])
        # PCI IDs mocked:
        # PF0:    0000:0a:00.0
        # PF0VF1: 0000:0a:02.1    PF0VF2: 0000:0a:02.2
        mock_get_function_by_ifname.side_effect = (
            [("0000:0a:00.0", True),
             ("0000:0a:02.1", False),
             ("0000:0a:02.2", False)])
        self.assertRaises(
            exception.RepresentorNotFound,
            linux_net.get_representor_port,
            'pf_ifname', '3')

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    @mock.patch.object(os, 'listdir')
    def test_physical_function_inferface_name(
            self, mock_listdir, mock_isfile, mock_open):
        mock_listdir.return_value = ['foo', 'bar']
        mock_isfile.side_effect = [True, True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
            ['', 'valid_switch'])
        ifname = linux_net.get_ifname_by_pci_address(
            '0000:00:00.1', pf_interface=True, switchdev=False)
        self.assertEqual(ifname, 'foo')

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os.path, 'isfile')
    @mock.patch.object(os, 'listdir')
    def test_physical_function_inferface_name_with_switchdev(
            self, mock_listdir, mock_isfile, mock_open):
        mock_listdir.return_value = ['foo', 'bar']
        mock_isfile.side_effect = [True, True]
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.side_effect = (
            ['', 'valid_switch'])
        ifname = linux_net.get_ifname_by_pci_address(
            '0000:00:00.1', pf_interface=True, switchdev=True)
        self.assertEqual(ifname, 'bar')

    @mock.patch.object(os, 'listdir')
    def test_get_ifname_by_pci_address_exception(self, mock_listdir):
        mock_listdir.side_effect = OSError('No such file or directory')
        self.assertRaises(
            exception.PciDeviceNotFoundById,
            linux_net.get_ifname_by_pci_address,
            '0000:00:00.1'
        )

    @mock.patch.object(os, 'readlink')
    @mock.patch.object(glob, 'iglob')
    def test_vf_number_found(self, mock_iglob, mock_readlink):
        mock_iglob.return_value = [
            '/sys/bus/pci/devices/0000:00:00.1/physfn/virtfn3',
        ]
        mock_readlink.return_value = '../../0000:00:00.1'
        vf_num = linux_net.get_vf_num_by_pci_address('0000:00:00.1')
        self.assertEqual(vf_num, '3')

    @mock.patch.object(os, 'readlink')
    @mock.patch.object(glob, 'iglob')
    def test_vf_number_not_found(self, mock_iglob, mock_readlink):
        mock_iglob.return_value = [
            '/sys/bus/pci/devices/0000:00:00.1/physfn/virtfn3',
        ]
        mock_readlink.return_value = '../../0000:00:00.2'
        self.assertRaises(
            exception.PciDeviceNotFoundById,
            linux_net.get_vf_num_by_pci_address,
            '0000:00:00.1'
        )

    @mock.patch.object(os, 'readlink')
    @mock.patch.object(glob, 'iglob')
    def test_get_vf_num_by_pci_address_exception(
            self, mock_iglob, mock_readlink):
        mock_iglob.return_value = [
            '/sys/bus/pci/devices/0000:00:00.1/physfn/virtfn3',
        ]
        mock_readlink.side_effect = OSError('No such file or directory')
        self.assertRaises(
            exception.PciDeviceNotFoundById,
            linux_net.get_vf_num_by_pci_address,
            '0000:00:00.1'
        )
