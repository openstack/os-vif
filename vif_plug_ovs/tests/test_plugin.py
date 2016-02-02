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

import contextlib
import mock
import os.path
import six
import testtools

from os_vif import objects

from oslo_concurrency import processutils

from vif_plug_ovs import linux_net
from vif_plug_ovs import ovs_hybrid


if six.PY2:
    nested = contextlib.nested
else:
    @contextlib.contextmanager
    def nested(*contexts):
        with contextlib.ExitStack() as stack:
            yield [stack.enter_context(c) for c in contexts]


class PluginTest(testtools.TestCase):

    def __init__(self, *args, **kwargs):
        super(PluginTest, self).__init__(*args, **kwargs)

        objects.register_all()

        self.subnet_bridge_4 = objects.subnet.Subnet(
            cidr='101.168.1.0/24',
            dns=['8.8.8.8'],
            gateway='101.168.1.1',
            dhcp_server='191.168.1.1')

        self.subnet_bridge_6 = objects.subnet.Subnet(
            cidr='101:1db9::/64',
            gateway='101:1db9::1')

        self.subnets = objects.subnet.SubnetList(
            objects=[self.subnet_bridge_4,
                     self.subnet_bridge_6])

        self.network_ovs = objects.network.Network(
            id='network-id-xxx-yyy-zzz',
            bridge='br0',
            subnets=self.subnets,
            vlan=99)

        self.profile_ovs = objects.vif.VIFPortProfileOpenVSwitch(
            interface_id='aaa-bbb-ccc')
        self.vif_ovs = objects.vif.VIFBridge(
            id='vif-xxx-yyy-zzz',
            address='ca:fe:de:ad:be:ef',
            network=self.network_ovs,
            dev_name='tap-xxx-yyy-zzz',
            bridge_name="qbrvif-xxx-yyy",
            port_profile=self.profile_ovs)

        self.instance = objects.instance_info.InstanceInfo(
            name='demo',
            uuid='f0000000-0000-0000-0000-000000000001')

    def _test_plug_ovs_hybrid(self, ipv6_exists):
        calls = {
            'device_exists': [mock.call('qbrvif-xxx-yyy'),
                              mock.call('qvovif-xxx-yyy')],
            '_create_veth_pair': [mock.call('qvbvif-xxx-yyy',
                                            'qvovif-xxx-yyy',
                                            1500)],
            'execute': [mock.call('brctl', 'addbr', 'qbrvif-xxx-yyy',
                                  run_as_root=True),
                        mock.call('brctl', 'setfd', 'qbrvif-xxx-yyy', 0,
                                  run_as_root=True),
                        mock.call('brctl', 'stp', 'qbrvif-xxx-yyy', 'off',
                                  run_as_root=True),
                        mock.call('tee', ('/sys/class/net/qbrvif-xxx-yyy'
                                          '/bridge/multicast_snooping'),
                                  process_input='0', run_as_root=True,
                                  check_exit_code=[0, 1])],
            'create_ovs_vif_port': [mock.call(
                                    'br0', 'qvovif-xxx-yyy', 'aaa-bbb-ccc',
                                    'ca:fe:de:ad:be:ef',
                                    'f0000000-0000-0000-0000-000000000001',
                                    timeout=120)]
        }
        # The disable_ipv6 call needs to be added in the middle, if required
        if ipv6_exists:
            calls['execute'].extend([
                mock.call('tee', ('/proc/sys/net/ipv6/conf'
                                  '/qbrvif-xxx-yyy/disable_ipv6'),
                          process_input='1', run_as_root=True,
                          check_exit_code=[0, 1])])
        calls['execute'].extend([
            mock.call('ip', 'link', 'set', 'qbrvif-xxx-yyy', 'up',
                      run_as_root=True),
            mock.call('brctl', 'addif', 'qbrvif-xxx-yyy',
                      'qvbvif-xxx-yyy', run_as_root=True)])

        with nested(
                mock.patch.object(linux_net, 'device_exists',
                                  return_value=False),
                mock.patch.object(processutils, 'execute'),
                mock.patch.object(linux_net, 'create_veth_pair'),
                mock.patch.object(linux_net, 'create_ovs_vif_port'),
                mock.patch.object(os.path, 'exists', return_value=ipv6_exists)
        ) as (device_exists, execute, _create_veth_pair, create_ovs_vif_port,
              path_exists):
            plugin = ovs_hybrid.OvsHybridPlugin.load("ovs_hybrid")
            plugin.plug(self.vif_ovs, self.instance)
            device_exists.assert_has_calls(calls['device_exists'])
            _create_veth_pair.assert_has_calls(calls['_create_veth_pair'])
            execute.assert_has_calls(calls['execute'])
            create_ovs_vif_port.assert_has_calls(calls['create_ovs_vif_port'])

    def test_plug_ovs_hybrid_ipv6(self):
        self._test_plug_ovs_hybrid(ipv6_exists=True)

    def test_plug_ovs_hybrid_no_ipv6(self):
        self._test_plug_ovs_hybrid(ipv6_exists=False)

    def test_unplug_ovs_hybrid(self):
        calls = {
            'device_exists': [mock.call('qbrvif-xxx-yyy')],
            'execute': [mock.call('brctl', 'delif', 'qbrvif-xxx-yyy',
                                  'qvbvif-xxx-yyy', run_as_root=True),
                        mock.call('ip', 'link', 'set',
                                  'qbrvif-xxx-yyy', 'down', run_as_root=True),
                        mock.call('brctl', 'delbr',
                                  'qbrvif-xxx-yyy', run_as_root=True)],
            'delete_ovs_vif_port': [mock.call('br0', 'qvovif-xxx-yyy',
                                    timeout=120)]
        }
        with nested(
                mock.patch.object(linux_net, 'device_exists',
                                  return_value=True),
                mock.patch.object(processutils, 'execute'),
                mock.patch.object(linux_net, 'delete_ovs_vif_port')
        ) as (device_exists, execute, delete_ovs_vif_port):
            plugin = ovs_hybrid.OvsHybridPlugin.load("ovs_hybrid")
            plugin.unplug(self.vif_ovs, self.instance)
            device_exists.assert_has_calls(calls['device_exists'])
            execute.assert_has_calls(calls['execute'])
            delete_ovs_vif_port.assert_has_calls(calls['delete_ovs_vif_port'])

    def test_unplug_ovs_hybrid_bridge_does_not_exist(self):
        calls = {
            'device_exists': [mock.call('qbrvif-xxx-yyy')],
            'delete_ovs_vif_port': [mock.call('br0', 'qvovif-xxx-yyy',
                                              timeout=120)]
        }
        with nested(
                mock.patch.object(linux_net, 'device_exists',
                                  return_value=False),
                mock.patch.object(linux_net, 'delete_ovs_vif_port')
        ) as (device_exists, delete_ovs_vif_port):
            plugin = ovs_hybrid.OvsHybridPlugin.load("ovs_hybrid")
            plugin.unplug(self.vif_ovs, self.instance)
            device_exists.assert_has_calls(calls['device_exists'])
            delete_ovs_vif_port.assert_has_calls(calls['delete_ovs_vif_port'])
