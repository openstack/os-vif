============
Linux Bridge
============

The Linux Bridge plugin, ``vif_plug_linux_bridge``, is an *os-vif* VIF plugin
for the Linux Bridge network backend. It is one of three plugins provided as
part of *os-vif* itself, the others being :doc:`ovs` and :doc:`noop`.

Supported VIF Types
-------------------

The Linux Bridge plugin provides support for the following VIF types:

``VIFBridge``
  Configuration where a guest is connected to a Linux bridge via a TAP device.
  This is the only supported configuration for this plugin.

  Refer to :ref:`vif-bridge` for more information.

For information on the VIF type objects, refer to :doc:`/user/vif-types`. Note
that only the above VIF types are supported by this plugin.
