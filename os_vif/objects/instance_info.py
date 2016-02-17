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


@base.VersionedObjectRegistry.register
class InstanceInfo(osv_base.VersionedObject):
    """Represents important information about a Nova instance."""
    # Version 1.0: Initial version
    VERSION = '1.0'

    fields = {
        # UUID of the instance
        'uuid': fields.UUIDField(),
        # The instance name, directly from the Nova instance field of the
        # same name
        'name': fields.StringField(),
        # The project/tenant ID that owns the instance
        'project_id': fields.StringField(),
    }
