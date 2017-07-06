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

import six

from os_vif import exception
from os_vif.tests.unit import base

"""Mostly inspired by os-brick's tests."""


class VIFExceptionTestCase(base.TestCase):
    def test_default_error_msg(self):
        class FakeVIFException(exception.ExceptionBase):
            msg_fmt = "default message"

        exc = FakeVIFException()
        self.assertEqual(six.text_type(exc), 'default message')

    def test_error_msg(self):
        self.assertEqual(six.text_type(exception.ExceptionBase('test')),
                         'test')

    def test_default_error_msg_with_kwargs(self):
        class FakeVIFException(exception.ExceptionBase):
            msg_fmt = "default message: %(foo)s"

        exc = FakeVIFException(foo="bar")
        self.assertEqual(six.text_type(exc), 'default message: bar')
