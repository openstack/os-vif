# Derived from nova/network/linux_net.py
#
# Copyright (c) 2011 X.commerce, a business unit of eBay Inc.
# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
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

"""Implements vlans, bridges, and iptables rules using linux utilities."""

import os

from os_vif.internal.ip.api import ip as ip_lib
from oslo_concurrency import lockutils
from oslo_concurrency import processutils
from oslo_log import log as logging

from vif_plug_linux_bridge import privsep


LOG = logging.getLogger(__name__)
_IPTABLES_MANAGER = None


def _set_device_mtu(dev, mtu):
    """Set the device MTU."""
    if mtu:
        ip_lib.set(dev, mtu=mtu, check_exit_code=[0, 2, 254])
    else:
        LOG.debug("MTU not set on %(interface_name)s interface",
                  {'interface_name': dev})


def _ip_bridge_cmd(action, params, device):
    """Build commands to add/del ips to bridges/devices."""
    cmd = ['ip', 'addr', action]
    cmd.extend(params)
    cmd.extend(['dev', device])
    return cmd


@privsep.vif_plug.entrypoint
def ensure_vlan_bridge(vlan_num, bridge, bridge_interface,
                       net_attrs=None, mac_address=None,
                       mtu=None):
    """Create a vlan and bridge unless they already exist."""
    interface = _ensure_vlan_privileged(vlan_num, bridge_interface,
                                        mac_address, mtu=mtu)
    _ensure_bridge_privileged(bridge, interface, net_attrs)
    _ensure_bridge_filtering(bridge, None)
    return interface


@lockutils.synchronized('nova-lock_vlan', external=True)
def _ensure_vlan_privileged(vlan_num, bridge_interface, mac_address, mtu):
    """Create a vlan unless it already exists.

    This assumes the caller is already annotated to run
    with elevated privileges.
    """
    interface = 'vlan%s' % vlan_num
    if not ip_lib.exists(interface):
        LOG.debug('Starting VLAN interface %s', interface)
        ip_lib.add(interface, 'vlan', link=bridge_interface,
                   vlan_id=vlan_num, check_exit_code=[0, 2, 254])
        # (danwent) the bridge will inherit this address, so we want to
        # make sure it is the value set from the NetworkManager
        if mac_address:
            ip_lib.set(interface, address=mac_address,
                       check_exit_code=[0, 2, 254])
        ip_lib.set(interface, state='up', check_exit_code=[0, 2, 254])
        # NOTE(vish): set mtu every time to ensure that changes to mtu get
        #             propagated
        _set_device_mtu(interface, mtu)

    return interface


@lockutils.synchronized('nova-lock_bridge', external=True)
def ensure_bridge(bridge, interface, net_attrs=None, gateway=True,
                  filtering=True, mtu=None):
    _ensure_bridge_privileged(bridge, interface, net_attrs, gateway,
                              filtering=filtering, mtu=mtu)
    if filtering:
        _ensure_bridge_filtering(bridge, gateway)


# TODO(sean-k-mooney): extract into common module
def _disable_ipv6(bridge):
    """disable ipv6 for bridge if available, must be called from
       privsep context.
    :param bridge: string bridge name
    """
    # NOTE(sean-k-mooney): os-vif disables ipv6 to ensure the Bridge
    # does not aquire an ipv6 auto config or link local adress.
    # This is required to prevent bug 1302080.
    # https://bugs.launchpad.net/neutron/+bug/1302080
    disv6 = ('/proc/sys/net/ipv6/conf/%s/disable_ipv6' % bridge)
    if os.path.exists(disv6):
        with open(disv6, 'w') as f:
            f.write('1')


# TODO(ralonsoh): extract into common module
def _arp_filtering(bridge):
    """Prevent the bridge from replying to ARP messages with machine local IPs

    1. Reply only if the target IP address is local address configured on the
       incoming interface.
    2. Always use the best local address.
    """
    arp_params = [('/proc/sys/net/ipv4/conf/%s/arp_ignore' % bridge, '1'),
                  ('/proc/sys/net/ipv4/conf/%s/arp_announce' % bridge, '2')]
    for parameter, value in arp_params:
        if os.path.exists(parameter):
            with open(parameter, 'w') as f:
                f.write(value)


