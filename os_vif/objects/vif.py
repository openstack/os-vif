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

from debtcollector import removals

from oslo_utils import versionutils
from oslo_versionedobjects import base
from oslo_versionedobjects import fields

from os_vif.objects import base as osv_base
from os_vif.objects import fields as osv_fields


@base.VersionedObjectRegistry.register
class VIFBase(osv_base.VersionedObject, base.ComparableVersionedObject):
    """Represents a virtual network interface.

    The base VIF defines fields that are common to all types of VIF and
    provides an association to the network the VIF is plugged into. It should
    not be instantiated itself - use a subclass instead.
    """

    # Version 1.0: Initial release
    VERSION = '1.0'

    fields = {
        #: Unique identifier of the VIF port.
        'id': fields.UUIDField(),

        #: The guest MAC address.
        'address': fields.MACAddressField(nullable=True),

        #: The network to which the VIF is connected.
        'network': fields.ObjectField('Network', nullable=True),

        #: Name of the registered os_vif plugin.
        'plugin': fields.StringField(),

        #: Whether the VIF is initially online.
        'active': fields.BooleanField(default=True),

        #: Whether the host VIF should be preserved on unplug.
        'preserve_on_delete': fields.BooleanField(default=False),

        #: Whether the network service has provided traffic filtering.
        'has_traffic_filtering': fields.BooleanField(default=False),

        #: The virtual port profile metadata.
        'port_profile': fields.ObjectField('VIFPortProfileBase',
                                           subclasses=True)
    }


@base.VersionedObjectRegistry.register
class VIFGeneric(VIFBase):
    """A generic-style VIF.

    Generic-style VIFs are unbound, floating TUN/TAP devices that should be
    setup by the plugin, not the hypervisor. The way the TAP device is
    connected to the host network stack is explicitly left undefined.

    For libvirt drivers, this maps to type="ethernet" which just implies a bare
    TAP device with all setup delegated to the plugin.
    """

    # Version 1.0: Initial release
    VERSION = '1.0'

    fields = {
        #: Name of the device to create.
        'vif_name': fields.StringField()
    }


@base.VersionedObjectRegistry.register
class VIFBridge(VIFBase):
    """A bridge-style VIF.

    Bridge-style VIFs are bound to a Linux host bridge by the hypervisor. This
    provides Ethernet layer bridging, typically to the LAN. Other devices may
    be bound to the same L2 virtual bridge.

    For libvirt drivers, this maps to type='bridge'.
    """

    # Version 1.0: Initial release
    VERSION = '1.0'

    fields = {
        #: Name of the virtual device to create.
        'vif_name': fields.StringField(),

        #: Name of the physical device to connect to (e.g. ``br0``).
        'bridge_name': fields.StringField(),
    }


@base.VersionedObjectRegistry.register
class VIFOpenVSwitch(VIFBase):
    """A bridge-style VIF specifically for use with OVS.

    Open vSwitch VIFs are bound directly (or indirectly) to an Open vSwitch
    bridge by the hypervisor. Other devices may be bound to the same virtual
    bridge.

    For libvirt drivers, this also maps to type='bridge'.
    """

    # Version 1.0: Initial release
    VERSION = '1.0'

    fields = {
        #: Name of the virtual device to create.
        'vif_name': fields.StringField(),

        #: Name of the physical device to connect to (e.g. ``br0``).
        'bridge_name': fields.StringField(),
    }


@base.VersionedObjectRegistry.register
class VIFDirect(VIFBase):
    """A direct-style VIF.

    Despite the confusing name, direct-style VIFs utilize macvtap which is a
    device driver that inserts a software layer between a guest and an SR-IOV
    Virtual Function (VF). Contrast this with
    :class:`~os_vif.objects.vif.VIFHostDevice`, which allows the guest to
    directly connect to the VF.

    The connection to the device may operate in one of a number of different
    modes, :term:`VEPA` (either :term:`802.1Qbg` or :term:`802.1Qbh`),
    passthrough (exclusive assignment of the host NIC) or bridge (ethernet
    layer bridging of traffic). The passthrough mode would be used when there
    is a network device which needs to have a MAC address or VLAN
    configuration. For passthrough of network devices without MAC/VLAN
    configuration, :class:`~os_vif.objects.vif.VIFHostDevice` should be used
    instead.

    For libvirt drivers, this maps to type='direct'
    """

    # Version 1.0: Initial release
    VERSION = '1.0'

    fields = {
        #: Name of the device to create.
        'vif_name': fields.StringField(),

        #: The PCI address of the host device.
        'dev_address': fields.PCIAddressField(),

        #: Port connection mode.
        'mode': osv_fields.VIFDirectModeField(),

        #: The VLAN device name to use.
        'vlan_name': fields.StringField(),
    }


