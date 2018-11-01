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

import os

from oslo_log import log as logging
from oslo_utils import importutils


LOG = logging.getLogger(__name__)


def _get_impl():
    if os.name == 'nt':
        impl = 'os_vif.internal.command.ip.windows.impl_netifaces.Netifaces'
    else:
        impl = 'os_vif.internal.command.ip.linux.impl_pyroute2.PyRoute2'

    return importutils.import_object(impl)
