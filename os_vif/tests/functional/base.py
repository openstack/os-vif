#    Derived from: neutron/tests/functional/base.py
#                  neutron/tests/base.py
#
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

import abc
import functools
import inspect
import os
import sys

import eventlet.timeout
from os_vif import version as osvif_version
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import fileutils
from oslotest import base


CONF = cfg.CONF
LOG = logging.getLogger(__name__)


def _get_test_log_path():
    return os.environ.get('OS_LOG_PATH', '/tmp')


# This is the directory from which infra fetches log files for functional tests
DEFAULT_LOG_DIR = os.path.join(_get_test_log_path(), 'osvif-functional-logs')


def wait_until_true(predicate, timeout=15, sleep=1):
    """Wait until callable predicate is evaluated as True

    :param predicate: Callable deciding whether waiting should continue.
                      Best practice is to instantiate predicate with
                      ``functools.partial()``.
    :param timeout: Timeout in seconds how long should function wait.
    :param sleep: Polling interval for results in seconds.
    :return: True if the predicate is evaluated as True within the timeout,
             False in case of timeout evaluating the predicate.
    """
    try:
        with eventlet.Timeout(timeout):
            while not predicate():
                eventlet.sleep(sleep)
    except eventlet.Timeout:
        return False
    return True


class _CatchTimeoutMetaclass(abc.ABCMeta):
    def __init__(cls, name, bases, dct):
        super(_CatchTimeoutMetaclass, cls).__init__(name, bases, dct)
        for name, method in inspect.getmembers(
                # NOTE(ihrachys): we should use isroutine because it will catch
                # both unbound methods (python2) and functions (python3)
                cls, predicate=inspect.isroutine):
            if name.startswith('test_'):
                setattr(cls, name, cls._catch_timeout(method))

    @staticmethod
    def _catch_timeout(f):
        @functools.wraps(f)
        def func(self, *args, **kwargs):
            try:
                return f(self, *args, **kwargs)
            except eventlet.Timeout as e:
                self.fail('Execution of this test timed out: %s' % e)
        return func


def setup_logging(component_name):
    """Sets up the logging options for a log with supplied name."""
    logging.setup(cfg.CONF, component_name)
    LOG.info("Logging enabled!")
    LOG.info("%(prog)s version %(version)s",
             {'prog': sys.argv[0], 'version': osvif_version.__version__})
    LOG.debug("command line: %s", " ".join(sys.argv))


def sanitize_log_path(path):
    """Sanitize the string so that its log path is shell friendly"""
    return path.replace(' ', '-').replace('(', '_').replace(')', '_')


# Test worker cannot survive eventlet's Timeout exception, which effectively
# kills the whole worker, with all test cases scheduled to it. This metaclass
# makes all test cases convert Timeout exceptions into unittest friendly
# failure mode (self.fail).
class BaseFunctionalTestCase(base.BaseTestCase,
                             metaclass=_CatchTimeoutMetaclass):
    """Base class for functional tests."""

    COMPONENT_NAME = 'os_vif'
    PRIVILEGED_GROUP = 'os_vif_privileged'

    def setUp(self):
        super(BaseFunctionalTestCase, self).setUp()
        logging.register_options(CONF)
        setup_logging(self.COMPONENT_NAME)
        fileutils.ensure_tree(DEFAULT_LOG_DIR, mode=0o755)
        log_file = sanitize_log_path(
            os.path.join(DEFAULT_LOG_DIR, "%s.txt" % self.id()))
        self.flags(log_file=log_file)
        privsep_helper = os.path.join(
            os.getenv('VIRTUAL_ENV', os.path.dirname(sys.executable)[:-4]),
            'bin', 'privsep-helper')
        self.flags(
            helper_command=' '.join(['sudo', '-E', privsep_helper]),
            group=self.PRIVILEGED_GROUP)

    def flags(self, **kw):
        """Override some configuration values.

        The keyword arguments are the names of configuration options to
        override and their values.

        If a group argument is supplied, the overrides are applied to
        the specified configuration option group.

        All overrides are automatically cleared at the end of the current
        test by the fixtures cleanup process.
        """
        group = kw.pop('group', None)
        for k, v in kw.items():
            CONF.set_override(k, v, group)
