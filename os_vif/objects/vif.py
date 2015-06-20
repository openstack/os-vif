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

from oslo_versionedobjects import base
from oslo_versionedobjects import fields

from os_vif import vnic_types

# Constants for dictionary keys in the 'vif_details' field in the VIF
# class
VIF_DETAILS_OVS_HYBRID_PLUG = 'ovs_hybrid_plug'
VIF_DETAILS_PHYSICAL_NETWORK = 'physical_network'

# The following two constants define the SR-IOV related fields in the
# 'vif_details'. 'profileid' should be used for VIF_TYPE_802_QBH,
# 'vlan' for VIF_TYPE_HW_VEB
VIF_DETAILS_PROFILEID = 'profileid'
VIF_DETAILS_VLAN = 'vlan'

# Constants for vhost-user related fields in 'vif_details'.
# vhost-user socket path
VIF_DETAILS_VHOSTUSER_SOCKET = 'vhostuser_socket'
# Specifies whether vhost-user socket should be plugged
# into ovs bridge. Valid values are True and False
VIF_DETAILS_VHOSTUSER_OVS_PLUG = 'vhostuser_ovs_plug'
# Constants for vhost-user related fields in 'vif_details'.
# Sets mode on vhost-user socket, valid values are 'client'
# and 'server'
VIF_DETAILS_VHOSTUSER_MODE = 'vhostuser_mode'

# Constant for max length of network interface names
# eg 'bridge' in the Network class or 'devname' in
# the VIF class
_NIC_NAME_LEN = 14


class VIF(base.VersionedObject):
    """Represents a virtual network interface."""
    # Version 1.0: Initial version
    VERSION = '1.0'

    fields = {
        'id': fields.UUIDField(),
        'instance_info': fields.ObjectField('InstanceInfo'),
        'ovs_interfaceid': fields.StringField(),
        # MAC address
        'address': fields.StringField(nullable=True),
        'network': fields.ObjectField('Network', nullable=True),
        # The name or alias of the plugin that should handle the VIF
        'plugin': fields.StringField(),
        'details': fields.DictOfStringsField(nullable=True),
        'profile': fields.DictOfStringsField(nullable=True),
        'devname': fields.StringField(nullable=True),
        'vnic_type': fields.StringField(),
        'active': fields.BooleanField(),
        'preserve_on_delete': fields.BooleanField(),
    }

    def __init__(self, id=None, address=None, network=None, plugin=None,
                 details=None, devname=None, ovs_interfaceid=None,
                 qbh_params=None, qbg_params=None, active=False,
                 vnic_type=vnic_types.NORMAL, profile=None,
                 preserve_on_delete=False, instance_info=None):
        details = details or {}
        ovs_id = ovs_interfaceid or id
        if not devname:
            devname = ("nic" + id)[:_NIC_NAME_LEN]
        super(VIF, self).__init__(id=id, address=address, network=network,
                                  plugin=plugin, details=details,
                                  devname=devname,
                                  ovs_interfaceid=ovs_id,
                                  qbg_params=qbg_params, qbh_params=qbh_params,
                                  active=active, vnic_type=vnic_type,
                                  profile=profile,
                                  preserve_on_delete=preserve_on_delete,
                                  instance_info=instance_info,
                                  )

    def devname_with_prefix(self, prefix):
        """Returns the device name for the VIF, with the a replaced prefix."""
        return prefix + self.devname[3:]

    # TODO(jaypipes): It's silly that there is a br_name and a (different)
    # bridge_name attribute, but this comes from the original libvirt/vif.py.
    # Clean this up and use better names for the attributes.
    @property
    def bridge_name(self):
        return self.network.bridge

    @property
    def br_name(self):
        return ("qbr" + self.id)[:_NIC_NAME_LEN]

    @property
    def veth_pair_names(self):
        return (("qvb%s" % self.id)[:_NIC_NAME_LEN],
                ("qvo%s" % self.id)[:_NIC_NAME_LEN])

    @property
    def ovs_hybrid_plug(self):
        return self.details.get(VIF_DETAILS_OVS_HYBRID_PLUG, False)

    @property
    def physical_network(self):
        phy_network = self.network['meta'].get('physical_network')
        if not phy_network:
            phy_network = self.details.get(VIF_DETAILS_PHYSICAL_NETWORK)
        return phy_network

    @property
    def profileid(self):
        return self.details.get(VIF_DETAILS_PROFILEID)

    @property
    def vlan(self):
        return self.details.get(VIF_DETAILS_VLAN)

    @property
    def vhostuser_mode(self):
        return self.details.get(VIF_DETAILS_VHOSTUSER_MODE)

    @property
    def vhostuser_socket(self):
        return self.details.get(VIF_DETAILS_VHOSTUSER_SOCKET)

    @property
    def vhostuser_ovs_plug(self):
        return self.details.get(VIF_DETAILS_VHOSTUSER_OVS_PLUG)

    @property
    def fixed_ips(self):
        return [fixed_ip for subnet in self.network['subnets']
                for fixed_ip in subnet['ips']]

    @property
    def floating_ips(self):
        return [floating_ip for fixed_ip in self.fixed_ips
                for floating_ip in fixed_ip['floating_ips']]
