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

import os_vif
from os_vif import objects
from os_vif.tests import base


class TestVIFS(base.TestCase):

    def setUp(self):
        super(TestVIFS, self).setUp()

        os_vif.objects.register_all()

    def _test_vif(self, cls, **kwargs):
        vif = cls(**kwargs)

        prim = vif.obj_to_primitive()
        vif2 = objects.vif.VIFBase.obj_from_primitive(prim)

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
                       dev_name="eth0")

    def test_vif_direct_vepa_qbg(self):
        prof = objects.vif.VIFPortProfile8021Qbg(
            manager_id=8,
            type_id=23,
            type_id_version=523,
            instance_id="72a00fee-2fbb-43e6-a592-c858d056fcfc")
        self._test_vif(objects.vif.VIFDirect,
                       vif_name="vif123",
                       dev_name="eth0",
                       port_profile=prof)

    def test_vif_direct_vepa_qbh(self):
        prof = objects.vif.VIFPortProfile8021Qbh(
            profile_id="fishfood")
        self._test_vif(objects.vif.VIFDirect,
                       vif_name="vif123",
                       dev_name="eth0",
                       port_profile=prof)

    def test_vif_vhost_user(self):
        self._test_vif(objects.vif.VIFVHostUser,
                       path="/some/socket.path",
                       mode=objects.fields.VIFVHostUserMode.CLIENT)

    def test_vif_host_dev_plain(self):
        self._test_vif(objects.vif.VIFHostDevice,
                       dev_address="0002:24:12.3",
                       vlan=8)

    def test_vif_host_dev_vepa_qbh(self):
        prof = objects.vif.VIFPortProfile8021Qbh(
            profile_id="fishfood")
        self._test_vif(objects.vif.VIFHostDevice,
                       dev_address="0002:24:12.3",
                       vlan=8,
                       port_profile=prof)
