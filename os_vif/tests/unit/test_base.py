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

import copy

from unittest import mock

from oslo_serialization import jsonutils
from oslo_versionedobjects import base
from oslo_versionedobjects import fields

from os_vif.objects import base as osv_base
from os_vif.tests.unit import base as test_base


class TestVersionedObjectPrintable(test_base.TestCase):
    @base.VersionedObjectRegistry.register_if(False)
    class OVOChild1(osv_base.VersionedObject,
                    osv_base.VersionedObjectPrintableMixin):
        fields = {
            "child1_field1": fields.ListOfIntegersField()
        }

    @base.VersionedObjectRegistry.register_if(False)
    class OVOParent(osv_base.VersionedObject,
                    osv_base.VersionedObjectPrintableMixin,
                    base.ComparableVersionedObject):
        fields = {
            "parent_field1": fields.ListOfObjectsField("OVOChild1"),
            "parent_field2": fields.StringField(),
        }

    def setUp(self):
        super(TestVersionedObjectPrintable, self).setUp()
        child1_1 = self.OVOChild1(child1_field1=[1, 2, 3])
        child1_2 = self.OVOChild1(child1_field1=[4, 5, 6])
        self.obj = self.OVOParent(
            parent_field1=[child1_1, child1_2],
            parent_field2="test string")

    def test_print_object(self):
        out = str(self.obj)
        self.assertIn("'child1_field1': [1, 2, 3]}", out)
        self.assertIn("'child1_field1': [4, 5, 6]}", out)
        cmp = str({'parent_field2': "test string"})
        cmp = cmp.replace('{', '').replace('}', '')
        self.assertIn(str(cmp), out)

    @mock.patch.object(base.VersionedObject, "obj_class_from_name",
                       side_effect=[OVOParent, OVOChild1, OVOChild1])
    def test_serialize_object(self, *mock):
        """Test jsonutils serialization is not affected by this new mixin."""
        obj_orig = copy.deepcopy(self.obj)
        obj_orig_primitive = obj_orig.obj_to_primitive()
        str_orig_primitive = jsonutils.dumps(obj_orig_primitive)
        obj_new_primitive = jsonutils.loads(str_orig_primitive)
        obj_new = self.OVOParent.obj_from_primitive(obj_new_primitive)
        self.assertEqual(obj_orig_primitive, obj_new_primitive)
        self.assertEqual(obj_orig, obj_new)

    def test_import_non_ovo_class(self):
        """Test VersionedObjectPrintable could be inherited by non-OVO classes.
        """
        class NonOVOClass(osv_base.VersionedObjectPrintableMixin):
            def __str__(self):
                return "NonOVOClass __str__ method"

        self.assertEqual("NonOVOClass __str__ method", str(NonOVOClass()))
