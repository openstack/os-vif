============================
So You Want to Contribute...
============================

For general information on contributing to OpenStack, please check out the
`contributor guide <https://docs.openstack.org/contributors/>`_ to get started.
It covers all the basics that are common to all OpenStack projects: the accounts
you need, the basics of interacting with our Gerrit review system, how we
communicate as a community, etc.

Below will cover the more project specific information you need to get started
with os-vif.

Communication
~~~~~~~~~~~~~

Please refer `how-to-get-involved <https://docs.openstack.org/nova/latest/contributor/how-to-get-involved.html>`_.

Contacting the Core Team
~~~~~~~~~~~~~~~~~~~~~~~~

The overall structure of the os-vif team is documented on `the wiki
<https://wiki.openstack.org/wiki/Nova#People>`_.

New Feature Planning
~~~~~~~~~~~~~~~~~~~~

You can file an RFE `bug <https://bugs.launchpad.net/os-vif/+filebug>`_ if it
has no interaction with other projects like nova or neutron.

If changes are part of the nova or neutron feature then it can be tracked
as part of the nova or neutron feature. In that case, you should use the
same topic to track the os-vif changes.

Task Tracking
~~~~~~~~~~~~~

We track our tasks in `Launchpad <https://bugs.launchpad.net/os-vif>`__.

If you're looking for some smaller, easier work item to pick up and get started
on, search for the 'low-hanging-fruit' tag.

Reporting a Bug
~~~~~~~~~~~~~~~

You found an issue and want to make sure we are aware of it? You can do so on
`Launchpad <https://bugs.launchpad.net/os-vif/+filebug>`__.
More info about Launchpad usage can be found on `OpenStack docs page
<https://docs.openstack.org/contributors/common/task-tracking.html#launchpad>`_.

Getting Your Patch Merged
~~~~~~~~~~~~~~~~~~~~~~~~~

All changes proposed to the os-vif requires two ``Code-Review +2`` votes from
os-vif core reviewers before one of the core reviewers can approve patch by
giving ``Workflow +1`` vote. One exception is for trivial changes for example
typo fixes etc which can be approved by a single core.
