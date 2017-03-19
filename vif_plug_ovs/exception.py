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

from os_vif.i18n import _

from os_vif import exception as osv_exception


class AgentError(osv_exception.ExceptionBase):
    msg_fmt = _('Error during following call to agent: %(method)s')


class MissingPortProfile(osv_exception.ExceptionBase):
    msg_fmt = _('A port profile is mandatory for the OpenVSwitch plugin')


class WrongPortProfile(osv_exception.ExceptionBase):
    msg_fmt = _('Port profile %(profile)s is not a subclass '
                'of VIFPortProfileOpenVSwitch')


class RepresentorNotFound(osv_exception.ExceptionBase):
    msg_fmt = _('Failed getting representor port for PF %(ifname)s with '
                '%(vf_num)s')


class PciDeviceNotFoundById(osv_exception.ExceptionBase):
    msg_fmt = _("PCI device %(id)s not found")
