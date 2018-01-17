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

import re

from oslo_concurrency import processutils
from oslo_utils import excutils

from os_vif.internal.command.ip import api


def _execute_command(*args):
    return processutils.execute(*args)


class ShellIpCommands(object):

    def __init__(self, cmd=_execute_command):
        self._execute_command = cmd

    def add_device(self, device, dev_type, peer=None, link=None,
                   vlan_id=None):
        ret = None
        if 'vlan' == dev_type:
            ret = self._execute_command('ip', 'link', 'add', 'link', link,
                                        'name', device, 'type', dev_type,
                                        'id', vlan_id)
        elif 'veth' == dev_type:
            ret = self._execute_command('ip', 'link', 'add', device, 'type',
                                        dev_type, 'peer', 'name', peer)
        elif 'dummy' == dev_type:
            ret = self._execute_command('ip', 'link', 'add', device,
                                        'type', dev_type)
        return ret

    def del_device(self, device):
        ret = None
        if self.exist_device(device):
            ret = self._execute_command('ip', 'link', 'del', device)
        return ret

    def set(self, device, status=None, **kwargs):
        args = ['ip', 'link', 'set', device]
        if status is not None:
            args.append(status)
        temp = [x for x in kwargs.items()]
        for x in temp:
            args += x
        self._execute_command(*args)

    def set_status_up(self, device):
        self.set(device, status='up')

    def set_status_down(self, device):
        self.set(device, status='down')

    def set_device_mtu(self, device, mtu):
        args = {'mtu': mtu}
        self.set(device, args)

    def show_device(self, device):
        val, err = _execute_command('ip', 'link', 'show', device)
        return val.splitlines()

    def exist_device(self, device):
        try:
            self._execute_command('ip', 'link', 'show', device)
            return True
        except processutils.ProcessExecutionError as e:
            with excutils.save_and_reraise_exception() as saved_exception:
                if e.exit_code == 1:
                    saved_exception.reraise = False
                    return False

    def show_state(self, device):
        regex = re.compile(r".*state (?P<state>\w+)")
        match = regex.match(self.show_device(device)[0])
        if match is None:
            return
        return match.group('state')

    def show_promisc(self, device):
        regex = re.compile(r".*(PROMISC)")
        match = regex.match(self.show_device(device)[0])
        return True if match else False

    def show_mac(self, device):
        exp = r".*link/ether (?P<mac>([0-9A-Fa-f]{2}[:]){5}[0-9A-Fa-f]{2})"
        regex = re.compile(exp)
        match = regex.match(self.show_device(device)[1])
        if match is None:
            return
        return match.group('mac')

    def show_mtu(self, device):
        regex = re.compile(r".*mtu (?P<mtu>\d+)")
        match = regex.match(self.show_device(device)[0])
        if match is None:
            return
        return int(match.group('mtu'))


class IPTools(api.IpCommand):

    def __init__(self, cmd=_execute_command):
        self.ip = ShellIpCommands(cmd=cmd)

    def set(self, device, check_exit_code=None, state=None, mtu=None,
            address=None, promisc=None):
        args = {}
        if mtu is not None:
            args['mtu'] = mtu
        if address is not None:
            args['address'] = address
        if promisc is not None:
            args['promisc'] = 'on' if promisc else 'off'

        if isinstance(check_exit_code, int):
            check_exit_code = [check_exit_code]
        return self.ip.set(device, status=state, **args)

    def add(self, device, dev_type, check_exit_code=None, peer=None, link=None,
            vlan_id=None):

        return self.ip.add_device(device, dev_type, peer=peer,
                                  link=link, vlan_id=vlan_id)

    def delete(self, device, check_exit_code=None):
        return self.ip.del_device(device)
