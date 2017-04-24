============
Open vSwitch
============

The Open vSwitch plugin, `vif_plug_ovs`, is an `os-vif` VIF plugin for the Open
vSwitch network backend. It is one of two plugins provided as part of `os-vif`
itself, the other being `linux-bridge`.

Supported VIF Types
-------------------

The Open vSwitch plugin provides support for the following VIF types:

`VIFOpenVSwitch`

  Configuration where a guest is directly connected an Open vSwitch bridge.

  Refer to :ref:`vif-openvswitch` for more information.

`VIFBridge`

  Configuration where a guest is connected to a Linux bridge via a TAP device,
  and that bridge is connected to the Open vSwitch bridge. This allows for the
  use of ``iptables`` rules for filtering traffic.

  Refer to :ref:`vif-bridge` for more information.

`VIFVHostUser`

  Configuration where a guest exposes a UNIX socket for its control plane. This
  configuration is used with the `DPDK datapath of Open vSwitch`__.

  Refer to :ref:`vif-vhostuser` for more information.

For information on the VIF type objects, refer to :doc:`../vif_types`. Note
that only the above VIF types are supported by this plugin.

__ http://docs.openvswitch.org/en/latest/howto/dpdk/
