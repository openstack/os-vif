=========
VIF Types
=========

In *os-vif*, a VIF type refers to a particular approach for configuring the
backend of a guest virtual network interface. There is a small, finite set of
ways that a VIF backend can be configured for any given hypervisor and a
limited amount of metadata is associated with each approach.


.. py:module:: os_vif.objects.vif

VIF objects
===========

Each distinct type of VIF configuration is represented by a versioned object,
subclassing :class:`VIFBase`.

.. autoclass:: VIFBase

.. autoclass:: VIFGeneric

.. autoclass:: VIFBridge

.. autoclass:: VIFOpenVSwitch

.. autoclass:: VIFDirect

.. autoclass:: VIFVHostUser

.. autoclass:: VIFDirect

.. autoclass:: VIFNestedDPDK


VIF port profile objects
========================

Each VIF instance can optionally be associated with a port profile object. This
provides a set of metadata attributes that serve to identify the guest virtual
interface to the host. Different types of host connectivity will require
different port profile object metadata. Each port profile type is associated
with a versioned object, subclassing `VIFPortProfileBase`.

VIFPortProfileOpenVSwitch
-------------------------

This profile provides the metadata required to associate a VIF with an Open
vSwitch host port.

VIFPortProfile8021Qbg
---------------------

This profile provides the metadata required to associate a VIF with a VEPA host
device supporting the :term:`802.1Qbg` spec.

VIFPortProfile8021Qbh
---------------------

This profile provides the metadata required to associate a VIF with a VEPA host
device supporting the :term:`802.1Qbh` spec.

VIFPortProfileFPOpenVSwitch
---------------------------

This profile provides the metadata required to associate a fast path
:term:`vhost-user` VIF with an :term:`Open vSwitch` port.

VIFPortProfileOVSRepresentor
----------------------------

This profile provides the metadata required to associate a VIF with a
:term:`VF` representor and :term:`Open vSwitch` port. If `representor_name` is
specified, it indicates a desire to rename the representor to the given name
on plugging.

.. note:: This port profile is provided for backwards compatibility only.

This interface has been superceded by the one provided by the
`DatapathOffloadRepresentor` class, which is now a field element of the
`VIFPortProfileBase` class.

VIFPortProfileFPBridge
----------------------

This profile provides the metadata required to associate a fast path vhost-user
VIF with a :term:`Linux bridge` port.

VIFPortProfileFPTap
-------------------

This profile provides the metadata required to associate a fast path vhost-user
VIF with a Calico port.

VIFPortProfileK8sDPDK
---------------------

This profile provides the metadata required to associate nested DPDK VIF with
a Kubernetes pod.

Datapath Offload type object
============================

Port profiles can be associated with a `datapath_offload` object. This
provides a set of metadata attributes that serve to identify the datapath
offload parameters of a VIF. Each different type of datapath offload is
associated with a versioned object, subclassing `DatapathOffloadBase`.

DatapathOffloadRepresentor
--------------------------

This object provides the metadata required to associate a VIF with a
:term:`VF` representor conforming to the
`switchdev <https://netdevconf.org/1.2/session.html?or-gerlitz>`_ kernel model.
If `representor_name` is specified, it indicates a desire to rename the
representor to the given name on plugging.

VIF network objects
===================

Each VIF instance is associated with a set of objects which describe the
logical network that the guest will be plugged into. This information is again
represented by a set of versioned objects

TODO :-(
