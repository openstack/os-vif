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

"""Implements vlans, bridges using linux utilities."""

import glob
import os
import re
import sys

from os_vif.internal.ip.api import ip as ip_lib
from oslo_concurrency import processutils
from oslo_log import log as logging
from oslo_utils import excutils

from vif_plug_ovs import constants
from vif_plug_ovs import exception
from vif_plug_ovs import privsep

LOG = logging.getLogger(__name__)

VIRTFN_RE = re.compile(r"virtfn(\d+)")

# phys_port_name only contains the VF number
INT_RE = re.compile(r"^(\d+)$")
# phys_port_name contains VF## or vf##
VF_RE = re.compile(r"vf(\d+)", re.IGNORECASE)
# phys_port_name contains PF## or pf##
PF_RE = re.compile(r"pf(\d+)", re.IGNORECASE)
# bus_info (bdf) contains <bus>:<dev>.<func>
PF_FUNC_RE = re.compile(r"\.(\d+)", 0)

_SRIOV_TOTALVFS = "sriov_totalvfs"


def _update_device_mtu(dev, mtu):
    if not mtu:
        return
    if sys.platform != constants.PLATFORM_WIN32:
        # Hyper-V with OVS does not support external programming of
        # virtual interface MTUs via netsh or other Windows tools.
        # When plugging an interface on Windows, we therefore skip
        # programming the MTU and fallback to DHCP advertisement.
        set_device_mtu(dev, mtu)


@privsep.vif_plug.entrypoint
def delete_net_dev(dev):
    """Delete a network device only if it exists."""
    if ip_lib.exists(dev):
        try:
            ip_lib.delete(dev, check_exit_code=[0, 2, 254])
            LOG.debug("Net device removed: '%s'", dev)
        except processutils.ProcessExecutionError:
            with excutils.save_and_reraise_exception():
                LOG.error("Failed removing net device: '%s'", dev)


@privsep.vif_plug.entrypoint
def create_veth_pair(dev1_name, dev2_name, mtu):
    """Create a pair of veth devices with the specified names,
    deleting any previous devices with those names.
    """
    for dev in [dev1_name, dev2_name]:
        delete_net_dev(dev)

    ip_lib.add(dev1_name, 'veth', peer=dev2_name)
    for dev in [dev1_name, dev2_name]:
        ip_lib.set(dev, state='up')
        ip_lib.set(dev, promisc='on')
        _update_device_mtu(dev, mtu)


@privsep.vif_plug.entrypoint
def update_veth_pair(dev1_name, dev2_name, mtu):
    """Update a pair of veth devices with new configuration."""
    for dev in [dev1_name, dev2_name]:
        _update_device_mtu(dev, mtu)


def _disable_ipv6(bridge):
    """Disable ipv6 if available for bridge. Must be called from
       privsep context.
    """
    # NOTE(sean-k-mooney): os-vif disables ipv6 to ensure the Bridge
    # does not aquire an ipv6 auto config or link local adress.
    # This is required to prevent bug 1302080.
    # https://bugs.launchpad.net/neutron/+bug/1302080
    disv6 = ('/proc/sys/net/ipv6/conf/%s/disable_ipv6' %
             bridge)
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


@privsep.vif_plug.entrypoint
def ensure_bridge(bridge):
    if not ip_lib.exists(bridge):
        ip_lib.add(bridge, 'bridge')
    _disable_ipv6(bridge)
    _arp_filtering(bridge)
    # we bring up the bridge to allow it to switch packets
    set_interface_state(bridge, 'up')


@privsep.vif_plug.entrypoint
def delete_bridge(bridge, dev):
    if ip_lib.exists(bridge):
        # Note(sean-k-mooney): this will detach all ports on
        # the bridge before deleting the bridge.
        ip_lib.delete(bridge, check_exit_code=[0, 2, 254])
        # howver it will not set the detached interface down
        # so we set the dev down if dev is not None and exists.
        if dev and ip_lib.exists(dev):
            set_interface_state(dev, "down")


@privsep.vif_plug.entrypoint
def add_bridge_port(bridge, dev):
    ip_lib.set(dev, master=bridge)


@privsep.vif_plug.entrypoint
def set_device_mtu(dev, mtu):
    """Set the device MTU."""
    if ip_lib.exists(dev):
        ip_lib.set(dev, mtu=mtu, check_exit_code=[0, 2, 254])


@privsep.vif_plug.entrypoint
def set_interface_state(interface_name, port_state):
    ip_lib.set(interface_name, state=port_state, check_exit_code=[0, 2, 254])


def _parse_vf_number(phys_port_name):
    """Parses phys_port_name and returns VF number or None.

    To determine the VF number of a representor, parse phys_port_name
    in the following sequence and return the first valid match. If none
    match, then the representor is not for a VF.
    """
    match = INT_RE.search(phys_port_name)
    if match:
        return match.group(1)
    match = VF_RE.search(phys_port_name)
    if match:
        return match.group(1)
    return None


def _parse_pf_number(phys_port_name):
    """Parses phys_port_name and returns PF number or None.

    To determine the PF number of a representor, parse phys_port_name in
    the following sequence and return the first valid match. If none
    match, then the representor is not for a PF.
    """
    match = PF_RE.search(phys_port_name)
    if match:
        return match.group(1)
    return None


