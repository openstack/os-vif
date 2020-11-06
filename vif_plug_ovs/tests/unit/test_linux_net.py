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
import os.path

from unittest import mock

import testtools

from os_vif.internal.ip.api import ip as ip_lib

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
        mock_add.assert_called_once_with("br0", "bridge", ageing=0)
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

    @mock.patch.object(os.path, 'exists', return_value=True)
    @mock.patch('builtins.open')
    def test__arp_filtering(self, mock_open, *args):
        mock_open.side_effect = mock.mock_open()
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

    @mock.patch.object(linux_net, '_get_phys_switch_id')
    def test_is_switchdev_ioerror(self, mock__get_phys_switch_id):
        mock__get_phys_switch_id.side_effect = ([IOError()])
        test_switchdev = linux_net._is_switchdev('pf_ifname')
        self.assertEqual(test_switchdev, False)

    @mock.patch.object(linux_net, '_get_phys_switch_id')
    def test_is_switchdev_empty(self, mock__get_phys_switch_id):
        mock__get_phys_switch_id.return_value = ''
        test_switchdev = linux_net._is_switchdev('pf_ifname')
        self.assertEqual(test_switchdev, False)

    @mock.patch.object(linux_net, '_get_phys_switch_id')
    def test_is_switchdev_positive(self, mock__get_phys_switch_id):
        mock__get_phys_switch_id.return_value = 'pf_sw_id'
        test_switchdev = linux_net._is_switchdev('pf_ifname')
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

    @mock.patch.object(os, 'listdir')
    @mock.patch.object(linux_net, "_get_pf_func")
    @mock.patch.object(linux_net, "_get_phys_port_name")
    @mock.patch.object(linux_net, '_get_phys_switch_id')
    def test_get_representor_port(self, mock__get_phys_switch_id,
                                  mock__get_phys_port_name,
                                  mock__get_pf_func,
                                  mock_listdir):
        mock_listdir.return_value = [
            'pf_ifname', 'rep_vf_1', 'rep_vf_2'
        ]
        mock__get_phys_switch_id.return_value = 'pf_sw_id'
        mock__get_pf_func.return_value = "0"
        mock__get_phys_port_name.side_effect = (['1', "pf0vf1", "pf0vf2"])
        ifname = linux_net.get_representor_port('pf_ifname', '2')
        self.assertEqual('rep_vf_2', ifname)

    @mock.patch.object(os, 'listdir')
    @mock.patch.object(linux_net, "_get_pf_func")
    @mock.patch.object(linux_net, "_get_phys_port_name")
    @mock.patch.object(linux_net, "_get_phys_switch_id")
    def test_get_representor_port_2_pfs(
            self, mock__get_phys_switch_id, mock__get_phys_port_name,
            mock__get_pf_func, mock_listdir):
        mock_listdir.return_value = [
            'pf_ifname1', 'pf_ifname2', 'rep_pf1_vf_1', 'rep_pf1_vf_2',
            'rep_pf2_vf_1', 'rep_pf2_vf_2',
        ]
        mock__get_phys_switch_id.return_value = 'pf_sw_id'
        mock__get_pf_func.return_value = "2"
        mock__get_phys_port_name.side_effect = (
            ["p1", "p2", "VF1@PF1", "pf2vf1", "vf2@pf1", "pf2vf2"])
        ifname = linux_net.get_representor_port('pf_ifname2', '2')
        self.assertEqual('rep_pf2_vf_2', ifname)

    @mock.patch.object(os, 'listdir')
    @mock.patch.object(linux_net, "_get_pf_func")
    @mock.patch.object(linux_net, "_get_phys_switch_id")
    @mock.patch.object(linux_net, "_get_phys_port_name")
    def test_get_representor_port_not_found(
            self, mock__get_phys_port_name, mock__get_phys_switch_id,
            mock__get_pf_func, mock_listdir):
        mock_listdir.return_value = [
            'pf_ifname', 'rep_vf_1', 'rep_vf_2'
        ]
        mock__get_phys_switch_id.return_value = 'pf_sw_id'
        mock__get_pf_func.return_value = "0"
        mock__get_phys_port_name.side_effect = (
            ["p0", "1", "2"])
        self.assertRaises(
            exception.RepresentorNotFound,
            linux_net.get_representor_port,
            'pf_ifname', '3'),

    @mock.patch.object(os, 'listdir')
    @mock.patch.object(linux_net, "_get_pf_func")
    @mock.patch.object(linux_net, "_get_phys_port_name")
    @mock.patch.object(linux_net, "_get_phys_switch_id")
    def test_get_representor_port_exception_io_error(
            self, mock__get_phys_switch_id, mock__get_phys_port_name,
            mock__get_pf_func, mock_listdir):
        mock_listdir.return_value = [
            'pf_ifname', 'rep_vf_1', 'rep_vf_2'
        ]
        mock__get_phys_switch_id.side_effect = (
            ['pf_sw_id', 'pf_sw_id', IOError(), 'pf_sw_id', '2'])
        mock__get_pf_func.return_value = "0"
        mock__get_phys_port_name.side_effect = (
            ["p0", "pf0vf0", "pf0vf1"])
        self.assertRaises(
            exception.RepresentorNotFound,
            linux_net.get_representor_port,
            'pf_ifname', '3')

    @mock.patch.object(os, 'listdir')
    @mock.patch.object(linux_net, "_get_pf_func")
    @mock.patch.object(linux_net, "_get_phys_port_name")
    @mock.patch.object(linux_net, "_get_phys_switch_id")
    def test_get_representor_port_exception_value_error(
            self, mock__get_phys_switch_id, mock__get_phys_port_name,
            mock__get_pf_func, mock_listdir):
        mock_listdir.return_value = [
            'pf_ifname', 'rep_vf_1', 'rep_vf_2'
        ]
        mock__get_phys_switch_id.return_value = 'pf_sw_id'
        mock__get_phys_port_name.side_effect = (['p0', '1', 'a'])
        mock__get_pf_func.return_value = "0"
        self.assertRaises(
            exception.RepresentorNotFound,
            linux_net.get_representor_port,
            'pf_ifname', '3')

    @mock.patch.object(os, 'listdir')
    @mock.patch.object(linux_net, '_get_phys_switch_id')
    @mock.patch.object(linux_net, "_get_phys_port_name")
    def test_physical_function_interface_name(
            self, mock__get_phys_port_name, mock__get_phys_switch_id,
            mock_listdir):
        mock_listdir.return_value = ['foo', 'bar']
        mock__get_phys_switch_id.side_effect = (
            ['', 'valid_switch'])
        mock__get_phys_port_name.side_effect = (["p1"])
        ifname = linux_net.get_ifname_by_pci_address(
            '0000:00:00.1', pf_interface=True, switchdev=False)
        self.assertEqual(ifname, 'foo')

    @mock.patch.object(os, 'listdir')
    @mock.patch.object(linux_net, "_get_phys_switch_id")
    @mock.patch.object(linux_net, "_get_phys_port_name")
    def test_physical_function_interface_name_with_switchdev(
            self, mock__get_phys_port_name, mock__get_phys_switch_id,
            mock_listdir):
        mock_listdir.return_value = ['foo', 'bar']
        mock__get_phys_switch_id.side_effect = (
            ['', 'valid_switch'])
        mock__get_phys_port_name.side_effect = (["p1s0"])
        ifname = linux_net.get_ifname_by_pci_address(
            '0000:00:00.1', pf_interface=True, switchdev=True)
        self.assertEqual(ifname, 'bar')

    @mock.patch.object(os, 'listdir')
    @mock.patch.object(linux_net, "_get_phys_switch_id")
    @mock.patch.object(linux_net, "_get_phys_port_name")
    def test_physical_function_interface_name_with_representors(
            self, mock__get_phys_port_name, mock__get_phys_switch_id,
            mock_listdir):
        # Get the PF that matches the phys_port_name regex
        mock_listdir.return_value = ['enp2s0f0_0', 'enp2s0f0_1', 'enp2s0f0']
        mock__get_phys_switch_id.side_effect = (
            ['valid_switch', 'valid_switch', 'valid_switch'])
        mock__get_phys_port_name.side_effect = (["pf0vf0", "pf0vf1", "p0"])
        ifname = linux_net.get_ifname_by_pci_address(
            '0000:00:00.1', pf_interface=True, switchdev=True)
        self.assertEqual(ifname, 'enp2s0f0')

    @mock.patch.object(os, 'listdir')
    @mock.patch.object(linux_net, "_get_phys_switch_id")
    @mock.patch.object(linux_net, "_get_phys_port_name")
    def test_physical_function_interface_name_with_fallback_To_first_netdev(
            self, mock__get_phys_port_name, mock__get_phys_switch_id,
            mock_listdir):
        # Try with switchdev mode to get PF but fail because there is no match
        # for the phys_port_name then fallback to first interface found
        mock_listdir.return_value = ['enp2s0f0_0', 'enp2s0f0_1', 'enp2s0f0']
        mock__get_phys_switch_id.side_effect = (['valid_switch',
                                                 'valid_switch',
                                                 'valid_switch'])
        mock__get_phys_port_name.side_effect = (["pf0vf0", "pf0vf1", "pf0vf2"])
        ifname = linux_net.get_ifname_by_pci_address(
            '0000:00:00.1', pf_interface=True, switchdev=True)
        self.assertEqual(ifname, 'enp2s0f0_0')

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

    @mock.patch('builtins.open')
    @mock.patch.object(os.path, 'isfile')
    def test__get_phys_port_name(self, mock_isfile, mock_open):
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.return_value = 'pf0vf0'
        mock_isfile.return_value = True
        phys_port_name = linux_net._get_phys_port_name("vf_ifname")
        self.assertEqual(phys_port_name, 'pf0vf0')

    @mock.patch.object(os.path, 'isfile')
    def test__get_phys_port_name_not_found(self, mock_isfile):
        mock_isfile.return_value = False
        phys_port_name = linux_net._get_phys_port_name("vf_ifname")
        self.assertIsNone(phys_port_name)

    @mock.patch('builtins.open')
    @mock.patch.object(os.path, 'isfile')
    def test__get_phys_switch_id(self, mock_isfile, mock_open):
        mock_open.return_value.__enter__ = lambda s: s
        readline_mock = mock_open.return_value.readline
        readline_mock.return_value = '66e40000039b0398'
        mock_isfile.return_value = True
        phys_port_name = linux_net._get_phys_switch_id("ifname")
        self.assertEqual(phys_port_name, '66e40000039b0398')

    @mock.patch.object(os.path, 'isfile')
    def test__get_phys_switch_id_not_found(self, mock_isfile):
        mock_isfile.return_value = False
        phys_port_name = linux_net._get_phys_switch_id("ifname")
        self.assertIsNone(phys_port_name)
