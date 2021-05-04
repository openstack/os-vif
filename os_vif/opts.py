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

__all__ = [
    'list_plugins_opts',
]

from copy import deepcopy
import os_vif


os_vif.initialize()

_EXT_MANAGER = os_vif._EXT_MANAGER

plugins_list = [
    (name, _EXT_MANAGER[name].obj)
    for name in sorted(_EXT_MANAGER.names())
]


def list_plugins_opts():
    return [('os_vif_' + g, deepcopy(o.CONFIG_OPTS)) for g, o in plugins_list]
