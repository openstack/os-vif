#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import netaddr

from oslo_versionedobjects import base
from oslo_versionedobjects import fields


@base.VersionedObjectRegistry.register
class Subnet(base.VersionedObject):
    """Represents a subnet."""
    # Version 1.0: Initial version
    VERSION = '1.0'

    fields = {
        'cidr': fields.StringField(nullable=True),
        'dns': fields.ListOfStringsField(),
        'gateway': fields.StringField(),
        'ips': fields.ListOfStringsField(),
        'routes': fields.ListOfStringsField(),
        'version': fields.IntegerField(nullable=True),
    }

    def __init__(self, cidr=None, dns=None, gateway=None, ips=None,
                 routes=None, **kwargs):

        dns = dns or set()
        ips = ips or set()
        routes = routes or set()
        version = kwargs.pop('version', None)

        if cidr and not version:
            version = netaddr.IPNetwork(cidr).version
        super(Subnet, self).__init__(cidr=cidr, dns=dns, gateway=gateway,
                                     ips=ips, routes=routes, version=version)

    def as_netaddr(self):
        """Convenience function to get cidr as a netaddr object."""
        return netaddr.IPNetwork(self.cidr)


@base.VersionedObjectRegistry.register
class SubnetList(base.VersionedObject, base.ObjectListBase):
    # Version 1.0: Initial version
    VERSION = '1.0'

    fields = {
        'objects': fields.ListOfObjectsField('Subnet'),
    }
