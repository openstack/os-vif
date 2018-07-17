=====
Usage
=====

The interface to the ``os_vif`` library is very simple. To begin using the
library, first call the ``os_vif.initialize()`` function. This will load all
installed plugins and register the object model:

.. code-block:: python

    import os_vif

    os_vif.initialize()

Once the ``os_vif`` library is initialized, there are only two other library
functions: ``os_vif.plug()`` and ``os_vif.unplug()``. Both methods accept an
argument of (a subclass of) type ``os_vif.objects.vif.VIFBase`` and an argument
of type ``os_vif.objects.instance_info.InstanceInfo``:

.. code-block:: python

    import uuid

    from nova import objects as nova_objects
    from os_vif import exception as vif_exc
    from os_vif.objects import fields
    from os_vif.objects import instance_info
    from os_vif.objects import network
    from os_vif.objects import subnet
    from os_vif.objects import vif as vif_obj

    instance_uuid = 'd7a730ca-3c28-49c3-8f26-4662b909fe8a'
    instance = nova_objects.Instance.get_by_uuid(instance_uuid)
    instance_info = instance_info.InstanceInfo(
        uuid=instance.uuid,
        name=instance.name,
        project_id=instance.project_id)

    subnet = subnet.Subnet(cidr='192.168.1.0/24')
    subnets = subnet.SubnetList([subnet])
    network = network.Network(label='tenantnet',
                              subnets=subnets,
                              multi_host=False,
                              should_provide_vlan=False,
                              should_provide_bridge=False)

    vif_uuid = uuid.uuid4()
    vif = vif_obj.VIFVHostUser(id=vif_uuid,
                               address=None,
                               network=network,
                               plugin='vhostuser',
                               path='/path/to/socket',
                               mode=fields.VIFVHostUserMode.SERVER)

    # Now do the actual plug operations to connect the VIF to
    # the backing network interface.
    try:
        os_vif.plug(vif, instance_info)
    except vif_exc.PlugException as err:
        # Handle the failure...

    # If you are removing a virtual machine and its interfaces,
    # you would use the unplug() operation:
    try:
        os_vif.unplug(vif, instance_info)
    except vif_exc.UnplugException as err:
        # Handle the failure...
