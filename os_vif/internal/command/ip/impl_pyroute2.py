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
from os_vif.internal.command.ip import api
from os_vif import utils

LOG = logging.getLogger(__name__)


class PyRoute2(api.IpCommand):

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
            address=None, promisc=None):
        check_exit_code = check_exit_code or []
        ip = iproute.IPRoute()
        idx = ip.link_lookup(ifname=device)
        if not idx:
            raise exception.NetworkInterfaceNotFound(interface=device)
        idx = idx[0]

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

        if isinstance(check_exit_code, int):
            check_exit_code = [check_exit_code]

        return self._ip_link(ip, 'set', check_exit_code, **args)

    def add(self, device, dev_type, check_exit_code=None, peer=None, link=None,
            vlan_id=None):
        check_exit_code = check_exit_code or []
        ip = iproute.IPRoute()
        args = {'ifname': device,
                'kind': dev_type}
        if self.TYPE_VLAN == dev_type:
            args['vlan_id'] = vlan_id
            idx = ip.link_lookup(ifname=link)
            if 0 == len(idx):
                raise exception.NetworkInterfaceNotFound(interface=link)
            args['link'] = idx[0]
        elif self.TYPE_VETH == dev_type:
            args['peer'] = peer
        else:
            raise exception.NetworkInterfaceTypeNotDefined(type=dev_type)

        return self._ip_link(ip, 'add', check_exit_code, **args)

    def delete(self, device, check_exit_code=None):
        check_exit_code = check_exit_code or []
        ip = iproute.IPRoute()
        idx = ip.link_lookup(ifname=device)
        if len(idx) == 0:
            raise exception.NetworkInterfaceNotFound(interface=device)
        idx = idx[0]

        return self._ip_link(ip, 'del', check_exit_code, **{'index': idx})
