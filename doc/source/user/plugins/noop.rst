=====
no-op
=====

The no-op plugin, ``vif_plug_noop``, is an *os-vif* VIF plugin for use with
network backends that do not require plugging of network interfaces. It is one
of two plugins provided as part of *os-vif* itself, the other being :doc:`ovs`.

Supported VIF Types
-------------------

The no-op plugin provides support for the following VIF types:

:mod:`~os_vif.objects.VIFVHostUser`
  Configuration where a guest exposes a UNIX socket for its control plane. This
  configuration is used with a userspace dataplane such as VPP or Snabb switch.

For information on the VIF type objects, refer to :doc:`/user/vif-types`. Note
that only the above VIF types are supported by this plugin.
