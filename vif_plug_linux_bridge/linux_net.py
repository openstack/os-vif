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

from oslo_concurrency import lockutils
from oslo_concurrency import processutils
from oslo_log import log as logging
from oslo_utils import excutils

from vif_plug_linux_bridge import privsep

LOG = logging.getLogger(__name__)
_IPTABLES_MANAGER = None


def device_exists(device):
    """Check if ethernet device exists."""
    return os.path.exists('/sys/class/net/%s' % device)


def _set_device_mtu(dev, mtu):
    """Set the device MTU."""
    if mtu:
        processutils.execute('ip', 'link', 'set', dev, 'mtu', mtu,
                             check_exit_code=[0, 2, 254])
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
    if not device_exists(interface):
        LOG.debug('Starting VLAN interface %s', interface)
        processutils.execute('ip', 'link', 'add', 'link',
                             bridge_interface, 'name', interface, 'type',
                             'vlan', 'id', vlan_num,
                             check_exit_code=[0, 2, 254])
        # (danwent) the bridge will inherit this address, so we want to
        # make sure it is the value set from the NetworkManager
        if mac_address:
            processutils.execute('ip', 'link', 'set', interface,
                                 'address', mac_address,
                                 check_exit_code=[0, 2, 254])
        processutils.execute('ip', 'link', 'set', interface, 'up',
                             check_exit_code=[0, 2, 254])
        # NOTE(vish): set mtu every time to ensure that changes to mtu get
        #             propogated
        _set_device_mtu(interface, mtu)

    return interface


@lockutils.synchronized('nova-lock_bridge', external=True)
def ensure_bridge(bridge, interface, net_attrs=None, gateway=True,
                  filtering=True, mtu=None):
    _ensure_bridge_privileged(bridge, interface, net_attrs, gateway,
                              filtering=filtering, mtu=mtu)
    if filtering:
        _ensure_bridge_filtering(bridge, gateway)


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
    if not device_exists(bridge):
        LOG.debug('Starting Bridge %s', bridge)
        try:
            processutils.execute('brctl', 'addbr', bridge)
        except Exception:
            with excutils.save_and_reraise_exception() as ectx:
                ectx.reraise = not device_exists(bridge)
        processutils.execute('brctl', 'setfd', bridge, 0)
        # processutils.execute('brctl setageing %s 10' % bridge)
        processutils.execute('brctl', 'stp', bridge, 'off')
        disv6 = ('/proc/sys/net/ipv6/conf/%s/disable_ipv6' % bridge)
        if os.path.exists(disv6):
            processutils.execute('tee',
                                 disv6,
                                 process_input='1',
                                 check_exit_code=[0, 1])
        # (danwent) bridge device MAC address can't be set directly.
        # instead it inherits the MAC address of the first device on the
        # bridge, which will either be the vlan interface, or a
        # physical NIC.
        processutils.execute('ip', 'link', 'set', bridge, 'up')

    if interface:
        LOG.debug('Adding interface %(interface)s to bridge %(bridge)s',
                  {'interface': interface, 'bridge': bridge})
        out, err = processutils.execute('brctl', 'addif', bridge,
                                        interface, check_exit_code=False)
        if (err and err != "device %s is already a member of a bridge; "
              "can't enslave it to bridge %s.\n" % (interface, bridge)):
            msg = _('Failed to add interface: %s') % err
            raise Exception(msg)

        out, err = processutils.execute('ip', 'link', 'set',
                                        interface, 'up', check_exit_code=False)

        _set_device_mtu(interface, mtu)

        # NOTE(vish): This will break if there is already an ip on the
        #             interface, so we move any ips to the bridge
        # NOTE(danms): We also need to copy routes to the bridge so as
        #              not to break existing connectivity on the interface
        old_routes = []
        out, err = processutils.execute('ip', 'route', 'show', 'dev',
                                        interface)
        for line in out.split('\n'):
            fields = line.split()
            if fields and 'via' in fields:
                old_routes.append(fields)
                processutils.execute('ip', 'route', 'del', *fields)
        out, err = processutils.execute('ip', 'addr', 'show', 'dev', interface,
                                        'scope', 'global')
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

        # NOTE(sean-k-mooney):
        # The bridge mtu cannont be set until after an
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
