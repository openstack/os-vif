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

from oslo_utils import versionutils
from oslo_versionedobjects import base
from oslo_versionedobjects import fields

from os_vif.objects import base as osv_base
from os_vif.objects import fields as osv_fields


@base.VersionedObjectRegistry.register
class VIFBase(osv_base.VersionedObject, base.ComparableVersionedObject):
    """Represents a virtual network interface."""
    # Version 1.0: Initial version
    VERSION = '1.0'

    fields = {
        # Unique identifier of the VIF port
        'id': fields.UUIDField(),

        # The guest MAC address
        'address': fields.MACAddressField(nullable=True),

        # The network to which the VIF is connected
        'network': fields.ObjectField('Network', nullable=True),

        # Name of the registered os_vif plugin
        'plugin': fields.StringField(),

        # Whether the VIF is initially online
        'active': fields.BooleanField(default=True),

        # Whether the host VIF should be preserved on unplug
        'preserve_on_delete': fields.BooleanField(default=False),

        # Whether the network service has provided traffic filtering
        'has_traffic_filtering': fields.BooleanField(default=False),

        # The virtual port profile metadata
        'port_profile': fields.ObjectField('VIFPortProfileBase',
                                           subclasses=True)
    }


@base.VersionedObjectRegistry.register
class VIFGeneric(VIFBase):
    # For libvirt drivers, this maps to type="ethernet" which
    # just implies a bare TAP device, all setup delegated to
    # the plugin

    VERSION = '1.0'

    fields = {
        # Name of the device to create
        'vif_name': fields.StringField()
    }


@base.VersionedObjectRegistry.register
class VIFBridge(VIFBase):
    # For libvirt drivers, this maps to type='bridge'

    VERSION = '1.0'

    fields = {
        # Name of the virtual device to create
        'vif_name': fields.StringField(),

        # Name of the physical device to connect to (eg br0)
        'bridge_name': fields.StringField(),
    }


@base.VersionedObjectRegistry.register
class VIFOpenVSwitch(VIFBase):
    # For libvirt drivers, this also maps to type='bridge'

    VERSION = '1.0'

    fields = {
        # Name of the virtual device to create
        'vif_name': fields.StringField(),

        # Name of the physical device to connect to (eg br0)
        'bridge_name': fields.StringField(),
    }


@base.VersionedObjectRegistry.register
class VIFDirect(VIFBase):
    # For libvirt drivers, this maps to type='direct'

    VERSION = '1.0'

    fields = {
        # Name of the device to create
        'vif_name': fields.StringField(),

        # The PCI address of the host device
        'dev_address': fields.PCIAddressField(),

        # Port connection mode
        'mode': osv_fields.VIFDirectModeField(),

        # The VLAN device name to use
        'vlan_name': fields.StringField(),
    }


@base.VersionedObjectRegistry.register
class VIFVHostUser(VIFBase):
    # For libvirt drivers, this maps to type='vhostuser'

    VERSION = '1.1'

    fields = {
        # Name of the vhostuser port to create
        'vif_name': fields.StringField(),

        # UNIX socket path
        'path': fields.StringField(),

        # UNIX socket access permissions
        'mode': osv_fields.VIFVHostUserModeField(),
    }

    def obj_make_compatible(self, primitive, target_version):
        super(VIFVHostUser, self).obj_make_compatible(primitive,
                                                      target_version)
        target_version = versionutils.convert_version_to_tuple(target_version)
        if target_version < (1, 1) and 'vif_name' in primitive:
            del primitive['vif_name']


@base.VersionedObjectRegistry.register
class VIFHostDevice(VIFBase):
    # For libvirt drivers, this maps to type='hostdev'

    VERSION = '1.0'

    fields = {

        # The type of the host device.
        # Valid values are ethernet and generic.
        # Ethernet is <interface type='hostdev'>
        # Generic is <hostdev mode='subsystem' type='pci'>
        'dev_type': osv_fields.VIFHostDeviceDevTypeField(),

        # The PCI address of the host device
        'dev_address': fields.PCIAddressField(),
    }


@base.VersionedObjectRegistry.register
class VIFPortProfileBase(osv_base.VersionedObject,
                         base.ComparableVersionedObject):
    # Base class for all types of port profile
    VERSION = '1.0'


@base.VersionedObjectRegistry.register
class VIFPortProfileOpenVSwitch(VIFPortProfileBase):
    # Port profile info for OpenVSwitch networks

    VERSION = '1.0'

    fields = {
        'interface_id': fields.UUIDField(),
        'profile_id': fields.StringField(),
    }


@base.VersionedObjectRegistry.register
class VIFPortProfileFPOpenVSwitch(VIFPortProfileOpenVSwitch):
    # Port profile info for OpenVSwitch networks using fastpath

    VERSION = '1.0'

    fields = {
        # Name of the bridge (managed by fast path) to connect to
        'bridge_name': fields.StringField(),

        # Whether the OpenVSwitch network is using hybrid plug
        'hybrid_plug': fields.BooleanField(default=False),
    }


@base.VersionedObjectRegistry.register
class VIFPortProfileOVSRepresentor(VIFPortProfileOpenVSwitch):
    # Port profile info for OpenVSwitch networks using a representor

    VERSION = '1.0'

    fields = {
        # Name to set on the representor (if set)
        'representor_name': fields.StringField(nullable=True),

        # The PCI address of the Virtual Function
        'representor_address': fields.PCIAddressField(nullable=True),
    }


@base.VersionedObjectRegistry.register
class VIFPortProfileFPBridge(VIFPortProfileBase):
    # Port profile info for LinuxBridge networks using fastpath

    VERSION = '1.0'

    fields = {
        # Name of the bridge (managed by fast path) to connect to
        'bridge_name': fields.StringField(),
    }


@base.VersionedObjectRegistry.register
class VIFPortProfileFPTap(VIFPortProfileBase):
    # Port profile info for Calico networks using fastpath

    VERSION = '1.0'

    fields = {
        # The mac address of the host vhostuser port
        'mac_address': fields.MACAddressField(nullable=True),
    }


@base.VersionedObjectRegistry.register
class VIFPortProfile8021Qbg(VIFPortProfileBase):
    # Port profile info for VEPA 802.1qbg networks

    VERSION = '1.0'

    fields = {
        'manager_id': fields.IntegerField(),
        'type_id': fields.IntegerField(),
        'type_id_version': fields.IntegerField(),
        'instance_id': fields.UUIDField(),
    }


@base.VersionedObjectRegistry.register
class VIFPortProfile8021Qbh(VIFPortProfileBase):
    # Port profile info for VEPA 802.1qbh networks

    VERSION = '1.0'

    fields = {
        'profile_id': fields.StringField()
    }
