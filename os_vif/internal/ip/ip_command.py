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

import abc


class IpCommand(metaclass=abc.ABCMeta):

    TYPE_VETH = 'veth'
    TYPE_VLAN = 'vlan'
    TYPE_BRIDGE = 'bridge'

    @abc.abstractmethod
    def set(self, device, check_exit_code=None, state=None, mtu=None,
            address=None, promisc=None, master=None):
        """Method to set a parameter in an interface.

        :param   device: A network device (string)
        :param   check_exit_code: List of integers of allowed execution exit
                                  codes
        :param   state: String network device state
        :param   mtu: Integer MTU value
        :param   address: String MAC address
        :param   promisc: Boolean promiscuous mode
        :param   master: String the master device that this device belongs to
        :return: status of the command execution
        """

    @abc.abstractmethod
    def add(self, device, dev_type, check_exit_code=None, peer=None, link=None,
            vlan_id=None, ageing=None):
        """Method to add an interface.

        :param   device: A network device (string)
        :param   dev_type: String network device type (TYPE_VETH, TYPE_VLAN)
        :param   check_exit_code: List of integers of allowed execution exit
                                  codes
        :param   peer: String peer name, for veth interfaces
        :param   link: String root network interface name, 'device' will be a
                       VLAN tagged virtual interface
        :param   vlan_id: Integer VLAN ID for VLAN devices
        :param   ageing: integer value in seconds before learned
                         mac addresses are forgotten.
        :return: status of the command execution
        """

    @abc.abstractmethod
    def delete(self, device, check_exit_code=None):
        """Method to delete an interface.

        :param   device: A network device (string)
        :param   dev_type: String network device type (TYPE_VETH, TYPE_VLAN)
        :return: status of the command execution
        """

    @abc.abstractmethod
    def exists(self, device):
        """Method to dectect if a device exists.

        :param   device: A network device (string)
        :return: True if device exists else False
        """
