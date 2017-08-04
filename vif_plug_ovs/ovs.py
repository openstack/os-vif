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

from os_vif import objects
from os_vif import plugin
from oslo_config import cfg

from vif_plug_ovs import constants
from vif_plug_ovs import exception
from vif_plug_ovs import linux_net


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
    )

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
        linux_net.create_ovs_vif_port(
            vif.network.bridge,
            vif_name,
            vif.port_profile.interface_id,
            vif.address, instance_info.uuid,
            mtu,
            timeout=self.config.ovs_vsctl_timeout,
            **kwargs)

    def _update_vif_port(self, vif, vif_name):
        mtu = self._get_mtu(vif)
        linux_net.update_ovs_vif_port(vif_name, mtu)

    @staticmethod
    def _get_vif_datapath_type(vif, datapath=constants.OVS_DATAPATH_SYSTEM):
        profile = vif.port_profile
        if 'datapath_type' not in profile or not profile.datapath_type:
            return datapath
        return profile.datapath_type

    def _plug_vhostuser(self, vif, instance_info):
        linux_net.ensure_ovs_bridge(
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
        if not linux_net.device_exists(v2_name):
            linux_net.create_veth_pair(v1_name, v2_name, mtu)
            linux_net.add_bridge_port(vif.bridge_name, v1_name)
            linux_net.ensure_ovs_bridge(vif.network.bridge,
                                        self._get_vif_datapath_type(vif))
            self._create_vif_port(vif, v2_name, instance_info)
        else:
            linux_net.update_veth_pair(v1_name, v2_name, mtu)
            self._update_vif_port(vif, v2_name)

    def _plug_vif_windows(self, vif, instance_info):
        """Create a per-VIF OVS port."""

        if not linux_net.device_exists(vif.id):
            linux_net.ensure_ovs_bridge(vif.network.bridge,
                                        self._get_vif_datapath_type(vif))
            self._create_vif_port(vif, vif.id, instance_info)

    def _plug_vf_passthrough(self, vif, instance_info):
        linux_net.ensure_ovs_bridge(
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
                linux_net.ensure_ovs_bridge(vif.network.bridge,
                                            self._get_vif_datapath_type(vif))
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
        linux_net.delete_ovs_vif_port(vif.network.bridge,
                                      OvsPlugin.gen_port_name(
                                          constants.OVS_VHOSTUSER_PREFIX,
                                          vif.id),
                                      timeout=self.config.ovs_vsctl_timeout)

    def _unplug_bridge(self, vif, instance_info):
        """UnPlug using hybrid strategy

        Unhook port from OVS, unhook port from bridge, delete
        bridge, and delete both veth devices.
        """

        v1_name, v2_name = self.get_veth_pair_names(vif)

        linux_net.delete_bridge(vif.bridge_name, v1_name)

        linux_net.delete_ovs_vif_port(vif.network.bridge, v2_name,
                                      timeout=self.config.ovs_vsctl_timeout)

    def _unplug_vif_windows(self, vif, instance_info):
        """Remove port from OVS."""

        linux_net.delete_ovs_vif_port(vif.network.bridge, vif.id,
                                      timeout=self.config.ovs_vsctl_timeout)

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
        linux_net.delete_ovs_vif_port(
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
            if sys.platform == constants.PLATFORM_WIN32:
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
