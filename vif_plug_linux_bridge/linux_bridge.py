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

from vif_plug_linux_bridge import iptables
from vif_plug_linux_bridge import linux_net


class LinuxBridgePlugin(plugin.PluginBase):
    """A VIF type that uses a standard Linux bridge device."""

    CONFIG_OPTS = (
        cfg.BoolOpt('use_ipv6',
                    default=False,
                    help='Use IPv6',
                    deprecated_group="DEFAULT"),

        cfg.StrOpt('iptables_top_regex',
                   default='',
                   help='Regular expression to match the iptables rule that '
                   'should always be on the top.',
                   deprecated_group="DEFAULT"),
        cfg.StrOpt('iptables_bottom_regex',
                   default='',
                   help='Regular expression to match the iptables rule that '
                   'should always be on the bottom.',
                   deprecated_group="DEFAULT"),
        cfg.StrOpt('iptables_drop_action',
                   default='DROP',
                   help='The table that iptables to jump to when a packet is '
                   'to be dropped.',
                   deprecated_group="DEFAULT"),

        cfg.MultiStrOpt('forward_bridge_interface',
                        default=['all'],
                        help='An interface that bridges can forward to. If '
                        'this is set to all then all traffic will be '
                        'forwarded. Can be specified multiple times.',
                        deprecated_group="DEFAULT"),
        cfg.StrOpt('vlan_interface',
                   help='VLANs will bridge into this interface if set',
                   deprecated_group="DEFAULT"),
        cfg.StrOpt('flat_interface',
                   help='FlatDhcp will bridge into this interface if set',
                   deprecated_group="DEFAULT"),
        cfg.IntOpt('network_device_mtu',
                   default=1500,
                   help='MTU setting for network interface.',
                   deprecated_group="DEFAULT"),
    )

    def __init__(self, config):
        super(LinuxBridgePlugin, self).__init__(config)

        ipm = iptables.IptablesManager(
            use_ipv6=config.use_ipv6,
            iptables_top_regex=config.iptables_top_regex,
            iptables_bottom_regex=config.iptables_bottom_regex,
            iptables_drop_action=config.iptables_drop_action,
            forward_bridge_interface=config.forward_bridge_interface)

        linux_net.configure(ipm)

    def describe(self):
        return objects.host_info.HostPluginInfo(
            plugin_name="linux_bridge",
            vif_info=[
                objects.host_info.HostVIFInfo(
                    vif_object_name=objects.vif.VIFBridge.__name__,
                    min_version="1.0",
                    max_version="1.0")
            ])

    def plug(self, vif, instance_info):
        """Ensure that the bridge exists, and add VIF to it."""
        network = vif.network
        bridge_name = vif.bridge_name
        if not network.multi_host and network.should_provide_bridge:
            mtu = network.mtu or self.config.network_device_mtu
            if network.should_provide_vlan:
                iface = self.config.vlan_interface or network.bridge_interface
                linux_net.ensure_vlan_bridge(network.vlan,
                                             bridge_name, iface, mtu=mtu)
            else:
                iface = self.config.flat_interface or network.bridge_interface
                # only put in iptables rules if Neutron not filtering
                install_filters = not vif.has_traffic_filtering
                linux_net.ensure_bridge(bridge_name, iface,
                                        filtering=install_filters, mtu=mtu)

    def unplug(self, vif, instance_info):
        # Nothing required to unplug a port for a VIF using standard
        # Linux bridge device...
        pass