@base.VersionedObjectRegistry.register
class VIFVHostUser(VIFBase):
    """A vhostuser-style VIF.

    vhostuser-style VIFs utilize a :term:`userspace vhost <vhost-user>`
    backend, which allows traffic to traverse between the guest and a host
    userspace application (commonly a virtual switch), bypassing the kernel
    network stack. Contrast this with :class:`~os_vif.objects.vif.VIFBridge`,
    where all packets must be handled by the hypervisor.

    For libvirt drivers, this maps to type='vhostuser'
    """

    # Version 1.0: Initial release
    # Version 1.1: Added 'vif_name'
    VERSION = '1.1'

    fields = {
        #: Name of the vhostuser port to create.
        'vif_name': fields.StringField(),

        #: UNIX socket path.
        'path': fields.StringField(),

        #: UNIX socket access permissions.
        'mode': osv_fields.VIFVHostUserModeField(),
    }

    def obj_make_compatible(self, primitive, target_version):
        target_version = versionutils.convert_version_to_tuple(target_version)
        if target_version < (1, 1) and 'vif_name' in primitive:
            del primitive['vif_name']
        super(VIFVHostUser, self).obj_make_compatible(primitive, '1.0')


@base.VersionedObjectRegistry.register
class VIFHostDevice(VIFBase):
    """A hostdev-style VIF.

    Hostdev-style VIFs provide a guest with direct access to an :term:`SR-IOV`
    :term:`Virtual Function` (VF) or an entire :term:`Physical Function` (PF).
    Contrast this with :class:`~ovs_vif.objects.vif.VIFDirect`, which includes
    a software layer between the interface and the guest.

    For libvirt drivers, this maps to type='hostdev'
    """

    # Version 1.0: Initial release
    VERSION = '1.0'

    fields = {
        #: The type of the host device.
        #:
        #: Valid values are ``ethernet`` and ``generic``.
        #:
        #: - ``ethernet`` is ``<interface type='hostdev'>``
        #: - ``generic`` is ``<hostdev mode='subsystem' type='pci'>``
        'dev_type': osv_fields.VIFHostDeviceDevTypeField(),

        #: The PCI address of the host device.
        'dev_address': fields.PCIAddressField(),
    }


@base.VersionedObjectRegistry.register
class VIFNestedDPDK(VIFBase):
    """A nested DPDK-style VIF.

    Nested DPDK-style VIFs are used by Kuryr-Kubernetes to provide accelerated
    DPDK datapath for nested Kubernetes pods running inside the VM. The port
    is first attached to the virtual machine, bound to the userspace driver
    (e.g. ``uio_pci_generic``, ``igb_uio`` or ``vfio-pci``) and then consumed
    by Kubernetes pod via the kuryr-kubernetes CNI plugin.

    This does not apply to libvirt drivers.
    """

    # Version 1.0: Initial release
    VERSION = '1.0'

    fields = {
        #: PCI address of the device.
        'pci_address': fields.StringField(),

        #: Name of the driver the device was previously bound to; it makes
        #: the controller driver agnostic (virtio, SR-IOV, etc.).
        'dev_driver': fields.StringField(),
    }


@base.VersionedObjectRegistry.register
class DatapathOffloadBase(osv_base.VersionedObject,
                          base.ComparableVersionedObject):
    """Base class for all types of datapath offload."""

    # Version 1.0: Initial release
    VERSION = '1.0'


