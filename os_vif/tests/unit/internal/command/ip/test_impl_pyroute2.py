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
from pyroute2 import iproute
from pyroute2.netlink import exceptions as ipexc
from pyroute2.netlink.rtnl import ifinfmsg

from os_vif import exception
from os_vif.internal.command.ip import impl_pyroute2
from os_vif.tests.unit import base


class TestIpCommand(base.TestCase):

    ERROR_CODE = 40
    OTHER_ERROR_CODE = 50
    DEVICE = 'device'
    MTU = 1500
    MAC = 'ca:fe:ca:fe:ca:fe'
    UP = 'up'
    TYPE_VETH = 'veth'
    TYPE_VLAN = 'vlan'
    LINK = 'device2'
    VLAN_ID = 14

    def setUp(self):
        super(TestIpCommand, self).setUp()
        self.ip = impl_pyroute2.PyRoute2()
        self.ip_link_p = mock.patch.object(iproute.IPRoute, 'link')
        self.ip_link = self.ip_link_p.start()

    def test_set(self):
        with mock.patch.object(iproute.IPRoute, 'link_lookup',
                               return_value=[1]) as mock_link_lookup:
            self.ip_link.return_value = [{'flags': 0x4000}]
            self.ip.set(self.DEVICE, state=self.UP, mtu=self.MTU,
                        address=self.MAC, promisc=True)
            mock_link_lookup.assert_called_once_with(ifname=self.DEVICE)
            args = {'state': self.UP,
                    'mtu': self.MTU,
                    'address': self.MAC,
                    'flags': 0x4000 | ifinfmsg.IFF_PROMISC}
            calls = [mock.call('get', index=1),
                     mock.call('set', index=1, **args)]
            self.ip_link.assert_has_calls(calls)

    def test_set_exit_code(self):
        with mock.patch.object(iproute.IPRoute, 'link_lookup',
                               return_value=[1]) as mock_link_lookup:
            self.ip_link.side_effect = ipexc.NetlinkError(self.ERROR_CODE,
                                                          msg="Error message")

            self.ip.set(self.DEVICE, check_exit_code=[self.ERROR_CODE])
            mock_link_lookup.assert_called_once_with(ifname=self.DEVICE)
            self.ip_link.assert_called_once_with('set', index=1)

            self.assertRaises(ipexc.NetlinkError, self.ip.set, self.DEVICE,
                              check_exit_code=[self.OTHER_ERROR_CODE])

    def test_set_no_interface_found(self):
        with mock.patch.object(iproute.IPRoute, 'link_lookup',
                               return_value=[]) as mock_link_lookup:
            self.assertRaises(exception.NetworkInterfaceNotFound, self.ip.set,
                              self.DEVICE)
            mock_link_lookup.assert_called_once_with(ifname=self.DEVICE)
            self.ip_link.assert_not_called()

    def test_add_veth(self):
        self.ip.add(self.DEVICE, self.TYPE_VETH, peer='peer')
        self.ip_link.assert_called_once_with(
            'add', ifname=self.DEVICE, kind=self.TYPE_VETH, peer='peer')

    def test_add_vlan(self):
        with mock.patch.object(iproute.IPRoute, 'link_lookup',
                               return_value=[1]) as mock_link_lookup:
            self.ip.add(self.DEVICE, self.TYPE_VLAN, link=self.LINK,
                        vlan_id=self.VLAN_ID)
            mock_link_lookup.assert_called_once_with(ifname=self.LINK)
            args = {'ifname': self.DEVICE,
                    'kind': self.TYPE_VLAN,
                    'vlan_id': self.VLAN_ID,
                    'link': 1}
            self.ip_link.assert_called_once_with('add', **args)

    def test_add_vlan_no_interface_found(self):
        with mock.patch.object(iproute.IPRoute, 'link_lookup',
                               return_value=[]) as mock_link_lookup:
            self.assertRaises(exception.NetworkInterfaceNotFound, self.ip.add,
                              self.DEVICE, self.TYPE_VLAN, link=self.LINK)
            mock_link_lookup.assert_called_once_with(ifname=self.LINK)
            self.ip_link.assert_not_called()

    def test_add_other_type(self):
        self.assertRaises(exception.NetworkInterfaceTypeNotDefined,
                          self.ip.add, self.DEVICE, 'type_not_defined')

    def test_add_exit_code(self):
        self.ip_link.side_effect = ipexc.NetlinkError(self.ERROR_CODE,
                                                      msg="Error message")

        self.ip.add(self.DEVICE, self.TYPE_VETH, peer='peer',
                    check_exit_code=[self.ERROR_CODE])
        self.ip_link.assert_called_once_with(
            'add', ifname=self.DEVICE, kind=self.TYPE_VETH, peer='peer')

        self.assertRaises(ipexc.NetlinkError, self.ip.add, self.DEVICE,
                          self.TYPE_VLAN, peer='peer',
                          check_exit_code=[self.OTHER_ERROR_CODE])

    def test_delete(self):
        with mock.patch.object(iproute.IPRoute, 'link_lookup',
                               return_value=[1]) as mock_link_lookup:
            self.ip.delete(self.DEVICE)
            mock_link_lookup.assert_called_once_with(ifname=self.DEVICE)
            self.ip_link.assert_called_once_with('del', index=1)

    def test_delete_no_interface_found(self):
        with mock.patch.object(iproute.IPRoute, 'link_lookup',
                               return_value=[]) as mock_link_lookup:
            self.assertRaises(exception.NetworkInterfaceNotFound,
                              self.ip.delete, self.DEVICE)
            mock_link_lookup.assert_called_once_with(ifname=self.DEVICE)

    def test_delete_exit_code(self):
        with mock.patch.object(iproute.IPRoute, 'link_lookup',
                               return_value=[1]) as mock_link_lookup:
            self.ip_link.side_effect = ipexc.NetlinkError(self.ERROR_CODE,
                                                          msg="Error message")

            self.ip.delete(self.DEVICE, check_exit_code=[self.ERROR_CODE])
            mock_link_lookup.assert_called_once_with(ifname=self.DEVICE)
            self.ip_link.assert_called_once_with('del', index=1)

            self.assertRaises(ipexc.NetlinkError, self.ip.delete, self.DEVICE,
                              check_exit_code=[self.OTHER_ERROR_CODE])
