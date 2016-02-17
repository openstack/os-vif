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

from oslo_versionedobjects import base
from oslo_versionedobjects import fields

from os_vif.objects import base as osv_base
from os_vif.objects import fields as osv_fields


@base.VersionedObjectRegistry.register
class Subnet(osv_base.VersionedObject):
    """Represents a subnet."""
    # Version 1.0: Initial version
    VERSION = '1.0'

    fields = {
        'cidr': fields.IPNetworkField(),
        'dns': osv_fields.ListOfIPAddressField(),
        'gateway': fields.IPAddressField(),
        'ips': fields.ObjectField("FixedIPList"),
        'routes': fields.ObjectField("RouteList"),
        'dhcp_server': fields.IPAddressField(),
    }


@base.VersionedObjectRegistry.register
class SubnetList(osv_base.VersionedObject, base.ObjectListBase):
    # Version 1.0: Initial version
    VERSION = '1.0'

    fields = {
        'objects': fields.ListOfObjectsField('Subnet'),
    }
