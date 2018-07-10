============
Open vSwitch
============

The Open vSwitch plugin, ``vif_plug_ovs``, is an *os-vif* VIF plugin for the
Open vSwitch network backend. It is one of three plugins provided as part of
*os-vif* itself, the others being :doc:`linux-bridge` and :doc:`noop`.

Supported VIF Types
-------------------

The Open vSwitch plugin provides support for the following VIF types:

``VIFOpenVSwitch``
  Configuration where a guest is directly connected an Open vSwitch bridge.

  Refer to :ref:`vif-openvswitch` for more information.

``VIFBridge``
  Configuration where a guest is connected to a Linux bridge via a TAP device,
  and that bridge is connected to the Open vSwitch bridge. This allows for the
  use of ``iptables`` rules for filtering traffic.

  Refer to :ref:`vif-bridge` for more information.

``VIFVHostUser``
  Configuration where a guest exposes a UNIX socket for its control plane. This
  configuration is used with the `DPDK datapath of Open vSwitch`__.

  Refer to :ref:`vif-vhostuser` for more information.

``VIFHostDevice``
  Configuration where an :term:`SR-IOV` PCI device :term:`VF` is passed through
  to a guest. The ``hw-tc-offload`` feature should be enabled on the SR-IOV
  :term:`PF` using ``ethtool``:

  .. code-block:: shell

      ethtool -K <PF> hw-tc-offload

  This will create a *VF representor* per VF. The VF representor plays the same
  role as TAP devices in Para-Virtual (PV) setup. In this case the ``plug()``
  method connects the VF representor to the OpenVSwitch bridge.

  .. important::

      Support for this feature requires Linux Kernel >= 4.8 and Open vSwitch
      2.8. These add support for :term:`tc`-based hardware offloads for SR-IOV
      VFs and offloading of OVS datapath rules using tc, respectively.

  Refer to :ref:`vif-hostdevice` for more information.

  .. versionadded:: 1.5.0

For information on the VIF type objects, refer to :doc:`/user/vif-types`. Note
that only the above VIF types are supported by this plugin.

__ http://docs.openvswitch.org/en/latest/howto/dpdk/
