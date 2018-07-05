=====
no-op
=====

The no-op plugin, ``vif_plug_noop``, is an *os-vif* VIF plugin for use with
network backends that do not require plugging of network interfaces. It is one
of three plugins provided as part of *os-vif* itself, the others being
:doc:`ovs` and  :doc:`linux-bridge`.

Supported VIF Types
-------------------

The no-op plugin provides support for the following VIF types:

``VIFVHostUser``
  Configuration where a guest exposes a UNIX socket for its control plane. This
  configuration is used with a userspace dataplane such as VPP or Snabb switch.

  Refer to :ref:`vif-vhostuser` for more information.

For information on the VIF type objects, refer to :doc:`/user/vif-types`. Note
that only the above VIF types are supported by this plugin.
