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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # mypy doesn't execute code, so it has no way to realize that we're
    # dynamically registering these objects on the 'os_vif.objects' class thus
    # we have to do so ourselves

    from os_vif.objects.fixed_ip import FixedIP, FixedIPList
    from os_vif.objects.host_info import (
        HostPortProfileInfo,
        HostVIFInfo,
        HostPluginInfo,
        HostInfo,
    )
    from os_vif.objects.instance_info import InstanceInfo
    from os_vif.objects.network import Network
    from os_vif.objects.route import Route, RouteList
    from os_vif.objects.subnet import Subnet, SubnetList
    from os_vif.objects.vif import (
        VIFBase,
        VIFGeneric,
        VIFBridge,
        VIFOpenVSwitch,
        VIFDirect,
        VIFVHostUser,
        VIFHostDevice,
        VIFNestedDPDK,
        DatapathOffloadBase,
        DatapathOffloadRepresentor,
        VIFPortProfileBase,
        VIFPortProfileOpenVSwitch,
        VIFPortProfileFPOpenVSwitch,
        VIFPortProfileOVSRepresentor,
        VIFPortProfileFPBridge,
        VIFPortProfileFPTap,
        VIFPortProfile8021Qbg,
        VIFPortProfile8021Qbh,
        VIFPortProfileK8sDPDK,
    )

    __all__ = [
        'FixedIP',
        'FixedIPList',
        'HostPortProfileInfo',
        'HostVIFInfo',
        'HostPluginInfo',
        'HostInfo',
        'InstanceInfo',
        'Network',
        'Route',
        'RouteList',
        'Subnet',
        'SubnetList',
        'VIFBase',
        'VIFGeneric',
        'VIFBridge',
        'VIFOpenVSwitch',
        'VIFDirect',
        'VIFVHostUser',
        'VIFHostDevice',
        'VIFNestedDPDK',
        'DatapathOffloadBase',
        'DatapathOffloadRepresentor',
        'VIFPortProfileBase',
        'VIFPortProfileOpenVSwitch',
        'VIFPortProfileFPOpenVSwitch',
        'VIFPortProfileOVSRepresentor',
        'VIFPortProfileFPBridge',
        'VIFPortProfileFPTap',
        'VIFPortProfile8021Qbg',
        'VIFPortProfile8021Qbh',
        'VIFPortProfileK8sDPDK',
    ]


def register_all() -> None:
    __import__('os_vif.objects.fixed_ip')
    __import__('os_vif.objects.host_info')
    __import__('os_vif.objects.instance_info')
    __import__('os_vif.objects.network')
    __import__('os_vif.objects.route')
    __import__('os_vif.objects.subnet')
    __import__('os_vif.objects.vif')
