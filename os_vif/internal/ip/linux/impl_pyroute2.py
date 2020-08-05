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

from oslo_log import log as logging
from oslo_utils import excutils
from pyroute2 import iproute
from pyroute2.netlink import exceptions as ipexc
from pyroute2.netlink.rtnl import ifinfmsg

from os_vif import exception
from os_vif.internal.ip import ip_command
from os_vif import utils

LOG = logging.getLogger(__name__)


class PyRoute2(ip_command.IpCommand):

    def _ip_link(self, ip, command, check_exit_code, **kwargs):
        try:
            LOG.debug('pyroute2 command %(command)s, arguments %(args)s' %
                      {'command': command, 'args': kwargs})
            return ip.link(command, **kwargs)
        except ipexc.NetlinkError as e:
            with excutils.save_and_reraise_exception() as ctx:
                if e.code in check_exit_code:
                    LOG.error('NetlinkError was raised, code %s, message: %s' %
                              (e.code, str(e)))
                    ctx.reraise = False

    def set(self, device, check_exit_code=None, state=None, mtu=None,
            address=None, promisc=None, master=None):
        check_exit_code = check_exit_code or []
        with iproute.IPRoute() as ip:
            idx = self.lookup_interface(ip, device)
            args = {'index': idx}
            if state:
                args['state'] = state
            if mtu:
                args['mtu'] = mtu
            if address:
                args['address'] = address
            if promisc is not None:
                flags = ip.link('get', index=idx)[0]['flags']
                args['flags'] = (utils.set_mask(flags, ifinfmsg.IFF_PROMISC)
                                 if promisc is True else
                                 utils.unset_mask(flags, ifinfmsg.IFF_PROMISC))
            if master:
                args['master'] = self.lookup_interface(ip, master)

            if isinstance(check_exit_code, int):
                check_exit_code = [check_exit_code]

            return self._ip_link(ip, 'set', check_exit_code, **args)

    def lookup_interface(self, ip, link):
        # TODO(sean-k-mooney): remove try block after we raise
        # the min pyroute2 version above 0.5.12
        try:
            idx = ip.link_lookup(ifname=link)
        except ipexc.NetlinkError:
            raise exception.NetworkInterfaceNotFound(interface=link)
        if not len(idx):
            raise exception.NetworkInterfaceNotFound(interface=link)
        return idx[0]

    def add(self, device, dev_type, check_exit_code=None, peer=None, link=None,
            vlan_id=None, ageing=None):
        check_exit_code = check_exit_code or []
        with iproute.IPRoute() as ip:
            args = {'ifname': device,
                    'kind': dev_type}
            if self.TYPE_VLAN == dev_type:
                args['vlan_id'] = vlan_id
                args['link'] = self.lookup_interface(ip, link)
            elif self.TYPE_VETH == dev_type:
                args['peer'] = peer
            elif self.TYPE_BRIDGE == dev_type:
                # NOTE(sean-k-mooney): the keys are defined in the pyroute2
                # codebase but are not documented. see the nla_map field
                # in the bridge_data class located in the
                # pyroute2.netlink.rtnl.ifinfmsg module for mode details
                # https://github.com/svinota/pyroute2/blob/3ba9cdde34b2346ef8c2f8ba17cef5dbeb4c6d52/pyroute2/netlink/rtnl/ifinfmsg/__init__.py#L776-L820
                args['IFLA_BR_FORWARD_DELAY'] = 0  # set no delay
                args['IFLA_BR_STP_STATE'] = 0  # disable spanning tree
                args['IFLA_BR_MCAST_SNOOPING'] = 0  # disable snooping
                # NOTE(sean-k-mooney): we conditionally enable mac ageing as
                # this code is shared between the ovs and linux bridge
                # plugins. For linux bridge we want to allow the default
                # ageing of 300 seconds, whereas for ovs with the ip-tables
                # firewall we want to disable ageing. None was chosen as
                # the default value of ageing to allow the caller to determine
                # what policy to use and keep this code generic.
                if ageing is not None:
                    args['IFLA_BR_AGEING_TIME'] = ageing
            else:
                raise exception.NetworkInterfaceTypeNotDefined(type=dev_type)

            return self._ip_link(ip, 'add', check_exit_code, **args)

    def delete(self, device, check_exit_code=None):
        check_exit_code = check_exit_code or []
        with iproute.IPRoute() as ip:
            idx = self.lookup_interface(ip, device)
            return self._ip_link(ip, 'del', check_exit_code, **{'index': idx})

    def exists(self, device):
        """Return True if the device exists."""
        with iproute.IPRoute() as ip:
            try:
                self.lookup_interface(ip, device)
                return True
            except Exception:
                return False
