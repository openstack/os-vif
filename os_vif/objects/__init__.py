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


def register_all():
    __import__('os_vif.objects.fixed_ip')
    __import__('os_vif.objects.host_info')
    __import__('os_vif.objects.instance_info')
    __import__('os_vif.objects.network')
    __import__('os_vif.objects.route')
    __import__('os_vif.objects.subnet')
    __import__('os_vif.objects.vif')
