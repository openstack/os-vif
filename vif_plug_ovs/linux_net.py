# Derived from nova/network/linux_net.py
#
# Copyright (c) 2011 X.commerce, a business unit of eBay Inc.
# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
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

"""Implements vlans, bridges using linux utilities."""

import os

from oslo_concurrency import processutils
from oslo_log import log as logging
from oslo_utils import excutils

from vif_plug_ovs import constants
from vif_plug_ovs import exception
from vif_plug_ovs.i18n import _LE
from vif_plug_ovs import privsep

LOG = logging.getLogger(__name__)


def _ovs_vsctl(args, timeout=None):
    full_args = ['ovs-vsctl']
    if timeout is not None:
        full_args += ['--timeout=%s' % timeout]
    full_args += args
    try:
        return processutils.execute(*full_args)
    except Exception as e:
        LOG.error(_LE("Unable to execute %(cmd)s. Exception: %(exception)s"),
                  {'cmd': full_args, 'exception': e})
        raise exception.AgentError(method=full_args)


def _create_ovs_vif_cmd(bridge, dev, iface_id, mac,
                        instance_id, interface_type=None,
                        vhost_server_path=None):
    cmd = ['--', '--if-exists', 'del-port', dev, '--',
            'add-port', bridge, dev,
            '--', 'set', 'Interface', dev,
            'external-ids:iface-id=%s' % iface_id,
            'external-ids:iface-status=active',
            'external-ids:attached-mac=%s' % mac,
            'external-ids:vm-uuid=%s' % instance_id]
    if interface_type:
        cmd += ['type=%s' % interface_type]
    if vhost_server_path:
        cmd += ['options:vhost-server-path=%s' % vhost_server_path]
    return cmd


def _create_ovs_bridge_cmd(bridge, datapath_type):
    return ['--', '--may-exist', 'add-br', bridge,
            '--', 'set', 'Bridge', bridge, 'datapath_type=%s' % datapath_type]


@privsep.vif_plug.entrypoint
def create_ovs_vif_port(bridge, dev, iface_id, mac, instance_id,
                        mtu=None, interface_type=None, timeout=None,
                        vhost_server_path=None):
    _ovs_vsctl(_create_ovs_vif_cmd(bridge, dev, iface_id,
                                   mac, instance_id, interface_type,
                                   vhost_server_path), timeout=timeout)
    _update_device_mtu(dev, mtu, interface_type, timeout=timeout)


@privsep.vif_plug.entrypoint
def update_ovs_vif_port(dev, mtu=None, interface_type=None, timeout=None):
    _update_device_mtu(dev, mtu, interface_type, timeout=timeout)


@privsep.vif_plug.entrypoint
def delete_ovs_vif_port(bridge, dev, timeout=None):
    _ovs_vsctl(['--', '--if-exists', 'del-port', bridge, dev],
               timeout=timeout)
    _delete_net_dev(dev)


def device_exists(device):
    """Check if ethernet device exists."""
    return os.path.exists('/sys/class/net/%s' % device)


def _delete_net_dev(dev):
    """Delete a network device only if it exists."""
    if device_exists(dev):
        try:
            processutils.execute('ip', 'link', 'delete', dev,
                                 check_exit_code=[0, 2, 254])
            LOG.debug("Net device removed: '%s'", dev)
        except processutils.ProcessExecutionError:
            with excutils.save_and_reraise_exception():
                LOG.error(_LE("Failed removing net device: '%s'"), dev)


@privsep.vif_plug.entrypoint
def create_veth_pair(dev1_name, dev2_name, mtu):
    """Create a pair of veth devices with the specified names,
    deleting any previous devices with those names.
    """
    for dev in [dev1_name, dev2_name]:
        _delete_net_dev(dev)

    processutils.execute('ip', 'link', 'add', dev1_name,
                         'type', 'veth', 'peer', 'name', dev2_name)
    for dev in [dev1_name, dev2_name]:
        processutils.execute('ip', 'link', 'set', dev, 'up')
        processutils.execute('ip', 'link', 'set', dev, 'promisc', 'on')
        _update_device_mtu(dev, mtu)


@privsep.vif_plug.entrypoint
def update_veth_pair(dev1_name, dev2_name, mtu):
    """Update a pair of veth devices with new configuration."""
    for dev in [dev1_name, dev2_name]:
        _update_device_mtu(dev, mtu)


@privsep.vif_plug.entrypoint
def ensure_ovs_bridge(bridge, datapath_type):
    _ovs_vsctl(_create_ovs_bridge_cmd(bridge, datapath_type))


@privsep.vif_plug.entrypoint
def ensure_bridge(bridge):
    if not device_exists(bridge):
        processutils.execute('brctl', 'addbr', bridge)
        processutils.execute('brctl', 'setfd', bridge, 0)
        processutils.execute('brctl', 'stp', bridge, 'off')
        syspath = '/sys/class/net/%s/bridge/multicast_snooping'
        syspath = syspath % bridge
        processutils.execute('tee', syspath, process_input='0',
                             check_exit_code=[0, 1])
        disv6 = ('/proc/sys/net/ipv6/conf/%s/disable_ipv6' %
                 bridge)
        if os.path.exists(disv6):
            processutils.execute('tee',
                                 disv6,
                                 process_input='1',
                                 check_exit_code=[0, 1])


@privsep.vif_plug.entrypoint
def delete_bridge(bridge, dev):
    if device_exists(bridge):
        processutils.execute('brctl', 'delif', bridge, dev)
        processutils.execute('ip', 'link', 'set', bridge, 'down')
        processutils.execute('brctl', 'delbr', bridge)


@privsep.vif_plug.entrypoint
def add_bridge_port(bridge, dev):
    processutils.execute('ip', 'link', 'set', bridge, 'up')
    processutils.execute('brctl', 'addif', bridge, dev)


def _update_device_mtu(dev, mtu, interface_type=None, timeout=120):
    if not mtu:
        return
    if interface_type not in [
        constants.OVS_VHOSTUSER_INTERFACE_TYPE,
        constants.OVS_VHOSTUSER_CLIENT_INTERFACE_TYPE]:
        _set_device_mtu(dev, mtu)
    elif _ovs_supports_mtu_requests(timeout=timeout):
        _set_mtu_request(dev, mtu, timeout=timeout)
    else:
        LOG.debug("MTU not set on %(interface_name)s interface "
                  "of type %(interface_type)s.",
                  {'interface_name': dev,
                   'interface_type': interface_type})


@privsep.vif_plug.entrypoint
def _set_device_mtu(dev, mtu):
    """Set the device MTU."""
    processutils.execute('ip', 'link', 'set', dev, 'mtu', mtu,
                         check_exit_code=[0, 2, 254])


@privsep.vif_plug.entrypoint
def _set_mtu_request(dev, mtu, timeout=None):
    args = ['--', 'set', 'interface', dev,
            'mtu_request=%s' % mtu]
    _ovs_vsctl(args, timeout=timeout)


@privsep.vif_plug.entrypoint
def _ovs_supports_mtu_requests(timeout=None):
    args = ['--columns=mtu_request', 'list', 'interface']
    _, error = _ovs_vsctl(args, timeout=timeout)
    if (error == 'ovs-vsctl: Interface does not contain' +
              ' a column whose name matches "mtu_request"'):
            return False
    return True
