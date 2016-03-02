===========
 VIF Types
===========

In os-vif, a VIF type refers to a particular approach for configuring
the backend of a guest virtual network interface. There is a small,
finite set of ways that a VIF backend can be configured for any given
hypervisor and a limited amount of metadata is associated with each
approach.

VIF objects
===========

Each distinct type of VIF configuration is represented by a versioned
object in os-vif, subclassed from os_vif.objects.VIFBase. The VIFBase
class defines some fields that are common to all types of VIF, and
provides an association to a versioned object describing the network
the VIF is plugged into.

VIFGeneric
----------

This class provides a totally generic type of configuration, where the
guest is simply associated with an arbitrary TAP device (or equivalent).
The way the TAP device is connected to the host network stack is
explicitly left undefined and entirely up to the plugin to decide.

VIFBridge
---------

This class provides a configuration where the guest is connected
directly to an explicit host bridge device. This provides ethernet
layer bridging, typically to the LAN.

VIFOpenVSwitch
--------------

This class provides a configuration where the guest is connected to
an openvswitch port.

VIFDirect
---------

This class provides a configuration where the guest is connected to
a physical network device. The connection to the device may operate
in one of a number of different modes, VEPA (either 802.1qbg
802.1qbh), passthrough (exclusive assignment of the host NIC) or
bridge (ethernet layer bridging of traffic). The passthrough mode
would be used when there is a network device which needs to have
a MAC address or vlan conf. For passthrough of network devices
without MAC/vlan configuration, the VIFHostDevice should be used
instead.

VIFVHostUser
------------

This class provides another totally generic type of configuration,
where the guest is exposing a UNIX socket for its control plane,
allowing an external userspace service to provide the backend data
plane via a mapped memory region. The process must implement the
virtio-net vhost protocol on this socket in whatever means is most
suitable.

VIFHostDevice
-------------

This class provides a way to pass a physical device to the guest.
Either an entire physical device, or a SR-IOV PCI device virtual
function, are permitted.


VIF port profile objects
========================

Each VIF instance can optionally be associated with a port profile
object. This provides a set of metadata attributes that serve to
identify the guest virtual interface to the host. Different types
of host connectivity will require different port profile object
metadata. Each port profile type is associated wtih a versioned
object, subclassing VIFPortProfileBase

VIFPortProfileOpenVSwitch
-------------------------

This profile provides the metadata required to associate a VIF
with an openvswitch host port.

VIFPortProfile8021Qbg
---------------------

This profile provides the metadata required to associate a VIF
with a VEPA host device supporting the 801.1Qbg spec.

VIFPortProfile8021Qbh
---------------------

This profile provides the metadata required to associate a VIF
with a VEPA host device supporting the 801.1Qbg spec.


VIF network objects
===================

Each VIF instance is associated with a set of objects which
describe the logical network that the guest will be plugged
into. This information is again represented by a set of
versioned objects

TODO :-(
