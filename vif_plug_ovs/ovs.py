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

from os_vif import objects
from os_vif import plugin
from oslo_config import cfg

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
    def get_veth_pair_names(vif):
        iface_id = vif.id
        return (("qvb%s" % iface_id)[:OvsPlugin.NIC_NAME_LEN],
                ("qvo%s" % iface_id)[:OvsPlugin.NIC_NAME_LEN])

    def describe(self):
        return objects.host_info.HostPluginInfo(
            plugin_name="ovs_hybrid",
            vif_info=[
                objects.host_info.HostVIFInfo(
                    vif_object_name=objects.vif.VIFBridge.__name__,
                    min_version="1.0",
                    max_version="1.0"),
                objects.host_info.HostVIFInfo(
                    vif_object_name=objects.vif.VIFOpenVSwitch.__name__,
                    min_version="1.0",
                    max_version="1.0")
            ])

    def _plug_bridge(self, vif, instance_info):
        """Plug using hybrid strategy

        Create a per-VIF linux bridge, then link that bridge to the OVS
        integration bridge via a veth device, setting up the other end
        of the veth device just like a normal OVS port. Then boot the
        VIF on the linux bridge using standard libvirt mechanisms.
        """

        v1_name, v2_name = self.get_veth_pair_names(vif)

        linux_net.ensure_bridge(vif.bridge_name)

        if not linux_net.device_exists(v2_name):
            linux_net.create_veth_pair(v1_name, v2_name,
                                       self.config.network_device_mtu)
            linux_net.add_bridge_port(vif.bridge_name, v1_name)
            linux_net.create_ovs_vif_port(
                vif.network.bridge,
                v2_name,
                vif.port_profile.interface_id,
                vif.address, instance_info.uuid,
                self.config.network_device_mtu,
                timeout=self.config.ovs_vsctl_timeout)

    def plug(self, vif, instance_info):
        if not hasattr(vif, "port_profile"):
            raise exception.MissingPortProfile()
        if not isinstance(vif.port_profile,
                          objects.vif.VIFPortProfileOpenVSwitch):
            raise exception.WrongPortProfile(
                profile=vif.port_profile.__class__.__name__)

        if isinstance(vif, objects.vif.VIFBridge):
            self._plug_bridge(vif, instance_info)

    def _unplug_bridge(self, vif, instance_info):
        """UnPlug using hybrid strategy

        Unhook port from OVS, unhook port from bridge, delete
        bridge, and delete both veth devices.
        """

        v1_name, v2_name = self.get_veth_pair_names(vif)

        linux_net.delete_bridge(vif.bridge_name, v1_name)

        linux_net.delete_ovs_vif_port(vif.network.bridge, v2_name,
                                      timeout=self.config.ovs_vsctl_timeout)

    def unplug(self, vif, instance_info):
        if not hasattr(vif, "port_profile"):
            raise exception.MissingPortProfile()
        if not isinstance(vif.port_profile,
                          objects.vif.VIFPortProfileOpenVSwitch):
            raise exception.WrongPortProfile(
                profile=vif.port_profile.__class__.__name__)

        if isinstance(vif, objects.vif.VIFBridge):
            self._unplug_bridge(vif, instance_info)
