# Copyright (c) 2021 OpenStack Foundation.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import os_vif

if TYPE_CHECKING:
    from oslo_config import cfg

    from os_vif import plugin


__all__ = [
    'list_plugins_opts',
]

os_vif.initialize()

if os_vif._EXT_MANAGER is None:
    raise RuntimeError('os_vif is not initialized')

plugins_list: list[tuple[str, plugin.PluginBase | None]]
plugins_list = [
    (name, os_vif._EXT_MANAGER[name].obj)
    for name in sorted(os_vif._EXT_MANAGER.names())
]


def list_plugins_opts() -> list[tuple[str, list[cfg.Opt]]]:
    return [
        ('os_vif_' + g, copy.deepcopy(o.CONFIG_OPTS))
        for g, o in plugins_list if o is not None
    ]
