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


@base.VersionedObjectRegistry.register
class Route(base.VersionedObject):
    """Represents a route."""
    # Version 1.0: Initial version
    VERSION = '1.0'

    fields = {
        'cidr': fields.IPNetworkField(),
        'gateway': fields.IPAddressField(),
        'interface': fields.StringField(),
    }


@base.VersionedObjectRegistry.register
class RouteList(base.VersionedObject, base.ObjectListBase):
    # Version 1.0: Initial version
    VERSION = '1.0'

    fields = {
        'objects': fields.ListOfObjectsField('Route'),
    }
