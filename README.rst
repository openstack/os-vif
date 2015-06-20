======
os-vif
======

A library for plugging and unplugging virtual interfaces in OpenStack.

Features
--------

* A base VIF plugin class that supplies a plug() and unplug() interface
* Versioned objects that represent a virtual interface and its components

Usage
-----

The interface to the `os_vif` library is very simple. To begin using the
library, first call the `os_vif.initialize()` function, supplying a set of
keyword arguments for configuration options::

    import os_vif

    os_vif.initialize(libvirt_virt_type='kvm',
                      network_device_mtu=1500,
                      vlan_interface='eth1',
                      use_ipv6=False,
                      iptables_top_regex='',
                      iptables_bottom_regex='',
                      iptables_drop_action='DROP',
                      forward_bridge_interface=['all'])

Once the `os_vif` library is initialized, there are only two other library
functions: `os_vif.plug()` and `os_vif.unplug()`. Both methods accept a single
argument of type `os_vif.objects.VIF`::

    import uuid

    from nova import objects as nova_objects
    from os_vif import exception as vif_exc
    from os_vif import objects as vif_objects
    from os_vif import vnic_types

    instance_uuid = 'd7a730ca-3c28-49c3-8f26-4662b909fe8a'
    instance = nova_objects.Instance.get_by_uuid(instance_uuid)
    instance_info = vif_objects.InstanceInfo.from_nova_instance(instance)

    subnet = vif_objects.Subnet(cidr='192.168.1.0/24')
    subnets = vif_objects.SubnetList([subnet])
    network = vif_objects.Network(label='tenantnet',
                                  subnets=subnets,
                                  multi_host=False,
                                  should_provide_vlan=False,
                                  should_provide_bridge=False)

    vif_uuid = uuid.uuid4()
    details = {
        'ovs_hybrid_plug': True,
        'vhostuser_socket': '/path/to/socket',
    }
    vif = vif_objects.VIF(id=vif_uuid,
                          address=None,
                          network=network,
                          plugin='vhostuser',
                          details=details,
                          profile=None,
                          vnic_type=vnic_types.NORMAL,
                          active=True,
                          preserve_on_delete=False,
                          instance_info=instance_info)

    # Now do the actual plug operations to connect the VIF to
    # the backing network interface.
    try:
        os_vif.plug(vif)
    except vif_exc.PlugException as err:
        # Handle the failure...

    # If you are removing a virtual machine and its interfaces,
    # you would use the unplug() operation:
    try:
        os_vif.unplug(vif)
    except vif_exc.UnplugException as err:
        # Handle the failure...
