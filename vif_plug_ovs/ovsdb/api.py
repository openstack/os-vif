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

import abc
from typing import Literal, overload, TYPE_CHECKING

if TYPE_CHECKING:
    from vif_plug_ovs.ovsdb import impl_idl
    from vif_plug_ovs.ovsdb import impl_vsctl
    from vif_plug_ovs.ovsdb import ovsdb_lib


interface_map = {
    'vsctl': 'vif_plug_ovs.ovsdb.impl_vsctl',
    'native': 'vif_plug_ovs.ovsdb.impl_idl',
}


@overload
def get_instance(
    context: ovsdb_lib.BaseOVS, iface_name: Literal['vsctl']
) -> impl_vsctl.OvsdbVsctl:
    ...


@overload
def get_instance(
    context: ovsdb_lib.BaseOVS, iface_name: Literal['native']
) -> impl_idl.NeutronOvsdbIdl:
    ...


def get_instance(
    context: ovsdb_lib.BaseOVS, iface_name: Literal['vsctl', 'native']
) -> impl_vsctl.OvsdbVsctl | impl_idl.NeutronOvsdbIdl:
    """Return the configured OVSDB API implementation"""
    match iface_name:
        case 'vsctl':
            from vif_plug_ovs.ovsdb import impl_vsctl
            return impl_vsctl.api_factory(context)
        case 'native':
            from vif_plug_ovs.ovsdb import impl_idl
            return impl_idl.api_factory(context)
        case _:
            raise ValueError(
                f'{iface_name} is not a supported backend'
            )


class ImplAPI(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def has_table_column(self, table: str, column: str) -> bool:
        """Check if a column exists in a database table

        :param table: (string) table name
        :param column: (string) column name
        :return: True if the column exists, False if not.
        """