@base.VersionedObjectRegistry.register
class DatapathOffloadRepresentor(DatapathOffloadBase):
    """Offload type for VF Representors conforming to the switchdev model.

    This datapath offloads provides the metadata required to associate a VIF
    with a :term:`VF` representor conforming to the `switchdev`_ kernel model.
    If ``representor_name`` is specified, it indicates a desire to rename the
    representor to the given name on plugging.

    .. _switchdev: https://netdevconf.org/1.2/session.html?or-gerlitz
    """

    # Version 1.0: Initial release
    VERSION = '1.0'

    fields = {
        #: Name to set on the representor (if set).
        'representor_name': fields.StringField(nullable=True),

        #: The PCI address of the Virtual Function.
        'representor_address': fields.StringField(nullable=True),
    }


@base.VersionedObjectRegistry.register
class VIFPortProfileBase(osv_base.VersionedObject,
                         base.ComparableVersionedObject):
    """Base class for all types of port profile.

    The base profile defines fields that are common to all types of profile. It
    should not be instantiated itself - use a subclass instead.
    """

    # Version 1.0: Initial release
    # Version 1.1: Added 'datapath_offload'
    VERSION = '1.1'

    fields = {
        #: Datapath offload type of the port.
        'datapath_offload': fields.ObjectField('DatapathOffloadBase',
                                               nullable=True,
                                               subclasses=True),
    }

    obj_relationships = {
        'datapath_offload': (('1.1', '1.0'),),
    }


@base.VersionedObjectRegistry.register
class VIFPortProfileOpenVSwitch(VIFPortProfileBase):
    """Port profile info for Open vSwitch networks.

    This profile provides the metadata required to associate a VIF with an Open
    vSwitch interface.
    """

    # Version 1.0: Initial release
    # Version 1.1: Added 'datapath_type'
    # Version 1.2: VIFPortProfileBase updated to 1.1 from 1.0
    # Version 1.3: Added 'create_port'
    VERSION = '1.3'

    fields = {
        #: A UUID to uniquely identify the interface. If omitted one will be
        #: generated automatically.
        'interface_id': fields.UUIDField(),

        #: The OpenVSwitch port profile for the interface.
        'profile_id': fields.StringField(),

        #: Datapath type of the bridge.
        'datapath_type': fields.StringField(nullable=True),

        #: Whether the os-vif plugin should add the port to the bridge.
        'create_port': fields.BooleanField(default=False),
    }

    def obj_make_compatible(self, primitive, target_version):
        target_version = versionutils.convert_version_to_tuple(target_version)
        if target_version < (1, 3) and 'create_port' in primitive:
            del primitive['create_port']
        if target_version < (1, 1) and 'datapath_type' in primitive:
            del primitive['datapath_type']
        if target_version < (1, 2):
            super(VIFPortProfileOpenVSwitch, self).obj_make_compatible(
                primitive, '1.0')
        else:
            super(VIFPortProfileOpenVSwitch, self).obj_make_compatible(
                primitive, '1.1')


@base.VersionedObjectRegistry.register
class VIFPortProfileFPOpenVSwitch(VIFPortProfileOpenVSwitch):
    """Port profile info for Open vSwitch networks using fast path.

    This profile provides the metadata required to associate a :term:`fast
    path <Fast Path>` VIF with an :term:`Open vSwitch` port.
    """

    # Version 1.0: Initial release
    # Version 1.1: VIFPortProfileOpenVSwitch updated to 1.1 from 1.0
    # Version 1.2: VIFPortProfileOpenVSwitch updated to 1.2 from 1.1
    # Version 1.3: VIFPortProfileOpenVSwitch updated to 1.3 from 1.2
    VERSION = '1.3'

    fields = {
        #: Name of the bridge (managed by fast path) to connect to.
        'bridge_name': fields.StringField(),

        #: Whether the OpenVSwitch network is using hybrid plug.
        'hybrid_plug': fields.BooleanField(default=False),
    }

    def obj_make_compatible(self, primitive, target_version):
        target_version = versionutils.convert_version_to_tuple(target_version)
        if target_version < (1, 1):
            super(VIFPortProfileFPOpenVSwitch, self).obj_make_compatible(
                primitive, '1.0')
        elif target_version < (1, 2):
            super(VIFPortProfileFPOpenVSwitch, self).obj_make_compatible(
                primitive, '1.1')
        elif target_version < (1, 3):
            super(VIFPortProfileFPOpenVSwitch, self).obj_make_compatible(
                primitive, '1.2')
        else:
            super(VIFPortProfileFPOpenVSwitch, self).obj_make_compatible(
                primitive, '1.3')


