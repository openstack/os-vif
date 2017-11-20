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

from oslo_utils import versionutils
from oslo_versionedobjects import base
from oslo_versionedobjects import fields

from os_vif import exception
from os_vif.objects import base as osv_base


def _get_common_version(object_name, max_version, min_version, exc_notmatch,
                        exc_notsupported):
    """Returns the accepted version from the loaded OVO registry"""
    reg = base.VersionedObjectRegistry.obj_classes()

    if object_name not in reg:
        raise exc_notmatch(name=object_name)

    gotvers = []
    for regobj in reg[object_name]:
        gotvers.append(regobj.VERSION)
        got = versionutils.convert_version_to_tuple(regobj.VERSION)
        minwant = versionutils.convert_version_to_tuple(min_version)
        maxwant = versionutils.convert_version_to_tuple(max_version)

        if minwant <= got <= maxwant:
            return regobj.VERSION

    raise exc_notsupported(name=object_name,
                           got_versions=",".join(gotvers),
                           min_version=min_version,
                           max_version=max_version)


@base.VersionedObjectRegistry.register
class HostPortProfileInfo(osv_base.VersionedObject,
                          base.ComparableVersionedObject,
                          osv_base.VersionedObjectPrintableMixin):
    """
    Class describing a PortProfile class and its supported versions
    """
    # Version 1.0: Initial version
    VERSION = "1.0"

    fields = {
        # object name of the subclass of os_vif.objects.vif.VIFPortProfileBase
        "profile_object_name": fields.StringField(),

        # String representing the earliest version of @name
        # that the plugin understands
        "min_version": fields.StringField(),

        # String representing the latest version of @name
        # that the plugin understands
        "max_version": fields.StringField(),
    }

    def get_common_version(self):
        return _get_common_version(self.profile_object_name,
                                   self.max_version,
                                   self.min_version,
                                   exception.NoMatchingPortProfileClass,
                                   exception.NoSupportedPortProfileVersion)


@base.VersionedObjectRegistry.register
class HostVIFInfo(osv_base.VersionedObject, base.ComparableVersionedObject,
                  osv_base.VersionedObjectPrintableMixin):
    """
    Class describing a VIF class and its supported versions
    """
    # Version 1.0: Initial version
    # Version 1.1: Adds 'supported_port_profiles' field
    VERSION = "1.1"

    fields = {
        # object name of the subclass of os_vif.objects.vif.VIFBase
        "vif_object_name": fields.StringField(),

        # String representing the earliest version of @name
        # that the plugin understands
        "min_version": fields.StringField(),

        # String representing the latest version of @name
        # that the plugin understands
        "max_version": fields.StringField(),

        # list of supported PortProfile objects and versions.
        "supported_port_profiles": fields.ListOfObjectsField(
            "HostPortProfileInfo")
    }

    def obj_make_compatible(self, primitive, target_version):
        super(HostVIFInfo, self).obj_make_compatible(primitive,
                                                      target_version)
        target_version = versionutils.convert_version_to_tuple(target_version)
        if target_version < (1, 1) and 'supported_port_profiles' in primitive:
            del primitive['supported_port_profiles']

    def get_common_version(self):
        return _get_common_version(self.vif_object_name,
                                   self.max_version,
                                   self.min_version,
                                   exception.NoMatchingVIFClass,
                                   exception.NoSupportedVIFVersion)


@base.VersionedObjectRegistry.register
class HostPluginInfo(osv_base.VersionedObject, base.ComparableVersionedObject,
                     osv_base.VersionedObjectPrintableMixin):
    """
    Class describing a plugin and its supported VIF classes
    """
    # Version 1.0: Initial version
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
class HostInfo(osv_base.VersionedObject, base.ComparableVersionedObject,
               osv_base.VersionedObjectPrintableMixin):
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
