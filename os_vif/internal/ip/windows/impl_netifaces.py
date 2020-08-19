#    Derived from: neutron/agent/windows/ip_lib.py
#
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

import netifaces

from oslo_log import log as logging

from os_vif import exception
from os_vif.internal.ip import ip_command

LOG = logging.getLogger(__name__)


class Netifaces(ip_command.IpCommand):

    def exists(self, device):
        """Return True if the device exists in the namespace."""
        try:
            return bool(netifaces.ifaddresses(device))
        except ValueError:
            LOG.warning("The device does not exist on the system: %s", device)
            return False
        except OSError:
            LOG.error("Failed to get interface addresses: %s", device)
            return False

    def set(self, device, check_exit_code=None, state=None, mtu=None,
            address=None, promisc=None, master=None):
        exception.NotImplementedForOS(function='ip.set', os='Windows')

    def add(self, device, dev_type, check_exit_code=None, peer=None, link=None,
            vlan_id=None):
        exception.NotImplementedForOS(function='ip.add', os='Windows')

    def delete(self, device, check_exit_code=None):
        exception.NotImplementedForOS(function='ip.delete', os='Windows')