@removals.removed_class("VIFPortProfileOVSRepresentor",
                        category=PendingDeprecationWarning)
@base.VersionedObjectRegistry.register
class VIFPortProfileOVSRepresentor(VIFPortProfileOpenVSwitch):
    """Port profile info for OpenVSwitch networks using a representor.

    This profile provides the metadata required to associate a VIF with a
    :term:`VF` representor and :term:`Open vSwitch` port. If `representor_name`
    is specified, it indicates a desire to rename the representor to the given
    name on plugging.

    .. note::

        This port profile is provided for backwards compatibility only.

        This interface has been superceded by the one provided by the
        :class:`DatapathOffloadRepresentor` class, which is now a field element
        of the :class:`VIFPortProfileBase` class. The ``datapath_offload``
        field in port profiles should be used instead.
    """

    # Version 1.0: Initial release
    # Version 1.1: VIFPortProfileOpenVSwitch updated to 1.1 from 1.0
    # Version 1.2: VIFPortProfileOpenVSwitch updated to 1.2 from 1.1
    # Version 1.3: VIFPortProfileOpenVSwitch updated to 1.3 from 1.2
    VERSION = '1.3'

    fields = {
        #: Name to set on the representor (if set).
        'representor_name': fields.StringField(nullable=True),

        #: The PCI address of the Virtual Function.
        'representor_address': fields.PCIAddressField(nullable=True),
    }

    def obj_make_compatible(self, primitive, target_version):
        target_version = versionutils.convert_version_to_tuple(target_version)
        if target_version < (1, 1):
            super(VIFPortProfileOVSRepresentor, self).obj_make_compatible(
                primitive, '1.0')
        elif target_version < (1, 2):
            super(VIFPortProfileOVSRepresentor, self).obj_make_compatible(
                primitive, '1.1')
        elif target_version < (1, 3):
            super(VIFPortProfileOVSRepresentor, self).obj_make_compatible(
                primitive, '1.2')
        else:
            super(VIFPortProfileOVSRepresentor, self).obj_make_compatible(
                primitive, '1.3')


@base.VersionedObjectRegistry.register
class VIFPortProfileFPBridge(VIFPortProfileBase):
    """Port profile info for Linux Bridge networks using fast path.

    This profile provides the metadata required to associate a :term:`fast
    path <Fast Path>` VIF with a :term:`Linux Bridge` port.
    """

    # Version 1.0: Initial release
    # Version 1.1: VIFPortProfileBase updated to 1.1 from 1.0
    VERSION = '1.1'

    fields = {
        #: Name of the bridge (managed by fast path) to connect to.
        'bridge_name': fields.StringField(),
    }

    def obj_make_compatible(self, primitive, target_version):
        target_version = versionutils.convert_version_to_tuple(target_version)
        if target_version < (1, 1):
            super(VIFPortProfileFPBridge, self).obj_make_compatible(
                primitive, '1.0')
        else:
            super(VIFPortProfileFPBridge, self).obj_make_compatible(
                primitive, '1.1')


@base.VersionedObjectRegistry.register
class VIFPortProfileFPTap(VIFPortProfileBase):
    """Port profile info for Calico networks using fast path.

    This profile provides the metadata required to associate a :term:`fast
    path <Fast Path>` VIF with a :term:`Calico` port.
    """

    # Version 1.0: Initial release
    # Version 1.1: VIFPortProfileBase updated to 1.1 from 1.0
    VERSION = '1.1'

    fields = {
        #: The MAC address of the host vhostuser port.
        'mac_address': fields.MACAddressField(nullable=True),
    }

    def obj_make_compatible(self, primitive, target_version):
        target_version = versionutils.convert_version_to_tuple(target_version)
        if target_version < (1, 1):
            super(VIFPortProfileFPTap, self).obj_make_compatible(
                primitive, '1.0')
        else:
            super(VIFPortProfileFPTap, self).obj_make_compatible(
                primitive, '1.1')