# This function is taken from nova/pci/utils.py
def get_function_by_ifname(ifname):
    """Given the device name, returns the PCI address of a device
    and returns True if the address is in a physical function.
    """
    dev_path = "/sys/class/net/%s/device" % ifname
    sriov_totalvfs = 0
    if os.path.isdir(dev_path):
        try:
            # sriov_totalvfs contains the maximum possible VFs for this PF
            dev_path_file = os.path.join(dev_path, _SRIOV_TOTALVFS)
            with open(dev_path_file, 'r') as fd:
                sriov_totalvfs = int(fd.readline().rstrip())
                return (os.readlink(dev_path).strip("./"),
                        sriov_totalvfs > 0)
        except (IOError, ValueError):
            return os.readlink(dev_path).strip("./"), False
    return None, False


def _get_pf_func(pf_ifname):
    """Gets PF function number using pf_ifname and returns function
    number or None.
    """

    address_str, pf = get_function_by_ifname(pf_ifname)
    if not address_str:
        return None
    match = PF_FUNC_RE.search(address_str)
    if match:
        return match.group(1)
    return None


def get_representor_port(pf_ifname, vf_num):
    """Get the representor netdevice which is corresponding to the VF.

    This method gets PF interface name and number of VF. It iterates over all
    the interfaces under the PF location and looks for interface that has the
    VF number in the phys_port_name. That interface is the representor for
    the requested VF.
    """
    pf_path = "/sys/class/net/%s" % pf_ifname
    pf_sw_id_file = os.path.join(pf_path, "phys_switch_id")

    pf_sw_id = None
    try:
        with open(pf_sw_id_file, 'r') as fd:
            pf_sw_id = fd.readline().rstrip()
    except (OSError, IOError):
        raise exception.RepresentorNotFound(ifname=pf_ifname, vf_num=vf_num)

    pf_subsystem_file = os.path.join(pf_path, "subsystem")
    try:
        devices = os.listdir(pf_subsystem_file)
    except (OSError, IOError):
        raise exception.RepresentorNotFound(ifname=pf_ifname, vf_num=vf_num)

    for device in devices:
        address_str, pf = get_function_by_ifname(device)
        if pf:
            continue

        device_path = "/sys/class/net/%s" % device
        device_sw_id_file = os.path.join(device_path, "phys_switch_id")
        try:
            with open(device_sw_id_file, 'r') as fd:
                device_sw_id = fd.readline().rstrip()
        except (OSError, IOError):
            continue

        if device_sw_id != pf_sw_id:
            continue
        device_port_name_file = (
            os.path.join(device_path, 'phys_port_name'))

        if not os.path.isfile(device_port_name_file):
            continue

        try:
            with open(device_port_name_file, 'r') as fd:
                phys_port_name = fd.readline().rstrip()
        except (OSError, IOError):
            continue

        # If the phys_port_name of the VF-rep is of the format pfXvfY
        # (or vfY@pfX), then match "X" (parent PF's func number) with
        # the PCI func number of pf_ifname.
        rep_parent_pf_func = _parse_pf_number(phys_port_name)
        if rep_parent_pf_func is not None:
                ifname_pf_func = _get_pf_func(pf_ifname)
                if ifname_pf_func is None:
                    continue
                if int(rep_parent_pf_func) != int(ifname_pf_func):
                    continue

        representor_num = _parse_vf_number(phys_port_name)
        # Note: representor_num can be 0, referring to VF0
        if representor_num is None:
            continue

        # At this point we're confident we have a representor.
        try:
            if int(representor_num) == int(vf_num):
                return device
        except (ValueError):
            continue

    raise exception.RepresentorNotFound(ifname=pf_ifname, vf_num=vf_num)


def _get_sysfs_netdev_path(pci_addr, pf_interface):
    """Get the sysfs path based on the PCI address of the device.

    Assumes a networking device - will not check for the existence of the path.
    """
    if pf_interface:
        return "/sys/bus/pci/devices/%s/physfn/net" % (pci_addr)
    return "/sys/bus/pci/devices/%s/net" % (pci_addr)


def _is_switchdev(netdev):
    """Returns True if a netdev has a readable phys_switch_id"""
    try:
        sw_id_file = "/sys/class/net/%s/phys_switch_id" % netdev
        with open(sw_id_file, 'r') as fd:
            phys_switch_id = fd.readline().rstrip()
        if phys_switch_id != "" and phys_switch_id is not None:
            return True
    except (OSError, IOError):
        return False
    return False


def get_ifname_by_pci_address(pci_addr, pf_interface=False, switchdev=False):
    """Get the interface name based on a VF's pci address

    :param pci_addr: the PCI address of the VF
    :param pf_interface: if True, look for the netdev of the parent PF
    :param switchdev: if True, ensure that phys_switch_id is valid

    :returns: netdev interface name

    The returned interface name is either the parent PF or that of the VF
    itself based on the argument of pf_interface.
    """
    dev_path = _get_sysfs_netdev_path(pci_addr, pf_interface)
    # make the if statement later more readable
    ignore_switchdev = not switchdev
    try:
        for netdev in os.listdir(dev_path):
            if ignore_switchdev or _is_switchdev(netdev):
                return netdev
    except Exception:
        raise exception.PciDeviceNotFoundById(id=pci_addr)
    raise exception.PciDeviceNotFoundById(id=pci_addr)


def get_vf_num_by_pci_address(pci_addr):
    """Get the VF number based on a VF's pci address

    A VF is associated with an VF number, which ip link command uses to
    configure it. This number can be obtained from the PCI device filesystem.
    """
    virtfns_path = "/sys/bus/pci/devices/%s/physfn/virtfn*" % (pci_addr)
    vf_num = None
    try:
        for vf_path in glob.iglob(virtfns_path):
            if re.search(pci_addr, os.readlink(vf_path)):
                t = VIRTFN_RE.search(vf_path)
                vf_num = t.group(1)
                break
    except Exception:
        pass
    if vf_num is None:
        raise exception.PciDeviceNotFoundById(id=pci_addr)
    return vf_num
