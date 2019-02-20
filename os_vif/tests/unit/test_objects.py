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

from oslo_versionedobjects import base as ovo_base
from oslo_versionedobjects import fixture

import os_vif
from os_vif import objects
from os_vif.tests.unit import base


object_data = {
    'HostInfo': '1.0-4dba5ce236ea2dc559de8764995dd247',
    'HostPluginInfo': '1.0-5204e579864981c9891ecb5d1c9329f2',
    'HostPortProfileInfo': '1.0-e0bc9228c1456b220830d67b05bc4bf2',
    'HostVIFInfo': '1.1-00fdbeba3f9bb3bd2a723c17023ba182',
    'FixedIP': '1.0-d1a0ec7e7b6ce021a784c54d44cce009',
    'FixedIPList': '1.0-15ecf022a68ddbb8c2a6739cfc9f8f5e',
    'InstanceInfo': '1.0-84104d3435046b1a282ac8265ec2a976',
    'Network': '1.1-27a8a3e236d1d239121668a590130154',
    'Route': '1.0-5ca049cb82c4d4ec5edb1b839c1429c7',
    'RouteList': '1.0-15ecf022a68ddbb8c2a6739cfc9f8f5e',
    'Subnet': '1.0-6a8c192ef7492120d1a5e0fd08e44272',
    'SubnetList': '1.0-15ecf022a68ddbb8c2a6739cfc9f8f5e',
    'VIFBase': '1.0-4a5a8881dc999752cb050dd443458b6a',
    'VIFBridge': '1.0-e78d355f3505361fafbf0797ffad484a',
    'VIFDirect': '1.0-05c939280f4025fd1f7efb921a835c57',
    'VIFGeneric': '1.0-c72e637ed620f0135ea50a9409a3f389',
    'VIFHostDevice': '1.0-bb090f1869c3b4df36efda216ab97a61',
    'VIFOpenVSwitch': '1.0-e78d355f3505361fafbf0797ffad484a',
    'VIFPortProfile8021Qbg': '1.1-b3011621809dca9216b50579ce9d6b19',
    'VIFPortProfile8021Qbh': '1.1-226b61b2e76ba452f7b31530cff80ac9',
    'VIFPortProfileBase': '1.1-4982d1621df12ebd1f3b07948f3d0e5f',
    'VIFPortProfileOpenVSwitch': '1.3-1ad9a350a9cae19c977d21fcce7c8c7f',
    'VIFPortProfileFPOpenVSwitch': '1.3-06c425743430e7702ef112e09b987346',
    'VIFPortProfileFPBridge': '1.1-49f1952bf50bab7a95112c908534751f',
    'VIFPortProfileFPTap': '1.1-fd178229477604dfb65de5ce929488e5',
    'VIFVHostUser': '1.1-1f95b43be1f884f090ca1f4d79adfd35',
    'VIFPortProfileOVSRepresentor': '1.3-f625e17143473b93d6c7f97ded9f785a',
    'VIFNestedDPDK': '1.0-fdbaf6b20afd116529929b21aa7158dc',
    'VIFPortProfileK8sDPDK': '1.1-e2a2abd112b14e0239e76b99d9b252ae',
    'DatapathOffloadBase': '1.0-77509ea1ea0dd750d5864b9bd87d3f9d',
    'DatapathOffloadRepresentor': '1.0-802a5dff22f73046df3742c815c51421',
}


class TestObjectVersions(base.TestCase):
    def setUp(self):
        super(TestObjectVersions, self).setUp()

        os_vif.objects.register_all()

    def test_versions(self):
        checker = fixture.ObjectVersionChecker(
            ovo_base.VersionedObjectRegistry.obj_classes())

        expected, actual = checker.test_hashes(object_data)
        self.assertEqual(expected, actual,
                         'Some objects have changed; please make sure the '
                         'versions have been bumped, and then update their '
                         'hashes here.')

    def test_vif_vhost_user_obj_make_compatible(self):
        vif = objects.vif.VIFVHostUser(
                path="/some/socket.path",
                mode=objects.fields.VIFVHostUserMode.CLIENT,
                vif_name="vhu123")
        primitive = vif.obj_to_primitive()['versioned_object.data']
        self.assertIn('vif_name', primitive)
        vif.obj_make_compatible(primitive, '1.0')
        self.assertNotIn('vif_name', primitive)