@base.VersionedObjectRegistry.register
class VIFPortProfile8021Qbg(VIFPortProfileBase):
    """Port profile info for VEPA 802.1qbg networks.

    This profile provides the metadata required to associate a VIF with a VEPA
    host device supporting the :term:`802.1Qbg` spec.
    """

    # Version 1.0: Initial release
    # Version 1.1: VIFPortProfileBase updated to 1.1 from 1.0
    VERSION = '1.1'

    fields = {
        # TODO(stephenfin): Apparently the value 0 is reserved for manager_id,
        # so should we set 'minimum=1'?
        # https://libvirt.org/formatdomain.html#elementsNICS

        #: The VSI Manager ID identifies the database containing the VSI type
        #: and instance definitions.
        'manager_id': fields.IntegerField(),

        #: The VSI Type ID identifies a VSI type characterizing the network
        #: access. VSI types are typically managed by network administrator.
        'type_id': fields.IntegerField(),

        #: The VSI Type Version allows multiple versions of a VSI Type.
        'type_id_version': fields.IntegerField(),

        #: The VSI Instance ID Identifier is generated when a VSI instance
        #: (i.e. a virtual interface of a virtual machine) is created. This is
        #: a globally unique identifier.
        'instance_id': fields.UUIDField(),
    }

    def obj_make_compatible(self, primitive, target_version):
        target_version = versionutils.convert_version_to_tuple(target_version)
        if target_version < (1, 1):
            super(VIFPortProfile8021Qbg, self).obj_make_compatible(
                primitive, '1.0')
        else:
            super(VIFPortProfile8021Qbg, self).obj_make_compatible(
                primitive, '1.1')


@base.VersionedObjectRegistry.register
class VIFPortProfile8021Qbh(VIFPortProfileBase):
    """Port profile info for VEPA 802.1qbh networks.

    This profile provides the metadata required to associate a VIF with a VEPA
    host device supporting the :term:`802.1Qbh` spec.
    """

    # Version 1.0: Initial release
    # Version 1.1: VIFPortProfileBase updated to 1.1 from 1.0
    VERSION = '1.1'

    fields = {
        #: The name of the port profile that is to be applied to this
        #: interface. This name is resolved by the port profile database into
        #: the network parameters from the port profile, and those network
        #: parameters will be applied to this interface.
        'profile_id': fields.StringField()
    }

    def obj_make_compatible(self, primitive, target_version):
        target_version = versionutils.convert_version_to_tuple(target_version)
        if target_version < (1, 1):
            super(VIFPortProfile8021Qbh, self).obj_make_compatible(
                primitive, '1.0')
        else:
            super(VIFPortProfile8021Qbh, self).obj_make_compatible(
                primitive, '1.1')


@base.VersionedObjectRegistry.register
class VIFPortProfileK8sDPDK(VIFPortProfileBase):
    """Port profile info for Kuryr-Kubernetes DPDK ports.

    This profile provides the metadata required to associate nested DPDK VIF
    with a Kubernetes pod.
    """

    # Version 1.0: Initial release
    # Version 1.1: VIFPortProfileBase updated to 1.1 from 1.0
    VERSION = '1.1'

    fields = {
        #: Specify whether this vif requires L3 setup.
        'l3_setup': fields.BooleanField(),

        #: String containing URL representing object in Kubernetes v1 API.
        'selflink': fields.StringField(),

        #: String used in Kubernetes v1 API to identify the server's internal
        #: version of this object.
        'resourceversion': fields.StringField()
    }

    def obj_make_compatible(self, primitive, target_version):
        target_version = versionutils.convert_version_to_tuple(target_version)
        if target_version < (1, 1):
            super(VIFPortProfileK8sDPDK, self).obj_make_compatible(
                primitive, '1.0')
        else:
            super(VIFPortProfileK8sDPDK, self).obj_make_compatible(
                primitive, '1.1')
