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

from __future__ import annotations

from collections.abc import Iterable
import socket
from typing import cast, TYPE_CHECKING

from ovs.db import idl
from ovs import socket_util
from ovs import stream
from ovsdbapp.backend.ovs_idl import connection
from ovsdbapp.backend.ovs_idl import idlutils
from ovsdbapp.backend.ovs_idl import vlog
from ovsdbapp.schema.open_vswitch import impl_idl

from vif_plug_ovs.ovsdb import api

if TYPE_CHECKING:
    from vif_plug_ovs.ovsdb import ovsdb_lib


REQUIRED_TABLES = ('Interface', 'Port', 'Bridge', 'Open_vSwitch', 'QoS')


def idl_factory(config: ovsdb_lib.BaseOVS) -> idl.Idl:
    conn = config.connection
    schema_name = 'Open_vSwitch'
    helper = idlutils.get_schema_helper(conn, schema_name)
    for table in REQUIRED_TABLES:
        helper.register_table(table)
    return idl.Idl(conn, helper)


def api_factory(config: ovsdb_lib.BaseOVS) -> NeutronOvsdbIdl:
    conn = connection.Connection(
        idl=idl_factory(config),
        timeout=config.timeout)
    return NeutronOvsdbIdl(conn)


class NeutronOvsdbIdl(impl_idl.OvsdbIdl, api.ImplAPI):
    """IDL interface for OVS database back-end

    This class provides an OVSDB IDL (Open vSwitch Database Interface
    Definition Language) interface to the OVS back-end.
    """

    def __init__(self, conn: connection.Connection) -> None:
        vlog.use_python_logger()
        super(NeutronOvsdbIdl, self).__init__(conn)

    def _get_table_columns(self, table: str) -> list[str]:
        return list(self.tables[table].columns)

    def has_table_column(self, table: str, column: Iterable[str]) -> bool:
        return column in self._get_table_columns(table)


# this is derived form https://review.opendev.org/c/openstack/neutron/+/794892
def add_keepalives(sock: socket.socket) -> int:
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    except socket.error as e:
        sock.close()
        # ovs is not typed
        return cast(int, socket_util.get_exception_errno(e))
    return 0


class NoProbesMixin:
    @staticmethod
    def needs_probes() -> bool:
        # If we are using keepalives, we can force probe_interval=0
        return False


class TCPStream(stream.TCPStream, NoProbesMixin):
    @classmethod
    def _open(cls, suffix: str, dscp: int) -> tuple[int, socket.socket | None]:
        error, sock = super()._open(suffix, dscp)
        if error:
            return error, sock
        error = add_keepalives(sock)
        # ovs is not typed
        return error, cast(socket.socket, sock)


class SSLStream(stream.SSLStream, NoProbesMixin):
    @classmethod
    def _open(cls, suffix: str, dscp: int) -> tuple[int, socket.socket | None]:
        error, sock = super()._open(suffix, dscp)
        if error:
            return error, sock
        error = add_keepalives(sock)
        # ovs is not typed
        return error, cast(socket.socket, sock)


# Overwriting globals in a library is clearly a good idea
stream.Stream.register_method("tcp", TCPStream)
stream.Stream.register_method("ssl", SSLStream)
