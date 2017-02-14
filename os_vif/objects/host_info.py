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

from oslo_versionedobjects import base
from oslo_versionedobjects import fields

from os_vif import exception
from os_vif.objects import base as osv_base


@base.VersionedObjectRegistry.register
class HostVIFInfo(osv_base.VersionedObject, base.ComparableVersionedObject):
    """
    Class describing a VIF class and its supported versions
    """

    VERSION = "1.0"

    fields = {
        # object name of the subclass of os_vif.objects.vif.VIFBase
        "vif_object_name": fields.StringField(),

        # String representing the earliest version of @name
        # that the plugin understands
        "min_version": fields.StringField(),

        # String representing the latest version of @name
        # that the plugin understands
        "max_version": fields.StringField(),
    }

    def get_common_version(self):
        def _vers_tuple(ver):
            return tuple([int(x) for x in ver.split(".")])

        reg = base.VersionedObjectRegistry.obj_classes()

        if self.vif_object_name not in reg:
            raise exception.NoMatchingVIFClass(vif_name=self.vif_object_name)

        gotvers = []
        for regobj in reg[self.vif_object_name]:
            gotvers.append(regobj.VERSION)
            got = _vers_tuple(regobj.VERSION)
            minwant = _vers_tuple(self.min_version)
            maxwant = _vers_tuple(self.max_version)

            if minwant <= got <= maxwant:
                return regobj.VERSION

        raise exception.NoSupportedVIFVersion(vif_name=self.vif_object_name,
                                              got_versions=",".join(gotvers),
                                              min_version=self.min_version,
                                              max_version=self.max_version)


@base.VersionedObjectRegistry.register
class HostPluginInfo(osv_base.VersionedObject,
                        base.ComparableVersionedObject):
    """
    Class describing a plugin and its supported VIF classes
    """

    VERSION = "1.0"

    fields = {
        # name of the plugin
        "plugin_name": fields.StringField(),

        # list of HostVIFInfo instances supported by the plugin
        "vif_info": fields.ListOfObjectsField("HostVIFInfo"),
    }

    def has_vif(self, name):
        for vif in self.vif_info:
            if vif.vif_object_name == name:
                return True
        return False

    def get_vif(self, name):
        for vif in self.vif_info:
            if vif.vif_object_name == name:
                return vif

        raise exception.NoMatchingVIFClass(vif_name=name)

    def filter_vif_types(self, permitted_vif_type_names):
        new_vif_info = []
        for vif in self.vif_info:
            if vif.vif_object_name in permitted_vif_type_names:
                new_vif_info.append(vif)
        self.vif_info = new_vif_info


@base.VersionedObjectRegistry.register
class HostInfo(osv_base.VersionedObject, base.ComparableVersionedObject):
    """
    Class describing a host host and its supported plugin classes
    """

    fields = {
        # list of HostPluginInfo instances supported by the host host
        "plugin_info": fields.ListOfObjectsField("HostPluginInfo"),
    }

    def has_plugin(self, name):
        for plugin in self.plugin_info:
            if name == plugin.plugin_name:
                return True
        return False

    def get_plugin(self, name):
        for plugin in self.plugin_info:
            if name == plugin.plugin_name:
                return plugin

        raise exception.NoMatchingPlugin(plugin_name=name)

    def filter_vif_types(self, permitted_vif_type_names):
        new_plugins = []
        for plugin in self.plugin_info:
            plugin.filter_vif_types(permitted_vif_type_names)
            if len(plugin.vif_info) == 0:
                continue
            new_plugins.append(plugin)
        self.plugin_info = new_plugins
