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
import six
import testtools

from os_vif import objects

from vif_plug_ovs import linux_net
from vif_plug_ovs import ovs


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
            id='437c6db5-4e6f-4b43-b64b-ed6a11ee5ba7',
            bridge='br0',
            subnets=self.subnets,
            vlan=99)

        self.profile_ovs = objects.vif.VIFPortProfileOpenVSwitch(
            interface_id='e65867e0-9340-4a7f-a256-09af6eb7a3aa')
        self.vif_ovs = objects.vif.VIFBridge(
            id='b679325f-ca89-4ee0-a8be-6db1409b69ea',
            address='ca:fe:de:ad:be:ef',
            network=self.network_ovs,
            dev_name='tap-xxx-yyy-zzz',
            bridge_name="qbrvif-xxx-yyy",
            port_profile=self.profile_ovs)

        self.instance = objects.instance_info.InstanceInfo(
            name='demo',
            uuid='f0000000-0000-0000-0000-000000000001')

    def test_plug_ovs_bridge(self):
        calls = {
            'device_exists': [mock.call('qvob679325f-ca')],
            'create_veth_pair': [mock.call('qvbb679325f-ca',
                                           'qvob679325f-ca',
                                           1500)],
            'ensure_bridge': [mock.call('qbrvif-xxx-yyy')],
            'add_bridge_port': [mock.call('qbrvif-xxx-yyy',
                                          'qvbb679325f-ca')],
            'create_ovs_vif_port': [mock.call(
                                    'br0', 'qvob679325f-ca',
                                    'e65867e0-9340-4a7f-a256-09af6eb7a3aa',
                                    'ca:fe:de:ad:be:ef',
                                    'f0000000-0000-0000-0000-000000000001',
                                    1500,
                                    timeout=120)]
        }

        with nested(
                mock.patch.object(linux_net, 'ensure_bridge'),
                mock.patch.object(linux_net, 'device_exists',
                                  return_value=False),
                mock.patch.object(linux_net, 'create_veth_pair'),
                mock.patch.object(linux_net, 'add_bridge_port'),
                mock.patch.object(linux_net, 'create_ovs_vif_port')
        ) as (ensure_bridge, device_exists, create_veth_pair,
              add_bridge_port, create_ovs_vif_port):
            plugin = ovs.OvsPlugin.load("ovs")
            plugin.plug(self.vif_ovs, self.instance)
            ensure_bridge.assert_has_calls(calls['ensure_bridge'])
            device_exists.assert_has_calls(calls['device_exists'])
            create_veth_pair.assert_has_calls(calls['create_veth_pair'])
            add_bridge_port.assert_has_calls(calls['add_bridge_port'])
            create_ovs_vif_port.assert_has_calls(calls['create_ovs_vif_port'])

    def test_unplug_ovs_bridge(self):
        calls = {
            'delete_bridge': [mock.call('qbrvif-xxx-yyy', 'qvbb679325f-ca')],
            'delete_ovs_vif_port': [mock.call('br0', 'qvob679325f-ca',
                                    timeout=120)]
        }
        with nested(
                mock.patch.object(linux_net, 'delete_bridge'),
                mock.patch.object(linux_net, 'delete_ovs_vif_port')
        ) as (delete_bridge, delete_ovs_vif_port):
            plugin = ovs.OvsPlugin.load("ovs")
            plugin.unplug(self.vif_ovs, self.instance)
            delete_bridge.assert_has_calls(calls['delete_bridge'])
            delete_ovs_vif_port.assert_has_calls(calls['delete_ovs_vif_port'])
