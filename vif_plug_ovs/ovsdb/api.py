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

import abc

from oslo_utils import importutils


interface_map = {
    'vsctl': 'vif_plug_ovs.ovsdb.impl_vsctl',
    'native': 'vif_plug_ovs.ovsdb.impl_idl',
}


def get_instance(context, iface_name=None):
    """Return the configured OVSDB API implementation"""
    iface = importutils.import_module(
        interface_map[iface_name or context.interface])
    return iface.api_factory(context)


class ImplAPI(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def has_table_column(self, table, column):
        """Check if a column exists in a database table

        :param table: (string) table name
        :param column: (string) column name
        :return: True if the column exists, False if not.
        """
