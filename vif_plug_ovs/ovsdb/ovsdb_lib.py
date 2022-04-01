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
        self._ovsdb = None

    # NOTE(sean-k-mooney): when using the native ovsdb bindings
    # creating an instance of the ovsdb api connects to the ovsdb
    # to initialize the library based on the schema version
    # of the ovsdb. To avoid that we lazy load the ovsdb
    # instance the first time we need it via a property.
    @property
    def ovsdb(self):
        if not self._ovsdb:
            self._ovsdb = ovsdb_api.get_instance(self)
        return self._ovsdb

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

    def delete_ovs_bridge(self, bridge):
        """Delete ovs bridge by name

        :param bridge: bridge name as a string

        .. note:: Do Not call with br-int !!!
        """
        # TODO(sean-k-mooney): when we fix bug: #1914886
        # add a guard against deleting the integration bridge
        # after adding a config option to store its name.
        return self.ovsdb.del_br(bridge).execute()

    def create_patch_port_pair(
        self, port_bridge, port_bridge_port, int_bridge, int_bridge_port,
        iface_id, mac, instance_id, tag=None
    ):
        """Create a patch port pair between any two bridges.

        :param port_bridge: the source bridge name for the patch port pair.
        :param port_bridge_port: the name of the patch port on the
        source bridge.
        :param int_bridge: the target bridge name, typically br-int.
        :param int_bridge_port: the name of the patch port on the
        target bridge.
        :param iface_id: neutron port ID.
        :param mac: port MAC.
        :param instance_id: instance uuid.
        :param mtu: port MTU.
        :param tag: OVS interface tag used for vlan isolation.
        """

        # NOTE(sean-k-mooney): we use a transaction here for 2 reasons:
        # 1.) if using the vsctl client its faster
        # 2.) in all cases we either want to fully create the patch port
        # pair or not create it atomically. By using a transaction we know
        # that we will never be in a mixed state where it was partly created.
        with self.ovsdb.transaction() as txn:
            # create integration bridge patch peer
            external_ids = {
                'iface-id': iface_id, 'iface-status': 'active',
                'attached-mac': mac, 'vm-uuid': instance_id
            }
            col_values = [
                ('external_ids', external_ids),
                ('type', 'patch'),
                ('options', {'peer': port_bridge_port})
            ]

            txn.add(self.ovsdb.add_port(int_bridge, int_bridge_port))
            if tag:
                txn.add(
                    self.ovsdb.db_set('Port', int_bridge_port, ('tag', tag)))
            txn.add(
                self.ovsdb.db_set('Interface', int_bridge_port, *col_values))

            # create port bridge patch peer
            col_values = [
                ('type', 'patch'),
                ('options', {'peer': int_bridge_port})
            ]
            txn.add(self.ovsdb.add_port(port_bridge, port_bridge_port))
            txn.add(
                self.ovsdb.db_set('Interface', port_bridge_port, *col_values))

    def create_ovs_vif_port(
        self, bridge, dev, iface_id, mac, instance_id,
        mtu=None, interface_type=None, vhost_server_path=None,
        tag=None, pf_pci=None, vf_num=None, set_ids=True, datapath_type=None
    ):
        """Create OVS port

        :param bridge: bridge name to create the port on.
        :param dev: port name.
        :param iface_id: port ID.
        :param mac: port MAC.
        :param instance_id: VM ID on which the port is attached to.
        :param mtu: port MTU.
        :param interface_type: OVS interface type.
        :param vhost_server_path: path to socket file of vhost server.
        :param tag: OVS interface tag.
        :param pf_pci: PCI address of PF for dpdk representor port.
        :param vf_num: VF number of PF for dpdk representor port.
        :param set_ids: set external ids on port (bool).
        :param datapath_type: datapath type for port's bridge

        .. note:: create DPDK representor port by setting all three values:
            `interface_type`, `pf_pci` and `vf_num`. if interface type is
            not `OVS_DPDK_INTERFACE_TYPE` then `pf_pci` and `vf_num` values
            are ignored.
        """
        external_ids = {'iface-id': iface_id,
                        'iface-status': 'active',
                        'attached-mac': mac,
                        'vm-uuid': instance_id}
        col_values = [('external_ids', external_ids)] if set_ids else []
        if interface_type:
            col_values.append(('type', interface_type))
        if vhost_server_path:
            col_values.append(('options',
                               {'vhost-server-path': vhost_server_path}))
        if (interface_type == constants.OVS_DPDK_INTERFACE_TYPE and
                pf_pci and vf_num):
            devargs_string = "{PF_PCI},representor=[{VF_NUM}]".format(
                PF_PCI=pf_pci, VF_NUM=vf_num)
            col_values.append(('options',
                              {'dpdk-devargs': devargs_string}))
        with self.ovsdb.transaction() as txn:
            if datapath_type:
                txn.add(self.ovsdb.add_br(bridge, may_exist=True,
                                          datapath_type=datapath_type))
            txn.add(self.ovsdb.add_port(bridge, dev))
            if tag:
                txn.add(self.ovsdb.db_set('Port', dev, ('tag', tag)))
            if col_values:
                txn.add(self.ovsdb.db_set('Interface', dev, *col_values))
        self.update_device_mtu(dev, mtu, interface_type=interface_type)

    def update_ovs_vif_port(self, dev, mtu=None, interface_type=None):
        self.update_device_mtu(dev, mtu, interface_type=interface_type)

    def delete_ovs_vif_port(self, bridge, dev, delete_netdev=True):
        self.ovsdb.del_port(dev, bridge=bridge, if_exists=True).execute()
        if delete_netdev:
            linux_net.delete_net_dev(dev)
