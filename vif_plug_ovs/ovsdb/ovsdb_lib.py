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

import sys

from oslo_log import log as logging

from vif_plug_ovs import constants
from vif_plug_ovs import linux_net
from vif_plug_ovs.ovsdb import api as ovsdb_api


LOG = logging.getLogger(__name__)


class BaseOVS(object):

    def __init__(self, config):
        self.timeout = config.ovs_vsctl_timeout
        self.connection = config.ovsdb_connection
        self.interface = config.ovsdb_interface
        self.ovsdb = ovsdb_api.get_instance(self)

    def _ovs_supports_mtu_requests(self):
        return self.ovsdb.has_table_column('Interface', 'mtu_request')

    def _set_mtu_request(self, dev, mtu):
        self.ovsdb.db_set('Interface', dev, ('mtu_request', mtu)).execute()

    def update_device_mtu(self, dev, mtu, interface_type=None):
        if not mtu:
            return
        if interface_type not in [
            constants.OVS_VHOSTUSER_INTERFACE_TYPE,
            constants.OVS_VHOSTUSER_CLIENT_INTERFACE_TYPE]:
            if sys.platform != constants.PLATFORM_WIN32:
                # Hyper-V with OVS does not support external programming of
                # virtual interface MTUs via netsh or other Windows tools.
                # When plugging an interface on Windows, we therefore skip
                # programming the MTU and fallback to DHCP advertisement.
                linux_net.set_device_mtu(dev, mtu)
        elif self._ovs_supports_mtu_requests():
            self._set_mtu_request(dev, mtu)
        else:
            LOG.debug("MTU not set on %(interface_name)s interface "
                      "of type %(interface_type)s.",
                      {'interface_name': dev,
                       'interface_type': interface_type})

    def ensure_ovs_bridge(self, bridge, datapath_type):
        return self.ovsdb.add_br(bridge, may_exist=True,
                                 datapath_type=datapath_type).execute()

    def create_ovs_vif_port(self, bridge, dev, iface_id, mac, instance_id,
                            mtu=None, interface_type=None,
                            vhost_server_path=None, tag=None):
        external_ids = {'iface-id': iface_id,
                        'iface-status': 'active',
                        'attached-mac': mac,
                        'vm-uuid': instance_id}
        col_values = [('external_ids', external_ids)]
        if interface_type:
            col_values.append(('type', interface_type))
        if vhost_server_path:
            col_values.append(('options',
                               {'vhost-server-path': vhost_server_path}))
        if tag:
            col_values.append(('tag', tag))

        with self.ovsdb.transaction() as txn:
            txn.add(self.ovsdb.add_port(bridge, dev))
            txn.add(self.ovsdb.db_set('Interface', dev, *col_values))
        self.update_device_mtu(dev, mtu, interface_type=interface_type)

    def update_ovs_vif_port(self, dev, mtu=None, interface_type=None):
        self.update_device_mtu(dev, mtu, interface_type=interface_type)

    def delete_ovs_vif_port(self, bridge, dev, delete_netdev=True):
        self.ovsdb.del_port(dev, bridge=bridge, if_exists=True).execute()
        if delete_netdev:
            linux_net.delete_net_dev(dev)