def _update_bridge_routes(interface, bridge):
    """Updates routing table for a given bridge and interface.
    :param interface: string interface name
    :param bridge: string bridge name
    """
    # TODO(sean-k-mooney): investigate deleting all this route
    # handling code. The vm tap devices should never have an ip,
    # this is old nova networks code and i dont think it will ever
    # be needed in os-vif.
    # NOTE(vish): This will break if there is already an ip on the
    #             interface, so we move any ips to the bridge
    # NOTE(danms): We also need to copy routes to the bridge so as
    #              not to break existing connectivity on the interface
    old_routes = []
    out, _ = processutils.execute('ip', 'route', 'show', 'dev',
                                  interface)
    for line in out.split('\n'):
        fields = line.split()
        if fields and 'via' in fields:
            old_routes.append(fields)
            processutils.execute('ip', 'route', 'del', *fields)

    out, _ = processutils.execute('ip', 'addr', 'show', 'dev',
                                  interface, 'scope', 'global')
    for line in out.split('\n'):
        fields = line.split()
        if fields and fields[0] == 'inet':
            if fields[-2] in ('secondary', 'dynamic', ):
                params = fields[1:-2]
            else:
                params = fields[1:-1]
                processutils.execute(*_ip_bridge_cmd('del', params,
                                                     fields[-1]),
                                     check_exit_code=[0, 2, 254])
                processutils.execute(*_ip_bridge_cmd('add', params,
                                                     bridge),
                                     check_exit_code=[0, 2, 254])
    for fields in old_routes:
        processutils.execute('ip', 'route', 'add', *fields)


@privsep.vif_plug.entrypoint
def _ensure_bridge_privileged(bridge, interface, net_attrs, gateway,
                              filtering=True, mtu=None):
    """Create a bridge unless it already exists.

    :param interface: the interface to create the bridge on.
    :param net_attrs: dictionary with  attributes used to create bridge.
    :param gateway: whether or not the bridge is a gateway.
    :param filtering: whether or not to create filters on the bridge.
    :param mtu: MTU of bridge.

    If net_attrs is set, it will add the net_attrs['gateway'] to the bridge
    using net_attrs['broadcast'] and net_attrs['cidr'].  It will also add
    the ip_v6 address specified in net_attrs['cidr_v6'] if use_ipv6 is set.

    The code will attempt to move any ips that already exist on the
    interface onto the bridge and reset the default gateway if necessary.

    """
    if not ip_lib.exists(bridge):
        LOG.debug('Starting Bridge %s', bridge)
        ip_lib.add(bridge, 'bridge')
        _disable_ipv6(bridge)
        _arp_filtering(bridge)
        ip_lib.set(bridge, state='up')

    if interface and ip_lib.exists(interface):
        LOG.debug('Adding interface %(interface)s to bridge %(bridge)s',
                  {'interface': interface, 'bridge': bridge})
        ip_lib.set(interface, master=bridge, state='up',
                   check_exit_code=[0, 2, 254])

        _set_device_mtu(interface, mtu)
        _update_bridge_routes(interface, bridge)
        # NOTE(sean-k-mooney):
        # The bridge mtu cannot be set until after an
        # interface is added due to bug:
        # https://bugs.launchpad.net/ubuntu/+source/linux/+bug/1399064
        _set_device_mtu(bridge, mtu)


def _ensure_bridge_filtering(bridge, gateway):
    # This method leaves privsep usage to iptables manager
    # Don't forward traffic unless we were told to be a gateway
    LOG.debug("Ensuring filtering %s to %s", bridge, gateway)
    global _IPTABLES_MANAGER
    ipv4_filter = _IPTABLES_MANAGER.ipv4['filter']
    if gateway:
        for rule in _IPTABLES_MANAGER.get_gateway_rules(bridge):
            ipv4_filter.add_rule(*rule)
    else:
        ipv4_filter.add_rule('FORWARD',
                             ('--in-interface %s -j %s'
                              % (bridge,
                                 _IPTABLES_MANAGER.iptables_drop_action)))
    ipv4_filter.add_rule('FORWARD',
                         ('--out-interface %s -j %s'
                          % (bridge,
                             _IPTABLES_MANAGER.iptables_drop_action)))
    _IPTABLES_MANAGER.apply()


def configure(iptables_mgr):
    """Configure the iptables manager impl.

    :param iptables_mgr: the iptables manager instance
    """
    global _IPTABLES_MANAGER
    _IPTABLES_MANAGER = iptables_mgr
