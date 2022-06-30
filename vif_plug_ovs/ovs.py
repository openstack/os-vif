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

from oslo_config import cfg
from oslo_log import log as logging

from os_vif import exception as osv_exception
from os_vif.internal.ip.api import ip as ip_lib
from os_vif import objects
from os_vif import plugin


from vif_plug_ovs import constants
from vif_plug_ovs import exception
from vif_plug_ovs import linux_net
from vif_plug_ovs.ovsdb import api as ovsdb_api
from vif_plug_ovs.ovsdb import ovsdb_lib

LOG = logging.getLogger(__name__)


class OvsPlugin(plugin.PluginBase):
    """An OVS plugin that can setup VIFs in many ways

    The OVS plugin supports several different VIF types, VIFBridge
    and VIFOpenVSwitch, and will choose the appropriate plugging
    action depending on the type of VIF config it receives.

    If given a VIFBridge, then it will create connect the VM via
    a regular Linux bridge device to allow security group rules to
    be applied to VM traffic.
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
                   default='native',
                   deprecated_for_removal=True,
                   deprecated_since='2.2.0',
                   deprecated_reason="""
                   os-vif has supported ovsdb access via python bindings
                   since Stein (1.15.0), starting in Victoria (2.2.0) the
                   ovs-vsctl driver is now deprecated for removal and
                   in future releases it will be be removed.
                   """,
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
                    'when using the neutron ovs ml2 agent.'),
        cfg.BoolOpt('per_port_bridge', default=False,
                    help='Controls if VIF should be plugged into a per-port '
                    'bridge. This is experimental and controls the plugging '
                    'behavior when not using hybrid-plug.'
                    'This is only used on linux and should be set to false '
                    'in all other cases such as ironic smartnic ports.')
    )

    def __init__(self, config):
        super(OvsPlugin, self).__init__(config)
        self.ovsdb = ovsdb_lib.BaseOVS(self.config)

    @staticmethod
    def gen_port_name(prefix, vif_id, max_length=NIC_NAME_LEN):
        return ("%s%s" % (prefix, vif_id))[:max_length]

    @staticmethod
    def get_veth_pair_names(vif):
        return (OvsPlugin.gen_port_name("qvb", vif.id),
                OvsPlugin.gen_port_name("qvo", vif.id))

    def describe(self):
        pp_ovs = objects.host_info.HostPortProfileInfo(
            profile_object_name=objects.vif.VIFPortProfileOpenVSwitch.__name__,  # noqa
            min_version="1.0",
            max_version="1.0",
        )
        pp_ovs_representor = objects.host_info.HostPortProfileInfo(
            profile_object_name=objects.vif.VIFPortProfileOVSRepresentor.__name__,  # noqa
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
        bridge = kwargs.pop('bridge', vif.network.bridge)
        self.ovsdb.create_ovs_vif_port(
            bridge,
            vif_name,
            vif.port_profile.interface_id,
            vif.address, instance_info.uuid,
            mtu=mtu,
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
        vif_name = OvsPlugin.gen_port_name(
            constants.OVS_VHOSTUSER_PREFIX, vif.id)
        args = {}
        args['datapath_type'] = self._get_vif_datapath_type(vif,
                datapath=constants.OVS_DATAPATH_NETDEV)
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

    def _plug_port_bridge(self, vif, instance_info):
        """Create a per-VIF OVS bridge and patch pair."""

        # NOTE(sean-k-mooney): the port name prefix should not be
        # changed to avoid losing ports on upgrade.
        port_bridge_name = self.gen_port_name('pb', vif.id)
        port_bridge_patch = self.gen_port_name('pbp', vif.id, max_length=64)
        int_bridge_name = vif.network.bridge
        int_bridge_patch = self.gen_port_name('ibp', vif.id, max_length=64)

        self.ovsdb.ensure_ovs_bridge(
             int_bridge_name, self._get_vif_datapath_type(vif))
        self.ovsdb.ensure_ovs_bridge(
            port_bridge_name, self._get_vif_datapath_type(vif))
        self._create_vif_port(
            vif, vif.vif_name, instance_info, bridge=port_bridge_name,
            set_ids=False
        )
        tag = constants.DEAD_VLAN if self.config.isolate_vif else None
        iface_id = vif.id
        mac = vif.address
        instance_id = instance_info.uuid
        LOG.debug(
            'creating patch port pair \n'
            f'{port_bridge_name}:({port_bridge_patch}) -> '
            f'{int_bridge_name}:({int_bridge_patch})'
        )
        self.ovsdb.create_patch_port_pair(
            port_bridge_name, port_bridge_patch, int_bridge_name,
            int_bridge_patch, iface_id, mac, instance_id, tag=tag)

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
        # bug #1734320 and introduces other issues for neutron.
        # this comment will be removed when we actually fix #1734320 in
        # all cases.

        # NOTE(hamdyk): As a WA to the above note, one can use
        # VIFPortProfileOpenVSwitch.create_port flag to explicitly
        # plug the port to the switch.
        if ("create_port" in vif.port_profile and
                vif.port_profile.create_port):
            self._create_vif_port(vif, vif.vif_name, instance_info)

    def _plug_vf(self, vif, instance_info):
        datapath = self._get_vif_datapath_type(vif)
        self.ovsdb.ensure_ovs_bridge(vif.network.bridge, datapath)
        pci_slot = vif.dev_address
        vf_num = linux_net.get_vf_num_by_pci_address(pci_slot)
        args = []
        kwargs = {}
        if datapath == constants.OVS_DATAPATH_SYSTEM:
            pf_ifname = linux_net.get_ifname_by_pci_address(
                pci_slot, pf_interface=True, switchdev=True)
            representor = linux_net.get_representor_port(pf_ifname, vf_num)
            linux_net.set_interface_state(representor, 'up')
            args = [vif, representor, instance_info]
        else:
            representor = linux_net.get_dpdk_representor_port_name(
                vif.id)
            pf_pci = linux_net.get_pf_pci_from_vf(pci_slot)
            args = [vif, representor, instance_info]
            kwargs = {'interface_type': constants.OVS_DPDK_INTERFACE_TYPE,
                      'pf_pci': pf_pci,
                      'vf_num': vf_num}
        self._create_vif_port(*args, **kwargs)

    def plug(self, vif, instance_info):
        if not hasattr(vif, "port_profile"):
            raise exception.MissingPortProfile()
        if not isinstance(vif.port_profile,
                          objects.vif.VIFPortProfileOpenVSwitch):
            raise exception.WrongPortProfile(
                profile=vif.port_profile.__class__.__name__)

        if sys.platform == constants.PLATFORM_WIN32:
            if type(vif) not in (
                objects.vif.VIFOpenVSwitch, objects.vif.VIFBridge
            ):
                raise osv_exception.PlugException(
                    vif=vif, err="This vif type is not supported on Windows")

            self._plug_vif_windows(vif, instance_info)
        elif isinstance(vif, objects.vif.VIFOpenVSwitch):
            if self.config.per_port_bridge:
                self._plug_port_bridge(vif, instance_info)
            else:
                self._plug_vif_generic(vif, instance_info)
        elif isinstance(vif, objects.vif.VIFBridge):
            self._plug_bridge(vif, instance_info)
        elif isinstance(vif, objects.vif.VIFVHostUser):
            self._plug_vhostuser(vif, instance_info)
        elif isinstance(vif, objects.vif.VIFHostDevice):
            self._plug_vf(vif, instance_info)
        else:
            # This should never be raised.
            raise osv_exception.PlugException(
                vif=vif,
                err="This vif type is not supported by this plugin")

    def _is_trunk_bridge(self, bridge_name):
        return bridge_name.startswith(constants.TRUNK_BR_PREFIX)

    def _delete_bridge_if_trunk(self, vif):
        if self._is_trunk_bridge(vif.network.bridge):
            self.ovsdb.delete_ovs_bridge(vif.network.bridge)

    def _unplug_vhostuser(self, vif, instance_info):
        self.ovsdb.delete_ovs_vif_port(vif.network.bridge,
            OvsPlugin.gen_port_name(
                constants.OVS_VHOSTUSER_PREFIX,
                vif.id))
        self._delete_bridge_if_trunk(vif)

    def _unplug_bridge(self, vif, instance_info, linux_bridge_name):
        """UnPlug using hybrid strategy

        Unhook port from OVS, unhook port from bridge, delete
        bridge, and delete both veth devices.
        """

        v1_name, v2_name = self.get_veth_pair_names(vif)

        linux_net.delete_bridge(linux_bridge_name, v1_name)

        self.ovsdb.delete_ovs_vif_port(vif.network.bridge, v2_name)
        self._delete_bridge_if_trunk(vif)

    def _unplug_vif_windows(self, vif, instance_info):
        """Remove port from OVS."""
        self.ovsdb.delete_ovs_vif_port(vif.network.bridge, vif.id,
                                       delete_netdev=False)
        self._delete_bridge_if_trunk(vif)

    def _unplug_port_bridge(self, vif, instance_info):
        """Create a per-VIF OVS bridge and patch pair."""
        # NOTE(sean-k-mooney): the port name prefix should not be
        # changed to avoid loosing ports on upgrade.
        port_bridge_name = self.gen_port_name('pb', vif.id)
        port_bridge_patch = self.gen_port_name('pbp', vif.id, max_length=64)
        int_bridge_patch = self.gen_port_name('ibp', vif.id, max_length=64)
        self.ovsdb.delete_ovs_vif_port(vif.network.bridge, int_bridge_patch)
        self.ovsdb.delete_ovs_vif_port(port_bridge_name, port_bridge_patch)
        self.ovsdb.delete_ovs_vif_port(port_bridge_name, vif.vif_name)
        self.ovsdb.delete_ovs_bridge(port_bridge_name)
        self._delete_bridge_if_trunk(vif)

    def _unplug_vif_generic(self, vif, instance_info):
        """Remove port from OVS."""
        # NOTE(sean-k-mooney): even with the partial revert of change
        # Iaf15fa7a678ec2624f7c12f634269c465fbad930 this should be correct
        # so this is not removed.
        self.ovsdb.delete_ovs_vif_port(vif.network.bridge, vif.vif_name)
        self._delete_bridge_if_trunk(vif)

    def _unplug_vf(self, vif):
        """Remove port from OVS."""
        datapath = self._get_vif_datapath_type(vif)
        if datapath == constants.OVS_DATAPATH_SYSTEM:
            pci_slot = vif.dev_address
            pf_ifname = linux_net.get_ifname_by_pci_address(
                pci_slot, pf_interface=True, switchdev=True)
            vf_num = linux_net.get_vf_num_by_pci_address(pci_slot)
            representor = linux_net.get_representor_port(pf_ifname, vf_num)
        else:
            representor = linux_net.get_dpdk_representor_port_name(
                vif.id)

        # The representor interface can't be deleted because it bind the
        # SR-IOV VF, therefore we just need to remove it from the ovs bridge
        # and set the status to down
        self.ovsdb.delete_ovs_vif_port(
            vif.network.bridge, representor, delete_netdev=False)
        if datapath == constants.OVS_DATAPATH_SYSTEM:
            linux_net.set_interface_state(representor, 'down')
        self._delete_bridge_if_trunk(vif)

    def unplug(self, vif, instance_info):
        if not hasattr(vif, "port_profile"):
            raise exception.MissingPortProfile()
        if not isinstance(vif.port_profile,
                          objects.vif.VIFPortProfileOpenVSwitch):
            raise exception.WrongPortProfile(
                profile=vif.port_profile.__class__.__name__)
        if sys.platform == constants.PLATFORM_WIN32:
            if type(vif) not in (
                objects.vif.VIFOpenVSwitch, objects.vif.VIFBridge
            ):
                raise osv_exception.UnplugException(
                    vif=vif, err="This vif type is not supported on windows.")
            self._unplug_vif_windows(vif, instance_info)
        elif isinstance(vif, objects.vif.VIFOpenVSwitch):
            if self.config.per_port_bridge:
                self._unplug_port_bridge(vif, instance_info)
            else:
                linux_bridge_name = self.gen_port_name('qbr', vif.id)
                if ip_lib.exists(linux_bridge_name):
                    self._unplug_bridge(vif, instance_info, linux_bridge_name)
                else:
                    self._unplug_vif_generic(vif, instance_info)
        elif isinstance(vif, objects.vif.VIFBridge):
            self._unplug_bridge(vif, instance_info, vif.bridge_name)
        elif isinstance(vif, objects.vif.VIFVHostUser):
            self._unplug_vhostuser(vif, instance_info)
        elif isinstance(vif, objects.vif.VIFHostDevice):
            self._unplug_vf(vif)
        else:
            # this should never be raised.
            raise osv_exception.UnplugException(
                vif=vif,
                err="This vif type is not supported by this plugin")
