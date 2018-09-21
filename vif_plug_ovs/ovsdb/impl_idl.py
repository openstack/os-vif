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

from ovs.db import idl
from ovsdbapp.backend.ovs_idl import connection
from ovsdbapp.backend.ovs_idl import idlutils
from ovsdbapp.backend.ovs_idl import vlog
from ovsdbapp.schema.open_vswitch import impl_idl

from vif_plug_ovs.ovsdb import api


def idl_factory(config):
    conn = config.connection
    schema_name = 'Open_vSwitch'
    helper = idlutils.get_schema_helper(conn, schema_name)
    helper.register_all()
    return idl.Idl(conn, helper)


def api_factory(config):
    conn = connection.Connection(
        idl=idl_factory(config),
        timeout=config.timeout)
    return NeutronOvsdbIdl(conn)


class NeutronOvsdbIdl(impl_idl.OvsdbIdl, api.ImplAPI):
    """IDL interface for OVS database back-end

    This class provides an OVSDB IDL (Open vSwitch Database Interface
    Definition Language) interface to the OVS back-end.
    """
    def __init__(self, conn):
        vlog.use_python_logger()
        super(NeutronOvsdbIdl, self).__init__(conn)

    def _get_table_columns(self, table):
        return list(self.tables[table].columns)

    def has_table_column(self, table, column):
        return column in self._get_table_columns(table)
