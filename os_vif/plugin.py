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
from oslo_config import cfg


CONF = cfg.CONF


class PluginBase(metaclass=abc.ABCMeta):
    """Base class for all VIF plugins."""

    # Override to provide a tuple of oslo_config.Opt instances for
    # the plugin config parameters
    CONFIG_OPTS = ()

    def __init__(self, config):
        """
        Initialize the plugin object with the provided config

        :param config: ``oslo_config.ConfigOpts.GroupAttr`` instance:
        """
        self.config = config

    @abc.abstractmethod
    def describe(self):
        """
        Return an object that describes the plugin's supported vif types and
        the earliest/latest known VIF object versions.

        :returns: A ``os_vif.objects.host_info.HostPluginInfo`` instance
        """

    @abc.abstractmethod
    def plug(self, vif, instance_info):
        """
        Given a model of a VIF, perform operations to plug the VIF properly.

        :param vif: ``os_vif.objects.vif.VIFBase`` object.
        :param instance_info: ``os_vif.objects.instance_info.InstanceInfo``
            object.
        :raises ``processutils.ProcessExecutionError``. Plugins implementing
                this method should let `processutils.ProcessExecutionError`
                bubble up.
        """

    @abc.abstractmethod
    def unplug(self, vif, instance_info):
        """
        Given a model of a VIF, perform operations to unplug the VIF properly.

        :param vif: ``os_vif.objects.vif.VIFBase`` object.
        :param instance_info: ``os_vif.objects.instance_info.InstanceInfo``
            object.
        :raises ``processutils.ProcessExecutionError``. Plugins implementing
                this method should let ``processutils.ProcessExecutionError``
                bubble up.
        """

    @classmethod
    def load(cls, plugin_name):
        """
        Load a plugin, registering its configuration options

        :param plugin_name: the name of the plugin extension

        :returns: an initialized instance of the class
        """
        cfg_group_name = "os_vif_" + plugin_name
        cfg_opts = getattr(cls, "CONFIG_OPTS")
        cfg_vals = None
        if cfg_opts and len(cfg_opts) > 0:
            cfg_group = cfg.OptGroup(
                cfg_group_name,
                "os-vif plugin %s options" % plugin_name)
            CONF.register_opts(cfg_opts, group=cfg_group)

            cfg_vals = getattr(CONF, cfg_group_name)
        return cls(cfg_vals)
