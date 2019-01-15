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

from oslo_utils import versionutils
from oslo_versionedobjects import base
from oslo_versionedobjects import fields

from os_vif import objects
from os_vif.objects import base as osv_base


@base.VersionedObjectRegistry.register
class Network(osv_base.VersionedObject):
    """Represents a network."""
    # Version 1.0: Initial version
    # Version 1.1: Added MTU field
    VERSION = '1.1'

    fields = {
        'id': fields.UUIDField(),
        'bridge': fields.StringField(),
        'label': fields.StringField(),
        'subnets': fields.ObjectField('SubnetList'),
        'multi_host': fields.BooleanField(),
        'should_provide_bridge': fields.BooleanField(),
        'should_provide_vlan': fields.BooleanField(),
        'bridge_interface': fields.StringField(nullable=True),
        'vlan': fields.IntegerField(nullable=True),
        'mtu': fields.IntegerField(nullable=True),
    }

    def __init__(self, **kwargs):
        kwargs.setdefault('subnets', objects.subnet.SubnetList(objects=[]))
        kwargs.setdefault('multi_host', False)
        kwargs.setdefault('should_provide_bridge', False)
        kwargs.setdefault('should_provide_vlan', False)
        kwargs.setdefault('mtu', None)
        super(Network, self).__init__(**kwargs)

    def obj_make_compatible(self, primitive, target_version):
        target_version = versionutils.convert_version_to_tuple(target_version)
        if target_version < (1, 1) and 'mtu' in primitive:
            del primitive['mtu']
        super(Network, self).obj_make_compatible(primitive, '1.0')
