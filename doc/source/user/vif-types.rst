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

.. autoclass:: VIFNestedDPDK


VIF port profile objects
========================

Each VIF instance can optionally be associated with a port profile object. This
provides a set of metadata attributes that serve to identify the guest virtual
interface to the host. Different types of host connectivity will require
different port profile object metadata. Each port profile type is associated
with a versioned object, subclassing :class:`VIFPortProfileBase`.

.. autoclass:: VIFPortProfileBase

.. autoclass:: VIFPortProfileOpenVSwitch

.. autoclass:: VIFPortProfileFPOpenVSwitch

.. autoclass:: VIFPortProfileOVSRepresentor

.. autoclass:: VIFPortProfileFPBridge

.. autoclass:: VIFPortProfileFPTap

.. autoclass:: VIFPortProfile8021Qbg

.. autoclass:: VIFPortProfile8021Qbh

.. autoclass:: VIFPortProfileK8sDPDK


Datapath Offload type object
============================

Port profiles can be associated with a ``datapath_offload`` object. This
provides a set of metadata attributes that serve to identify the datapath
offload parameters of a VIF. Each different type of datapath offload is
associated with a versioned object, subclassing :class:`DatapathOffloadBase`.

.. autoclass:: DatapathOffloadBase

.. autoclass:: DatapathOffloadRepresentor


VIF network objects
===================

Each VIF instance is associated with a set of objects which describe the
logical network that the guest will be plugged into. This information is again
represented by a set of versioned objects

.. todo:: Populate this!
