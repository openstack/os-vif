========
Glossary
========

.. glossary::

   Calico

     A virtual networking solution that uses IP routing (layer 3) to provide
     connectivity in the form of a flat IP network instead of bridging and
     tunneling.

     Refer to the `Calico documentation`__ for more information.

     __ http://docs.projectcalico.org

   Linux Bridge

     The native networking "backend" found in Linux.

     Refer to the `Linux Foundation wiki`__ for more information.

     __ https://wiki.linuxfoundation.org/networking/bridge

   Open vSwitch

     A software implementation of a :term:`virtual multilayer network switch
     <vSwitch>`

     Refer to the `OVS documentation`__ for more information.

     __ http://docs.openvswitch.org

   VEB
   Virtual Ethernet Bridge

     A virtual Ethernet switch that implmented in a virtualized server
     environment. It is anything that mimics a traditional external layer 2
     (L2) switch or bridge for connecting VMs. Generally implemented as a
     :term:`vSwitch`, though hardware-based VEBs using SR-IOV are possible.

     Refer to this `Virtual networking technologies brief`__ for more
     information.

     __ http://cs.nyu.edu/courses/fall14/CSCI-GA.3033-010/Network/SDN.pdf

   vSwitch
   Virtual Switch

     A software-based virtual switch that connects virtual NICs to other
     virtual NICs and the broader physical network.

     Refer to this `presentation`__ for more information.

     __ http://cs.nyu.edu/courses/fall14/CSCI-GA.3033-010/Network/SDN.pdf

   VEPA
   Virtual Ethernet Port Aggregator

     An approach to virtual networking where VM traffic is handled on the
     physical network rather than by a virtual switch. Unlike :term:`VNTag`,
     frames are not tagged and the switch will use a single port to handle all
     :term:`VIFs <VIF>` for a host.

     The basis of the :term:`802.1Qbg` spec.

     Refer to this `presentation`__ for more information.

     __ http://www.ieee802.org/1/files/public/docs2009/new-hudson-vepa_summary-0509.pdf

   VN-Tag
   VNTag

     An approach to virtual networking where an interface virtualizer (IV) is
     used in place of a :term:`VEB` to connect multiple :term:`VIFs <VIF>` to a
     single, external, IV-capable hardware bridge. Each VIF is tagged with a
     unique ID (`vif_id`) which is used to route traffic through IVs, and VIFs
     are then treated like any other interface.

     The basis of the :term:`802.1Qbh` and :term:`802.1Qbr` specs.

     Refer to this `Cisco presentation`__ for more information.

     __ https://learningnetwork.cisco.com/docs/DOC-27114

   vhost

     An alternative to :term:`virtio` that allows a userspace process to share
     *virtqueues* directly with the kernel, preventing the QEMU process from
     becoming a bottleneck.

   vhost-user

     A variation of :term:`vhost` that operates entirely in userspace. This
     allows processes operating in userspace, such as virtual switches, to
     avoid the kernel entirely and maximize performance.

     Refer to the `QEMU documentation`__ for more information.

     __ https://github.com/qemu/qemu/blob/master/docs/specs/vhost-user.txt

   virtio

     A class of virtual device emulated by QEMU. Virtio devices have
     *virtqueues* which can be used to share data from host to guest.

     Refer to the `libvirt Wiki`__ for more information.

     __ https://wiki.libvirt.org/page/Virtio

   virtio-net

     A network driver implementation based on virtio. Guests share *virtqueues*
     with the QEMU process, which in turn receives this traffic and forwards it
     to the host.

     Refer to the `KVM documentation`__ for more information.

     __ http://www.linux-kvm.org/page/Virtio

   VIF

     A virtual network interface.

   IEEE 802.1Q
   802.1Q

     A networking standard that supports virtual LANs (VLANs) on an Ethernet
     network.

     Refer to the `IEEE spec`__ for more information.

     __ http://www.ieee802.org/1/pages/802.1Q.html

   IEEE 802.1Qbg
   802.1Qbg

     An amendment to the :term:`802.1Q` spec known as "Edge Virtual Bridging",
     802.1Qbg is an approach to networking where VM traffic is handled on the
     physical network rather than by a virtual switch. Originally based on
     :term:`VEPA`.

     Refer to the `IEEE spec`__ for more information.

     __ http://www.ieee802.org/1/pages/802.1bg.html

   IEEE 802.1Qbh
   802.1Qbh

     A withdrawn amendment to the :term:`802.1Q` spec known as "Bridge Port
     Extensions", replaced by :term:`802.1Qbr` spec.

     Refer to the `IEEE spec`__ for more information.

     __ http://www.ieee802.org/1/pages/802.1bh.html

   IEEE 802.1Qbr
   802.1Qbr

     An amendment to the :term:`802.1Q` spec known as "Bridge Port Extensions",


     Refer to the `IEEE spec`__ for more information.

     __ http://www.ieee802.org/1/pages/802.1br.html

   tc

      A framework for interacting with traffic control settings (QoS,
      essentially) in the Linux kernel.

      Refer to the `tc(8) man page`__ for more information.

      __ https://linux.die.net/man/8/tc

   SR-IOV
   Single Root I/O Virtualization

     An extension to the PCI Express (PCIe) specification that allows a device,
     typically a network adapter, to split access to its resources among
     various PCIe hardware functions, :term:`physical <PF>` or :term:`virtual
     <VF>`.

     Refer to this `article by Scott Lowe`__ or the original `PCI-SIG spec`__
     (paywall) for more information.

     __ http://blog.scottlowe.org/2009/12/02/what-is-sr-iov/
     __ https://members.pcisig.com/wg/PCI-SIG/document/download/8272

   PF
   Physical Function

     In SR-IOV, a PCIe function that has full configuration resources. An
     SR-IOV device can have *up to* 8 PFs, though this varies between devices.
     A PF would typically correspond to a single interface on a NIC.

     Refer to this `article by Scott Lowe`__ for more information.

     __ http://blog.scottlowe.org/2009/12/02/what-is-sr-iov/

   VF
   Virtual Function

     In SR-IOV, a PCIe function that lacks configuration resources. An SR-IOV
     device can have *up to* 256 VFs, though this varies between devices. A VF
     must be of the same type as the parent device's :term:`PF`.

     Refer to this `article by Scott Lowe`__ for more information.

     __ http://blog.scottlowe.org/2009/12/02/what-is-sr-iov/
