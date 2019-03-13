# Derived from nova/virt/libvirt/vif.py
#
# Copyright (C) 2011 Midokura KK
# Copyright (C) 2011 Nicira, Inc
# Copyright 2011 OpenStack Foundation
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

import sys

from os_vif.internal.ip.api import ip as ip_lib
from os_vif import objects
from os_vif import plugin
from oslo_config import cfg

from vif_plug_ovs import constants
from vif_plug_ovs import exception
from vif_plug_ovs import linux_net
from vif_plug_ovs.ovsdb import api as ovsdb_api
from vif_plug_ovs.ovsdb import ovsdb_lib


class OvsPlugin(plugin.PluginBase):
    """An OVS plugin that can setup VIFs in many ways

    The OVS plugin supports several different VIF types, VIFBridge
    and VIFOpenVSwitch, and will choose the appropriate plugging
    action depending on the type of VIF config it receives.

    If given a VIFBridge, then it will create connect the VM via
    a regular Linux bridge device to allow security group rules to
    be applied to VM traiffic.
    """

    NIC_NAME_LEN = 14

    CONFIG_OPTS = (
        cfg.IntOpt('network_device_mtu',
                   default=1500,
                   help='MTU setting for network interface.',
                   deprecated_group="DEFAULT"),
        cfg.IntOpt('ovs_vsctl_timeout',
                   default=120,
                   help='Amount of time, in seconds, that ovs_vsctl should '
                   'wait for a response from the database. 0 is to wait '
                   'forever.',
                   deprecated_group="DEFAULT"),
        cfg.StrOpt('ovsdb_connection',
                   default='tcp:127.0.0.1:6640',
                   help='The connection string for the OVSDB backend. '
                   'When executing commands using the native or vsctl '
                   'ovsdb interface drivers this config option defines '
                   'the ovsdb endpoint used.'),
        cfg.StrOpt('ovsdb_interface',
                   choices=list(ovsdb_api.interface_map),
                   default='vsctl',
                   help='The interface for interacting with the OVSDB'),
        # NOTE(sean-k-mooney): This value is a bool for two reasons.
        # First I want to allow this config option to be reusable with
        # non ml2/ovs deployment in the future if required, as such I do not
        # want to encode how the isolation is done in the config option.
        # Second in the case of ml2/ovs the isolation is based on VLAN tags.
        # The 802.1Q IEEE spec that defines the VLAN format reserved two VLAN
        # id values, VLAN ID 0 means the packet is a member of no VLAN
        # and VLAN ID 4095 is reserved for implementation defined use.
        # Using VLAN ID 0 would not provide isolation and all other VLAN IDs
        # except VLAN ID 4095 are valid for the ml2/ovs agent to use for a
        # tenant network's local VLAN ID. As such only VLAN ID 4095 is valid
        # to use for vif isolation which is defined in Neutron as the
        # dead VLAN, a VLAN on which all traffic will be dropped.
        cfg.BoolOpt('isolate_vif', default=False,
                    help='Controls if VIF should be isolated when plugged '
                    'to the ovs bridge. This should only be set to True '
                    'when using the neutron ovs ml2 agent.')
    )

    def __init__(self, config):
        super(OvsPlugin, self).__init__(config)
        self.ovsdb = ovsdb_lib.BaseOVS(self.config)

    @staticmethod
    def gen_port_name(prefix, id):
        return ("%s%s" % (prefix, id))[:OvsPlugin.NIC_NAME_LEN]

    @staticmethod
    def get_veth_pair_names(vif):
        return (OvsPlugin.gen_port_name("qvb", vif.id),
                OvsPlugin.gen_port_name("qvo", vif.id))

    def describe(self):
        pp_ovs = objects.host_info.HostPortProfileInfo(
            profile_object_name=
            objects.vif.VIFPortProfileOpenVSwitch.__name__,
            min_version="1.0",
            max_version="1.0",
        )
        pp_ovs_representor = objects.host_info.HostPortProfileInfo(
            profile_object_name=
            objects.vif.VIFPortProfileOVSRepresentor.__name__,
            min_version="1.0",
            max_version="1.0",
        )
        return objects.host_info.HostPluginInfo(
            plugin_name=constants.PLUGIN_NAME,
            vif_info=[
                objects.host_info.HostVIFInfo(
                    vif_object_name=objects.vif.VIFBridge.__name__,
                    min_version="1.0",
                    max_version="1.0",
                    supported_port_profiles=[pp_ovs]),
                objects.host_info.HostVIFInfo(
                    vif_object_name=objects.vif.VIFOpenVSwitch.__name__,
                    min_version="1.0",
                    max_version="1.0",
                    supported_port_profiles=[pp_ovs]),
                objects.host_info.HostVIFInfo(
                    vif_object_name=objects.vif.VIFVHostUser.__name__,
                    min_version="1.0",
                    max_version="1.0",
                    supported_port_profiles=[pp_ovs, pp_ovs_representor]),
                objects.host_info.HostVIFInfo(
                    vif_object_name=objects.vif.VIFHostDevice.__name__,
                    min_version="1.0",
                    max_version="1.0",
                    supported_port_profiles=[pp_ovs, pp_ovs_representor]),
            ])

    def _get_mtu(self, vif):
        if vif.network and vif.network.mtu:
            return vif.network.mtu
        return self.config.network_device_mtu

    def _create_vif_port(self, vif, vif_name, instance_info, **kwargs):
        mtu = self._get_mtu(vif)
        # NOTE(sean-k-mooney): As part of a partial fix to bug #1734320
        # we introduced the isolate_vif config option to enable isolation
        # of the vif prior to neutron wiring up the interface. To do
        # this we take advantage of the fact the ml2/ovs uses the
        # implementation defined VLAN 4095 as a dead VLAN to indicate
        # that all packets should be dropped. We only enable this
        # behaviour conditionally as it is not portable to SDN based
        # deployment such as ODL or OVN as such operator must opt-in
        # to this behaviour by setting the isolate_vif config option.
        # TODO(sean-k-mooney): Extend neutron to record what ml2 driver
        # bound the interface in the vif binding details so isolation
        # can be enabled automatically in the future.
        if self.config.isolate_vif:
            kwargs['tag'] = constants.DEAD_VLAN
        self.ovsdb.create_ovs_vif_port(
            vif.network.bridge,
            vif_name,
            vif.port_profile.interface_id,
            vif.address, instance_info.uuid,
            mtu,
            **kwargs)

    def _update_vif_port(self, vif, vif_name):
        mtu = self._get_mtu(vif)
        self.ovsdb.update_ovs_vif_port(vif_name, mtu)

    @staticmethod
    def _get_vif_datapath_type(vif, datapath=constants.OVS_DATAPATH_SYSTEM):
        profile = vif.port_profile
        if 'datapath_type' not in profile or not profile.datapath_type:
            return datapath
        return profile.datapath_type

    def _plug_vhostuser(self, vif, instance_info):
        self.ovsdb.ensure_ovs_bridge(
            vif.network.bridge, self._get_vif_datapath_type(
                vif, datapath=constants.OVS_DATAPATH_NETDEV))
        vif_name = OvsPlugin.gen_port_name(
            constants.OVS_VHOSTUSER_PREFIX, vif.id)
        args = {}
        if vif.mode == "client":
            args['interface_type'] = \
                constants.OVS_VHOSTUSER_INTERFACE_TYPE
        else:
            args['interface_type'] = \
                constants.OVS_VHOSTUSER_CLIENT_INTERFACE_TYPE
            args['vhost_server_path'] = vif.path

        self._create_vif_port(
            vif, vif_name, instance_info, **args)

    def _plug_bridge(self, vif, instance_info):
        """Plug using hybrid strategy

        Create a per-VIF linux bridge, then link that bridge to the OVS
        integration bridge via a veth device, setting up the other end
        of the veth device just like a normal OVS port. Then boot the
        VIF on the linux bridge using standard libvirt mechanisms.
        """

        v1_name, v2_name = self.get_veth_pair_names(vif)

        linux_net.ensure_bridge(vif.bridge_name)

        mtu = self._get_mtu(vif)
        if not ip_lib.exists(v2_name):
            linux_net.create_veth_pair(v1_name, v2_name, mtu)
            linux_net.add_bridge_port(vif.bridge_name, v1_name)
            self.ovsdb.ensure_ovs_bridge(vif.network.bridge,
                self._get_vif_datapath_type(vif))
            self._create_vif_port(vif, v2_name, instance_info)
        else:
            linux_net.update_veth_pair(v1_name, v2_name, mtu)
            self._update_vif_port(vif, v2_name)

    def _plug_vif_windows(self, vif, instance_info):
        """Create a per-VIF OVS port."""

        if not ip_lib.exists(vif.id):
            self.ovsdb.ensure_ovs_bridge(vif.network.bridge,
                                         self._get_vif_datapath_type(vif))
            self._create_vif_port(vif, vif.id, instance_info)

    def _plug_vif_generic(self, vif, instance_info):
        """Create a per-VIF OVS port."""
        self.ovsdb.ensure_ovs_bridge(vif.network.bridge,
                                     self._get_vif_datapath_type(vif))
        # NOTE(sean-k-mooney): as part of a partial revert of
        # change Iaf15fa7a678ec2624f7c12f634269c465fbad930
        # (always create ovs port during plug), we stopped calling
        # self._create_vif_port(vif, vif.vif_name, instance_info).
        # Calling _create_vif_port here was intended to ensure
        # that the vif was wired up by neutron before the vm was
        # spawned on boot or live migration to partially resolve
        # #1734320. When the "always create ovs port during plug" change
        # was written it was understood by me that libvirt would not
        # modify ovs if the port exists but in fact it deletes and
        # recreates the port. This both undoes the effort to resolve
        # bug #1734320 and intoduces other issues for neutron.
        # this comment will be removed when we actully fix #1734320 in
        # all cases.

        # NOTE(hamdyk): As a WA to the above note, one can use
        # VIFPortProfileOpenVSwitch.create_port flag to explicitly
        # plug the port to the switch.
        if ("create_port" in vif.port_profile and
                vif.port_profile.create_port):
            self._create_vif_port(vif, vif.vif_name, instance_info)

    def _plug_vf_passthrough(self, vif, instance_info):
        self.ovsdb.ensure_ovs_bridge(
            vif.network.bridge, constants.OVS_DATAPATH_SYSTEM)
        pci_slot = vif.dev_address
        pf_ifname = linux_net.get_ifname_by_pci_address(
            pci_slot, pf_interface=True, switchdev=True)
        vf_num = linux_net.get_vf_num_by_pci_address(pci_slot)
        representor = linux_net.get_representor_port(pf_ifname, vf_num)
        linux_net.set_interface_state(representor, 'up')
        self._create_vif_port(vif, representor, instance_info)

    def plug(self, vif, instance_info):
        if not hasattr(vif, "port_profile"):
            raise exception.MissingPortProfile()
        if not isinstance(vif.port_profile,
                          objects.vif.VIFPortProfileOpenVSwitch):
            raise exception.WrongPortProfile(
                profile=vif.port_profile.__class__.__name__)

        if isinstance(vif, objects.vif.VIFOpenVSwitch):
            if sys.platform != constants.PLATFORM_WIN32:
                self._plug_vif_generic(vif, instance_info)
            else:
                self._plug_vif_windows(vif, instance_info)
        elif isinstance(vif, objects.vif.VIFBridge):
            if sys.platform != constants.PLATFORM_WIN32:
                self._plug_bridge(vif, instance_info)
            else:
                self._plug_vif_windows(vif, instance_info)
        elif isinstance(vif, objects.vif.VIFVHostUser):
            self._plug_vhostuser(vif, instance_info)
        elif isinstance(vif, objects.vif.VIFHostDevice):
            self._plug_vf_passthrough(vif, instance_info)

    def _unplug_vhostuser(self, vif, instance_info):
        self.ovsdb.delete_ovs_vif_port(vif.network.bridge,
            OvsPlugin.gen_port_name(
                constants.OVS_VHOSTUSER_PREFIX,
                vif.id))

    def _unplug_bridge(self, vif, instance_info):
        """UnPlug using hybrid strategy

        Unhook port from OVS, unhook port from bridge, delete
        bridge, and delete both veth devices.
        """

        v1_name, v2_name = self.get_veth_pair_names(vif)

        linux_net.delete_bridge(vif.bridge_name, v1_name)

        self.ovsdb.delete_ovs_vif_port(vif.network.bridge, v2_name)

    def _unplug_vif_windows(self, vif, instance_info):
        """Remove port from OVS."""
        self.ovsdb.delete_ovs_vif_port(vif.network.bridge, vif.id,
                                       delete_netdev=False)

    def _unplug_vif_generic(self, vif, instance_info):
        """Remove port from OVS."""
        # NOTE(sean-k-mooney): even with the partial revert of change
        # Iaf15fa7a678ec2624f7c12f634269c465fbad930 this should be correct
        # so this is not removed.
        self.ovsdb.delete_ovs_vif_port(vif.network.bridge, vif.vif_name)

    def _unplug_vf_passthrough(self, vif, instance_info):
        """Remove port from OVS."""
        pci_slot = vif.dev_address
        pf_ifname = linux_net.get_ifname_by_pci_address(pci_slot,
            pf_interface=True, switchdev=True)
        vf_num = linux_net.get_vf_num_by_pci_address(pci_slot)
        representor = linux_net.get_representor_port(pf_ifname, vf_num)
        # The representor interface can't be deleted because it bind the
        # SR-IOV VF, therefore we just need to remove it from the ovs bridge
        # and set the status to down
        self.ovsdb.delete_ovs_vif_port(
            vif.network.bridge, representor, delete_netdev=False)
        linux_net.set_interface_state(representor, 'down')

    def unplug(self, vif, instance_info):
        if not hasattr(vif, "port_profile"):
            raise exception.MissingPortProfile()
        if not isinstance(vif.port_profile,
                          objects.vif.VIFPortProfileOpenVSwitch):
            raise exception.WrongPortProfile(
                profile=vif.port_profile.__class__.__name__)

        if isinstance(vif, objects.vif.VIFOpenVSwitch):
            if sys.platform != constants.PLATFORM_WIN32:
                self._unplug_vif_generic(vif, instance_info)
            else:
                self._unplug_vif_windows(vif, instance_info)
        elif isinstance(vif, objects.vif.VIFBridge):
            if sys.platform != constants.PLATFORM_WIN32:
                self._unplug_bridge(vif, instance_info)
            else:
                self._unplug_vif_windows(vif, instance_info)
        elif isinstance(vif, objects.vif.VIFVHostUser):
            self._unplug_vhostuser(vif, instance_info)
        elif isinstance(vif, objects.vif.VIFHostDevice):
            self._unplug_vf_passthrough(vif, instance_info)
