================
Host Information
================

To enable negotiation of features between a service host (typically a compute
node) and the network provider host, os-vif exposes some objects that describe
the host running the plugins.

Host Information Objects
========================

The following objects encode the information about the service host.

HostInfo
--------

This class provides information about the host as a whole. This currently means
a list of plugins installed on the host. In the future this may include further
information about the host OS state.

HostPluginInfo
--------------

This class provides information about the capabilities of a single os-vif
plugin implementation that is installed on the host. This currently means a
list of VIF objects that the plugin is capable of consuming. In the future this
may include further information about resources on the host that the plugin
can/will utilize. While many plugins will only ever support a single VIF
object, it is permitted to support multiple different VIF objects. An example
would be openvswitch which can use the same underlying host network
functionality to configure a VM in several different ways.

HostVIFInfo
-----------

This class provides information on a single VIF object that is supported by a
plugin. This will include the versioned object name and the minimum and maximum
versions of the object that can be consumed.

It is the responsibility of the network provider to ensure that it only sends
back a serialized VIF object that satisfies the minimum and maximum version
constraints indicated by the plugin. Objects outside of this version range will
be rejected with a fatal error.

Negotiating networking
======================

When a service host wants to create a network port, it will first populate an
instance of the HostInfo class, to describe all the plugins installed on the
host. It will then serialize this class to JSON and send it to the network
manager host. The network manager host will deserialize it back into a HostInfo
object. This can then be passed down into the network driver which can use it
to decide how to configure the network port.

If the os-vif version installed on the network host is older than that on the
service host, it may not be able to deserialize the HostInfo class. In this
case it should reply with an error to the service host. The error message
should report the maximum version of the HostInfo class that is supported. the
service host should then backlevel its HostInfo object to that version before
serializing it and re-trying the port creation request.

The mechanism or transport for passing the plugin information between the
network and service hosts is left undefined. It is upto the user of os-vif to
decide upon the appropriate approach.
