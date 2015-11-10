#    Copyright 2016 Red Hat, Inc.
#
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

from oslo_versionedobjects import fields

from os_vif.i18n import _LE

import re


class PCIAddress(fields.FieldType):
    @staticmethod
    def coerce(obj, attr, value):
        m = "[0-9a-f]{1,4}:[0-9a-f]{1,2}:[0-9a-f]{1,2}.[0-9a-f]"
        newvalue = value.lower()
        if not re.match(m, newvalue):
            raise ValueError(_LE("Malformed PCI address %s"), value)
        return newvalue


class PCIAddressField(fields.AutoTypedField):
    AUTO_TYPE = PCIAddress()


class VIFDirectMode(fields.Enum):
    VEPA = 'vepa'
    PASSTHROUGH = 'passthrough'
    BRIDGE = 'bridge'

    ALL = (VEPA, PASSTHROUGH, BRIDGE)

    def __init__(self):
        super(VIFDirectMode, self).__init__(
            valid_values=VIFDirectMode.ALL)


class VIFDirectModeField(fields.BaseEnumField):
    AUTO_TYPE = VIFDirectMode()


class VIFVHostUserMode(fields.Enum):
    CLIENT = "client"
    SERVER = "server"

    ALL = (CLIENT, SERVER)

    def __init__(self):
        super(VIFVHostUserMode, self).__init__(
            valid_values=VIFVHostUserMode.ALL)


class VIFVHostUserModeField(fields.BaseEnumField):
    AUTO_TYPE = VIFVHostUserMode()
