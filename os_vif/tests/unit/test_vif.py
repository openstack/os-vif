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


class TestVIFS(base.TestCase):

    def setUp(self):
        super(TestVIFS, self).setUp()

        os_vif.objects.register_all()

    def _test_vif(self, cls, **kwargs):
        vif = cls(**kwargs)

        prim = vif.obj_to_primitive()
        self.assertEqual("os_vif", prim["versioned_object.namespace"])
        vif2 = objects.vif.VIFBase.obj_from_primitive(prim)

        # The __eq__ function works by using obj_to_primitive()
        # and this includes a list of changed fields. Very
        # occassionally the ordering of the list of changes
        # varies, causing bogus equality failures. This is
        # arguably a bug in oslo.versionedobjects since the
        # set of changes fields should not affect equality
        # comparisons. Remove this hack once this is fixed:
        #
        # https://bugs.launchpad.net/oslo.versionedobjects/+bug/1563787
        vif.obj_reset_changes(recursive=True)
        vif2.obj_reset_changes(recursive=True)

        self.assertEqual(vif, vif2)

    def test_vif_generic(self):
        self._test_vif(objects.vif.VIFGeneric,
                       vif_name="vif123")

    def test_vif_bridge_plain(self):
        self._test_vif(objects.vif.VIFBridge,
                       vif_name="vif123",
                       bridge_name="br0")

    def test_vif_bridge_ovs(self):
        prof = objects.vif.VIFPortProfileOpenVSwitch(
            interface_id="07bd6cea-fb37-4594-b769-90fc51854ee9",
            profile_id="fishfood")
        self._test_vif(objects.vif.VIFOpenVSwitch,
                       vif_name="vif123",
                       bridge_name="br0",
                       port_profile=prof)

    def test_vif_direct_plain(self):
        self._test_vif(objects.vif.VIFDirect,
                       vif_name="vif123",
                       dev_address="0002:24:12.3")

    def test_vif_direct_vepa_qbg(self):
        prof = objects.vif.VIFPortProfile8021Qbg(
            manager_id=8,
            type_id=23,
            type_id_version=523,
            instance_id="72a00fee-2fbb-43e6-a592-c858d056fcfc")
        self._test_vif(objects.vif.VIFDirect,
                       vif_name="vif123",
                       port_profile=prof,
                       dev_address="0002:24:12.3")

    def test_vif_direct_vepa_qbh(self):
        prof = objects.vif.VIFPortProfile8021Qbh(
            profile_id="fishfood")
        self._test_vif(objects.vif.VIFDirect,
                       vif_name="vif123",
                       port_profile=prof,
                       dev_address="0002:24:12.3")

    def test_vif_vhost_user(self):
        self._test_vif(objects.vif.VIFVHostUser,
                       path="/some/socket.path",
                       mode=objects.fields.VIFVHostUserMode.CLIENT,
                       vif_name="vhu123")

    def test_vif_vhost_user_fp_ovs(self):
        prof = objects.vif.VIFPortProfileFPOpenVSwitch(
            interface_id="07bd6cea-fb37-4594-b769-90fc51854ee8",
            profile_id="fishfood",
            bridge_name="br-int",
            hybrid_plug=False)
        self._test_vif(objects.vif.VIFVHostUser,
                       path="/some/socket.path",
                       mode=objects.fields.VIFVHostUserMode.CLIENT,
                       vif_name="tap123",
                       port_profile=prof)

    def test_vif_vhost_user_ovs_representor(self):
        prof = objects.vif.VIFPortProfileOVSRepresentor(
            interface_id="07bd6cea-fb37-4594-b769-90fc51854ee8",
            profile_id="fishfood",
            representor_name="tap123",
            representor_address="0002:24:12.3")
        self._test_vif(objects.vif.VIFVHostUser,
                       path="/some/socket.path",
                       mode=objects.fields.VIFVHostUserMode.CLIENT,
                       vif_name="tap123",
                       port_profile=prof)

    def test_vif_vhost_user_fp_lb(self):
        prof = objects.vif.VIFPortProfileFPBridge(bridge_name="brq456")
        self._test_vif(objects.vif.VIFVHostUser,
                       path="/some/socket.path",
                       mode=objects.fields.VIFVHostUserMode.CLIENT,
                       vif_name="tap123",
                       port_profile=prof)

    def test_vif_vhost_user_fp_tap(self):
        prof = objects.vif.VIFPortProfileFPTap(mac_address="fa:16:3e:4c:2c:30")
        self._test_vif(objects.vif.VIFVHostUser,
                       path="/some/socket.path",
                       mode=objects.fields.VIFVHostUserMode.CLIENT,
                       vif_name="tap123",
                       port_profile=prof)

    def test_vif_host_dev_plain(self):
        self._test_vif(
            objects.vif.VIFHostDevice,
            dev_type=objects.fields.VIFHostDeviceDevType.ETHERNET,
            dev_address="0002:24:12.3")

    def test_vif_host_dev_vepa_qbh(self):
        prof = objects.vif.VIFPortProfile8021Qbh(
            profile_id="fishfood")
        self._test_vif(objects.vif.VIFHostDevice,
                       dev_address="0002:24:12.3",
                       port_profile=prof)

object_data = {
    'HostInfo': '1.0-4dba5ce236ea2dc559de8764995dd247',
    'HostPluginInfo': '1.0-5204e579864981c9891ecb5d1c9329f2',
    'HostVIFInfo': '1.0-9866583de62ae23cc868ce45f402da6d',
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
    'VIFPortProfileOpenVSwitch': '1.0-533126c2a16b1a40ddf38c33e7b1f1c5',
    'VIFPortProfileFPOpenVSwitch': '1.0-9fc1799cb0adcd469481653b0420dc5e',
    'VIFPortProfileFPBridge': '1.0-d50872b3cddd245ffebef6053dfbe27a',
    'VIFPortProfileFPTap': '1.0-11670d8dbabd772ff0da26961adadc5a',
    'VIFVHostUser': '1.1-1f95b43be1f884f090ca1f4d79adfd35',
    'VIFPortProfileOVSRepresentor': '1.0-d1b67d954bcab8378c8064771d62ecd5',
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
