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

import six


class PluginVIFInfo(object):
    """
    Class describing the plugin and the versions of VIF object it understands.
    """

    def __init__(self, vif_class, min_version, max_version):
        """
        Constructs the PluginInfo object.

        :param vif_class: subclass of os_vif.objects.vif.VIF that is supported
        :param min_version: String representing the earliest version of
                            @vif_class that the plugin understands.
        :param_max_version: String representing the latest version of
                            @vif_class that the plugin understands.
        """
        self.vif_class = vif_class
        self.min_version = min_version
        self.max_version = max_version


class PluginInfo(object):
    """
    Class describing the plugin and the versions of VIF object it understands.
    """

    def __init__(self, vif_info):
        """
        Constructs the PluginInfo object.

        :param vif_info: list of PluginVIFInfo instances supported by the
                         plugin
        """
        self.vif_info = vif_info


@six.add_metaclass(abc.ABCMeta)
class PluginBase(object):
    """Base class for all VIF plugins."""

    def __init__(self, **config):
        """
        Sets up the plugin using supplied kwargs representing configuration
        options.
        """
        self.config = config

    @abs.abstractmethod
    def describe(self):
        """
        Return an object that describes the plugin's supported vif types and
        the earliest/latest known VIF object versions.

        :returns: A `os_vif.plugin.PluginInfo` instance
        """

    @abc.abstractmethod
    def plug(self, instance, vif):
        """
        Given a model of a VIF, perform operations to plug the VIF properly.

        :param instance: `nova.objects.Instance` object.
        :param vif: `os_vif.objects.VIF` object.
        :raises `processutils.ProcessExecutionError`. Plugins implementing
                this method should let `processutils.ProcessExecutionError`
                bubble up.
        """

    @abc.abstractmethod
    def unplug(self, vif):
        """
        Given a model of a VIF, perform operations to unplug the VIF properly.

        :param vif: `os_vif.objects.VIF` object.
        :raises `processutils.ProcessExecutionError`. Plugins implementing
                this method should let `processutils.ProcessExecutionError`
                bubble up.
        """
