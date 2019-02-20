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

import warnings

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

    def test_port_profile_base_backport_1_0(self):
        datapath_offload = objects.vif.DatapathOffloadRepresentor(
            representor_name="felix",
            representor_address="0002:24:12.3")
        obj = objects.vif.VIFPortProfileBase(
            datapath_offload=datapath_offload)
        primitive = obj.obj_to_primitive(target_version='1.0')
        self.assertEqual('1.0', primitive['versioned_object.version'])
        data = primitive['versioned_object.data']
        self.assertNotIn('datapath_type', data)

    def test_vif_bridge_ovs(self):
        prof = objects.vif.VIFPortProfileOpenVSwitch(
            interface_id="07bd6cea-fb37-4594-b769-90fc51854ee9",
            profile_id="fishfood",
            datapath_type='netdev')
        self._test_vif(objects.vif.VIFOpenVSwitch,
                       vif_name="vif123",
                       bridge_name="br0",
                       port_profile=prof)

    def test_port_profile_ovs_backport_1_0(self):
        obj = objects.vif.VIFPortProfileOpenVSwitch(
            interface_id="07bd6cea-fb37-4594-b769-90fc51854ee9",
            profile_id="fishfood",
            datapath_type='netdev')
        primitive = obj.obj_to_primitive(target_version='1.0')
        self.assertEqual('1.0', primitive['versioned_object.version'])
        data = primitive['versioned_object.data']
        self.assertEqual('07bd6cea-fb37-4594-b769-90fc51854ee9',
                         data['interface_id'])
        self.assertEqual('fishfood', data['profile_id'])
        self.assertNotIn('datapath_type', data)

    def test_port_profile_ovs_backport_1_1(self):
        datapath_offload = objects.vif.DatapathOffloadRepresentor(
            representor_name="felix",
            representor_address="0002:24:12.3")
        obj = objects.vif.VIFPortProfileOpenVSwitch(
            interface_id="07bd6cea-fb37-4594-b769-90fc51854ee9",
            profile_id="fishfood",
            datapath_type='netdev',
            datapath_offload=datapath_offload)
        primitive = obj.obj_to_primitive(target_version='1.1')
        self.assertEqual('1.1', primitive['versioned_object.version'])
        data = primitive['versioned_object.data']
        self.assertEqual('07bd6cea-fb37-4594-b769-90fc51854ee9',
                         data['interface_id'])
        self.assertEqual('fishfood', data['profile_id'])
        self.assertEqual('netdev', data['datapath_type'])
        self.assertNotIn('datapath_offload', data)

    def test_port_profile_ovs_backport_1_2(self):
        obj = objects.vif.VIFPortProfileOpenVSwitch(
            interface_id="07bd6cea-fb37-4594-b769-90fc51854ee9",
            create_port=True)
        primitive = obj.obj_to_primitive(target_version='1.2')
        self.assertEqual('1.2', primitive['versioned_object.version'])
        data = primitive['versioned_object.data']
        self.assertEqual('07bd6cea-fb37-4594-b769-90fc51854ee9',
                         data['interface_id'])
        self.assertNotIn('create_port', data)

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
            datapath_type='netdev',
            bridge_name="br-int",
            hybrid_plug=False)
        self._test_vif(objects.vif.VIFVHostUser,
                       path="/some/socket.path",
                       mode=objects.fields.VIFVHostUserMode.CLIENT,
                       vif_name="tap123",
                       port_profile=prof)

    def test_port_profile_fp_ovs_backport_1_0(self):
        obj = objects.vif.VIFPortProfileFPOpenVSwitch(
            interface_id="07bd6cea-fb37-4594-b769-90fc51854ee9",
            profile_id="fishfood",
            datapath_type='netdev',
            bridge_name="br-int",
            hybrid_plug=False)
        primitive = obj.obj_to_primitive(target_version='1.0')
        self.assertEqual('1.0', primitive['versioned_object.version'])
        data = primitive['versioned_object.data']
        self.assertEqual('07bd6cea-fb37-4594-b769-90fc51854ee9',
                         data['interface_id'])
        self.assertEqual('fishfood', data['profile_id'])
        self.assertEqual('br-int', data['bridge_name'])
        self.assertEqual(False, data['hybrid_plug'])
        self.assertNotIn('datapath_type', data)

    def test_port_profile_fp_ovs_backport_1_1(self):
        datapath_offload = objects.vif.DatapathOffloadRepresentor(
            representor_name="felix",
            representor_address="0002:24:12.3")
        obj = objects.vif.VIFPortProfileFPOpenVSwitch(
            interface_id="07bd6cea-fb37-4594-b769-90fc51854ee9",
            profile_id="fishfood",
            datapath_type='netdev',
            bridge_name="br-int",
            hybrid_plug=False,
            datapath_offload=datapath_offload)
        primitive = obj.obj_to_primitive(target_version='1.1')
        self.assertEqual('1.1', primitive['versioned_object.version'])
        data = primitive['versioned_object.data']
        self.assertEqual('07bd6cea-fb37-4594-b769-90fc51854ee9',
                         data['interface_id'])
        self.assertEqual('fishfood', data['profile_id'])
        self.assertEqual('br-int', data['bridge_name'])
        self.assertEqual(False, data['hybrid_plug'])
        self.assertEqual('netdev', data['datapath_type'])
        self.assertNotIn('datapath_offload', data)

    def test_vif_vhost_user_ovs_representor(self):
        prof = objects.vif.VIFPortProfileOVSRepresentor(
            interface_id="07bd6cea-fb37-4594-b769-90fc51854ee8",
            profile_id="fishfood",
            datapath_type='netdev',
            representor_name="tap123",
            representor_address="0002:24:12.3")
        self._test_vif(objects.vif.VIFVHostUser,
                       path="/some/socket.path",
                       mode=objects.fields.VIFVHostUserMode.CLIENT,
                       vif_name="tap123",
                       port_profile=prof)

    def test_port_profile_ovs_representor_backport_1_0(self):
        obj = objects.vif.VIFPortProfileOVSRepresentor(
            interface_id="07bd6cea-fb37-4594-b769-90fc51854ee9",
            profile_id="fishfood",
            datapath_type='netdev',
            representor_name="tap123",
            representor_address="0002:24:12.3")
        primitive = obj.obj_to_primitive(target_version='1.0')
        self.assertEqual('1.0', primitive['versioned_object.version'])
        data = primitive['versioned_object.data']
        self.assertEqual('07bd6cea-fb37-4594-b769-90fc51854ee9',
                         data['interface_id'])
        self.assertEqual('fishfood', data['profile_id'])
        self.assertEqual('tap123', data['representor_name'])
        self.assertEqual("0002:24:12.3", data['representor_address'])
        self.assertNotIn('datapath_type', data)

    def test_port_profile_ovs_representor_backport_1_1(self):
        datapath_offload = objects.vif.DatapathOffloadRepresentor(
            representor_name="felix",
            representor_address="0002:24:12.3")
        obj = objects.vif.VIFPortProfileOVSRepresentor(
            interface_id="07bd6cea-fb37-4594-b769-90fc51854ee9",
            profile_id="fishfood",
            datapath_type='netdev',
            representor_name="tap123",
            representor_address="0002:24:12.3",
            datapath_offload=datapath_offload)
        primitive = obj.obj_to_primitive(target_version='1.1')
        self.assertEqual('1.1', primitive['versioned_object.version'])
        data = primitive['versioned_object.data']
        self.assertEqual('07bd6cea-fb37-4594-b769-90fc51854ee9',
                         data['interface_id'])
        self.assertEqual('fishfood', data['profile_id'])
        self.assertEqual('tap123', data['representor_name'])
        self.assertEqual("0002:24:12.3", data['representor_address'])
        self.assertEqual('netdev', data['datapath_type'])
        self.assertNotIn('datapath_offload', data)

    def test_vif_vhost_user_generic_representor(self):
        datapath_offload = objects.vif.DatapathOffloadRepresentor(
            representor_name="felix",
            representor_address="0002:24:12.3")
        prof = objects.vif.VIFPortProfileBase(
            datapath_offload=datapath_offload,
            )
        self._test_vif(objects.vif.VIFVHostUser,
                       path="/some/socket.path",
                       mode=objects.fields.VIFVHostUserMode.SERVER,
                       vif_name="felix",
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

    def test_vif_nested_dpdk_k8s(self):
        prof = objects.vif.VIFPortProfileK8sDPDK(
            l3_setup=False,
            selflink="/some/url",
            resourceversion="1")
        self._test_vif(
            objects.vif.VIFNestedDPDK,
            pci_adress="0002:24:12.3",
            dev_driver="virtio_pci",
            port_profile=prof)

    def test_port_profile_fp_bridge_backport_1_0(self):
        datapath_offload = objects.vif.DatapathOffloadRepresentor(
            representor_name="felix",
            representor_address="0002:24:12.3")
        obj = objects.vif.VIFPortProfileFPBridge(
            bridge_name='joe',
            datapath_offload=datapath_offload)
        primitive = obj.obj_to_primitive(target_version='1.0')
        self.assertEqual('1.0', primitive['versioned_object.version'])
        data = primitive['versioned_object.data']
        self.assertEqual('joe', data['bridge_name'])
        self.assertNotIn('datapath_type', data)

    def test_port_profile_fp_tap_backport_1_0(self):
        datapath_offload = objects.vif.DatapathOffloadRepresentor(
            representor_name="felix",
            representor_address="0002:24:12.3")
        obj = objects.vif.VIFPortProfileFPTap(
            mac_address='00:de:ad:be:ef:01',
            datapath_offload=datapath_offload)
        primitive = obj.obj_to_primitive(target_version='1.0')
        self.assertEqual('1.0', primitive['versioned_object.version'])
        data = primitive['versioned_object.data']
        self.assertEqual('00:de:ad:be:ef:01', data['mac_address'])
        self.assertNotIn('datapath_type', data)

    def test_port_profile_8021qbg_backport_1_0(self):
        datapath_offload = objects.vif.DatapathOffloadRepresentor(
            representor_name="felix",
            representor_address="0002:24:12.3")
        obj = objects.vif.VIFPortProfile8021Qbg(
            manager_id=42,
            type_id=43,
            type_id_version=44,
            instance_id='07bd6cea-fb37-4594-b769-90fc51854ee9',
            datapath_offload=datapath_offload)
        primitive = obj.obj_to_primitive(target_version='1.0')
        self.assertEqual('1.0', primitive['versioned_object.version'])
        data = primitive['versioned_object.data']
        self.assertEqual(42, data['manager_id'])
        self.assertEqual(43, data['type_id'])
        self.assertEqual(44, data['type_id_version'])
        self.assertEqual('07bd6cea-fb37-4594-b769-90fc51854ee9',
                         data['instance_id'])
        self.assertNotIn('datapath_type', data)

    def test_port_profile_8021qbh_backport_1_0(self):
        datapath_offload = objects.vif.DatapathOffloadRepresentor(
            representor_name="felix",
            representor_address="0002:24:12.3")
        obj = objects.vif.VIFPortProfile8021Qbh(
            profile_id='catfood',
            datapath_offload=datapath_offload)
        primitive = obj.obj_to_primitive(target_version='1.0')
        self.assertEqual('1.0', primitive['versioned_object.version'])
        data = primitive['versioned_object.data']
        self.assertEqual('catfood', data['profile_id'])
        self.assertNotIn('datapath_type', data)

    def test_port_profile_dpdk_k8s_backport_1_0(self):
        datapath_offload = objects.vif.DatapathOffloadRepresentor(
            representor_name="felix",
            representor_address="0002:24:12.3")
        obj = objects.vif.VIFPortProfileK8sDPDK(
            l3_setup=False,
            selflink="/some/url",
            resourceversion="1",
            datapath_offload=datapath_offload)
        primitive = obj.obj_to_primitive(target_version='1.0')
        self.assertEqual('1.0', primitive['versioned_object.version'])
        data = primitive['versioned_object.data']
        self.assertEqual(False, data['l3_setup'])
        self.assertEqual("/some/url", data['selflink'])
        self.assertEqual("1", data['resourceversion'])
        self.assertNotIn('datapath_type', data)

    def test_vif_host_dev_ovs_offload(self):
        datapath_offload = objects.vif.DatapathOffloadRepresentor(
            representor_name="felix",
            representor_address="0002:24:12.3")
        prof = objects.vif.VIFPortProfileOpenVSwitch(
            interface_id="07bd6cea-fb37-4594-b769-90fc51854ee8",
            profile_id="fishfood",
            datapath_type='netdev',
            datapath_offload=datapath_offload)
        self._test_vif(
            objects.vif.VIFHostDevice,
            dev_type=objects.fields.VIFHostDeviceDevType.ETHERNET,
            dev_address="0002:24:12.3",
            port_profile=prof)

    def test_pending_warnings_emitted_class_direct(self):
        with warnings.catch_warnings(record=True) as capture:
            warnings.simplefilter("always")
            pp = objects.vif.VIFPortProfileOVSRepresentor()
        self.assertEqual(1, len(capture))
        w = capture[0]
        self.assertEqual(PendingDeprecationWarning, w.category)
        self.assertEqual(pp.VERSION,
            objects.vif.VIFPortProfileOVSRepresentor.VERSION)
