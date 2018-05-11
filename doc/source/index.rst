======
os-vif
======

`os-vif` is a library for plugging and unplugging virtual interfaces (VIFs) in
OpenStack. It provides:

- Versioned objects that represent various types of virtual interfaces and
  their components

- Base VIF plugin class that supplies a ``plug()`` and ``unplug()`` interface

- Plugins for two networking backends - Open vSwitch and Linux Bridge

`os-vif` is intended to define a common model for representing VIF types in
OpenStack. With the exception of the two included plugins, all plugins for
other networking backends are maintained in separate code repositories.

Usage Guide
-----------

.. toctree::
   :maxdepth: 2

   user/usage
   user/vif-types
   user/host-info
   user/plugins/linux-bridge
   user/plugins/noop
   user/plugins/ovs

Reference
---------

.. toctree::
   :maxdepth: 2

   reference/glossary
