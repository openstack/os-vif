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
import six

from oslo_log import log as logging
from oslo_utils import importutils


LOG = logging.getLogger(__name__)


impl_map = {
    'pyroute2': 'os_vif.internal.command.ip.impl_pyroute2.PyRoute2',
    'IPTools': 'os_vif.internal.command.ip.impl_shell.IPTools',
}


def _get_impl():
    # NOTE(sean-k-mooney): currently pyroute2 has a file handle leak. An
    # iptools driver has been added as a workaround but No config options are
    # exposed to the user. The iptools driver is considered deprecated and
    # will be removed when a new release of pyroute2 is available.
    driver = 'IPTools'
    return importutils.import_object(impl_map[driver])


@six.add_metaclass(abc.ABCMeta)
class IpCommand(object):

    TYPE_VETH = 'veth'
    TYPE_VLAN = 'vlan'

    @abc.abstractmethod
    def set(self, device, check_exit_code=None, state=None, mtu=None,
            address=None, promisc=None):
        """Method to set a parameter in an interface.

        :param   device: A network device (string)
        :param   check_exit_code: List of integers of allowed execution exit
                                  codes
        :param   state: String network device state
        :param   mtu: Integer MTU value
        :param   address: String MAC address
        :param   promisc: Boolean promiscuous mode
        :return: status of the command execution
        """

    @abc.abstractmethod
    def add(self, device, dev_type, check_exit_code=None, peer=None, link=None,
            vlan_id=None):
        """Method to add an interface.

        :param   device: A network device (string)
        :param   dev_type: String network device type (TYPE_VETH, TYPE_VLAN)
        :param   check_exit_code: List of integers of allowed execution exit
                                  codes
        :param   peer: String peer name, for veth interfaces
        :param   link: String root network interface name, 'device' will be a
                       VLAN tagged virtual interface
        :param   vlan_id: Integer VLAN ID for VLAN devices
        :return: status of the command execution
        """

    @abc.abstractmethod
    def delete(self, device, check_exit_code=None):
        """Method to delete an interface.

        :param   device: A network device (string)
        :param   dev_type: String network device type (TYPE_VETH, TYPE_VLAN)
        :return: status of the command execution
        """
