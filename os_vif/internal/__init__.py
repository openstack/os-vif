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

import inspect
from os import path

from os_vif import exception

os_vif_root = path.dirname(path.dirname(path.dirname(__file__)))
frames_info = inspect.getouterframes(inspect.currentframe())
for frame_info in frames_info[1:]:
    importer_filename = inspect.getframeinfo(frame_info[0]).filename
    if os_vif_root in importer_filename:
        break
else:
    raise exception.ExternalImport()
