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
    'VIFPortProfile8021Qbg': '1.0-167f305f6e982b9368cc38763815d429',
    'VIFPortProfile8021Qbh': '1.0-4b945f07d2666ab00a48d1dc225669b1',
    'VIFPortProfileBase': '1.0-77509ea1ea0dd750d5864b9bd87d3f9d',
    'VIFPortProfileOpenVSwitch': '1.1-70d36e09c8d800345ce71177265212df',
    'VIFPortProfileFPOpenVSwitch': '1.1-74e77f46aa5806930df6f37a0b76ff8b',
    'VIFPortProfileFPBridge': '1.0-d50872b3cddd245ffebef6053dfbe27a',
    'VIFPortProfileFPTap': '1.0-11670d8dbabd772ff0da26961adadc5a',
    'VIFVHostUser': '1.1-1f95b43be1f884f090ca1f4d79adfd35',
    'VIFPortProfileOVSRepresentor': '1.1-30e555981003a109b133da5b43ded5df',
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
