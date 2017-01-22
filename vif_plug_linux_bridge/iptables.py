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

# TODO(jaypipes): Replace this entire module with use of the python-iptables
# library: https://github.com/ldx/python-iptables

import inspect
import os
import re

from oslo_concurrency import lockutils
from oslo_concurrency import processutils
from vif_plug_linux_bridge import privsep

import six


# NOTE(vish): Iptables supports chain names of up to 28 characters,  and we
#             add up to 12 characters to binary_name which is used as a prefix,
#             so we limit it to 16 characters.
#             (max_chain_name_length - len('-POSTROUTING') == 16)
def get_binary_name():
    """Grab the name of the binary we're running in."""
    return os.path.basename(inspect.stack()[-1][1])[:16]

binary_name = get_binary_name()


@privsep.vif_plug.entrypoint
def iptables_save():
    return processutils.execute('iptables-save',
                                '-c', attempts=5)


@privsep.vif_plug.entrypoint
def ip6tables_save():
    return processutils.execute('ip6tables-save',
                                '-c', attempts=5)


@privsep.vif_plug.entrypoint
def iptables_restore(input):
    return processutils.execute('iptables-restore',
                                '-c', attempts=5,
                                process_input=input)


@privsep.vif_plug.entrypoint
def ip6tables_restore(input):
    return processutils.execute('ip6tables-restore',
                                '-c', attempts=5,
                                process_input=input)


class IptablesRule(object):
    """An iptables rule.

    You shouldn't need to use this class directly, it's only used by
    IptablesManager.

    """

    def __init__(self, chain, rule, wrap=True, top=False):
        self.chain = chain
        self.rule = rule
        self.wrap = wrap
        self.top = top

    def __eq__(self, other):
        return ((self.chain == other.chain) and
                (self.rule == other.rule) and
                (self.top == other.top) and
                (self.wrap == other.wrap))

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        if self.wrap:
            chain = '%s-%s' % (binary_name, self.chain)
        else:
            chain = self.chain
        # new rules should have a zero [packet: byte] count
        return '[0:0] -A %s %s' % (chain, self.rule)


class IptablesTable(object):
    """An iptables table."""

    def __init__(self):
        self.rules = []
        self.remove_rules = []
        self.chains = set()
        self.unwrapped_chains = set()
        self.remove_chains = set()
        self.dirty = True

    def has_chain(self, name, wrap=True):
        if wrap:
            return name in self.chains
        else:
            return name in self.unwrapped_chains

    def add_chain(self, name, wrap=True):
        """Adds a named chain to the table.

        The chain name is wrapped to be unique for the component creating
        it, so different components of Nova can safely create identically
        named chains without interfering with one another.

        At the moment, its wrapped name is <binary name>-<chain name>,
        so if nova-compute creates a chain named 'OUTPUT', it'll actually
        end up named 'nova-compute-OUTPUT'.

        """
        if wrap:
            self.chains.add(name)
        else:
            self.unwrapped_chains.add(name)
        self.dirty = True

    def remove_chain(self, name, wrap=True):
        """Remove named chain.

        This removal "cascades". All rule in the chain are removed, as are
        all rules in other chains that jump to it.

        If the chain is not found, this is merely logged.

        """
        if wrap:
            chain_set = self.chains
        else:
            chain_set = self.unwrapped_chains

        if name not in chain_set:
            return

        self.dirty = True

        # non-wrapped chains and rules need to be dealt with specially,
        # so we keep a list of them to be iterated over in apply()
        if not wrap:
            self.remove_chains.add(name)
        chain_set.remove(name)
        if not wrap:
            self.remove_rules += [r for r in self.rules if r.chain == name]
        self.rules = [r for r in self.rules if r.chain != name]

        if wrap:
            jump_snippet = '-j %s-%s' % (binary_name, name)
        else:
            jump_snippet = '-j %s' % (name,)

        if not wrap:
            self.remove_rules += [r for r in self.rules
                                  if jump_snippet in r.rule]
        self.rules = [r for r in self.rules if jump_snippet not in r.rule]

    def add_rule(self, chain, rule, wrap=True, top=False):
        """Add a rule to the table.

        This is just like what you'd feed to iptables, just without
        the '-A <chain name>' bit at the start.

        However, if you need to jump to one of your wrapped chains,
        prepend its name with a '$' which will ensure the wrapping
        is applied correctly.

        """
        if wrap and chain not in self.chains:
            raise ValueError(_('Unknown chain: %r') % chain)

        if '$' in rule:
            rule = ' '.join(map(self._wrap_target_chain, rule.split(' ')))

        rule_obj = IptablesRule(chain, rule, wrap, top)
        if rule_obj not in self.rules:
            self.rules.append(IptablesRule(chain, rule, wrap, top))
            self.dirty = True

    def _wrap_target_chain(self, s):
        if s.startswith('$'):
            return '%s-%s' % (binary_name, s[1:])
        return s

    def remove_rule(self, chain, rule, wrap=True, top=False):
        """Remove a rule from a chain.

        Note: The rule must be exactly identical to the one that was added.
        You cannot switch arguments around like you can with the iptables
        CLI tool.

        """
        try:
            self.rules.remove(IptablesRule(chain, rule, wrap, top))
            if not wrap:
                self.remove_rules.append(IptablesRule(chain, rule, wrap, top))
            self.dirty = True
        except ValueError:
            pass

    def remove_rules_regex(self, regex):
        """Remove all rules matching regex."""
        if isinstance(regex, six.string_types):
            regex = re.compile(regex)
        num_rules = len(self.rules)
        self.rules = [r for r in self.rules if not regex.match(str(r))]
        removed = num_rules - len(self.rules)
        if removed > 0:
            self.dirty = True
        return removed

    def empty_chain(self, chain, wrap=True):
        """Remove all rules from a chain."""
        chained_rules = [rule for rule in self.rules
                              if rule.chain == chain and rule.wrap == wrap]
        if chained_rules:
            self.dirty = True
        for rule in chained_rules:
            self.rules.remove(rule)


class IptablesManager(object):
    """Wrapper for iptables.

    See IptablesTable for some usage docs

    A number of chains are set up to begin with.

    First, nova-filter-top. It's added at the top of FORWARD and OUTPUT. Its
    name is not wrapped, so it's shared between the various nova workers. It's
    intended for rules that need to live at the top of the FORWARD and OUTPUT
    chains. It's in both the ipv4 and ipv6 set of tables.

    For ipv4 and ipv6, the built-in INPUT, OUTPUT, and FORWARD filter chains
    are wrapped, meaning that the "real" INPUT chain has a rule that jumps to
    the wrapped INPUT chain, etc. Additionally, there's a wrapped chain named
    "local" which is jumped to from nova-filter-top.

    For ipv4, the built-in PREROUTING, OUTPUT, and POSTROUTING nat chains are
    wrapped in the same was as the built-in filter chains. Additionally,
    there's a snat chain that is applied after the POSTROUTING chain.

    """

    def __init__(self, use_ipv6=False, iptables_top_regex=None,
                 iptables_bottom_regex=None, iptables_drop_action='DROP',
                 forward_bridge_interface=None):
        self.use_ipv6 = use_ipv6
        self.iptables_top_regex = iptables_top_regex
        self.iptables_bottom_regex = iptables_bottom_regex
        self.iptables_drop_action = iptables_drop_action
        self.forward_bridge_interface = forward_bridge_interface or ['all']
        self.ipv4 = {'filter': IptablesTable(),
                     'nat': IptablesTable(),
                     'mangle': IptablesTable()}
        self.ipv6 = {'filter': IptablesTable()}

        self.iptables_apply_deferred = False

        # Add a nova-filter-top chain. It's intended to be shared
        # among the various nova components. It sits at the very top
        # of FORWARD and OUTPUT.
        for tables in [self.ipv4, self.ipv6]:
            tables['filter'].add_chain('nova-filter-top', wrap=False)
            tables['filter'].add_rule('FORWARD', '-j nova-filter-top',
                                      wrap=False, top=True)
            tables['filter'].add_rule('OUTPUT', '-j nova-filter-top',
                                      wrap=False, top=True)

            tables['filter'].add_chain('local')
            tables['filter'].add_rule('nova-filter-top', '-j $local',
                                      wrap=False)

        # Wrap the built-in chains
        builtin_chains = {4: {'filter': ['INPUT', 'OUTPUT', 'FORWARD'],
                              'nat': ['PREROUTING', 'OUTPUT', 'POSTROUTING'],
                              'mangle': ['POSTROUTING']},
                          6: {'filter': ['INPUT', 'OUTPUT', 'FORWARD']}}

        for ip_version in builtin_chains:
            if ip_version == 4:
                tables = self.ipv4
            elif ip_version == 6:
                tables = self.ipv6

            for table, chains in six.iteritems(builtin_chains[ip_version]):
                for chain in chains:
                    tables[table].add_chain(chain)
                    tables[table].add_rule(chain, '-j $%s' % (chain,),
                                           wrap=False)

        # Add a nova-postrouting-bottom chain. It's intended to be shared
        # among the various nova components. We set it as the last chain
        # of POSTROUTING chain.
        self.ipv4['nat'].add_chain('nova-postrouting-bottom', wrap=False)
        self.ipv4['nat'].add_rule('POSTROUTING', '-j nova-postrouting-bottom',
                                  wrap=False)

        # We add a snat chain to the shared nova-postrouting-bottom chain
        # so that it's applied last.
        self.ipv4['nat'].add_chain('snat')
        self.ipv4['nat'].add_rule('nova-postrouting-bottom', '-j $snat',
                                  wrap=False)

        # And then we add a float-snat chain and jump to first thing in
        # the snat chain.
        self.ipv4['nat'].add_chain('float-snat')
        self.ipv4['nat'].add_rule('snat', '-j $float-snat')

    def defer_apply_on(self):
        self.iptables_apply_deferred = True

    def defer_apply_off(self):
        self.iptables_apply_deferred = False
        self.apply()

    def dirty(self):
        for table in six.itervalues(self.ipv4):
            if table.dirty:
                return True
        if self.use_ipv6:
            for table in six.itervalues(self.ipv6):
                if table.dirty:
                    return True
        return False

    def apply(self):
        if self.iptables_apply_deferred:
            return
        if self.dirty():
            self._apply()

    @lockutils.synchronized('nova-iptables', external=True)
    def _apply(self):
        """Apply the current in-memory set of iptables rules.

        This will blow away any rules left over from previous runs of the
        same component of Nova, and replace them with our current set of
        rules. This happens atomically, thanks to iptables-restore.

        """
        s = [(iptables_save, iptables_restore, self.ipv4)]
        if self.use_ipv6:
            s += [(ip6tables_save, ip6tables_restore, self.ipv6)]

        for save, restore, tables in s:
            all_tables, _err = save()
            all_lines = all_tables.split('\n')
            for table_name, table in six.iteritems(tables):
                start, end = self._find_table(all_lines, table_name)
                all_lines[start:end] = self._modify_rules(
                        all_lines[start:end], table, table_name)
                table.dirty = False
            restore('\n'.join(all_lines))

    def _find_table(self, lines, table_name):
        if len(lines) < 3:
            # length only <2 when fake iptables
            return (0, 0)
        try:
            start = lines.index('*%s' % table_name) - 1
        except ValueError:
            # Couldn't find table_name
            return (0, 0)
        end = lines[start:].index('COMMIT') + start + 2
        return (start, end)

    def _modify_rules(self, current_lines, table, table_name):
        unwrapped_chains = table.unwrapped_chains
        chains = sorted(table.chains)
        remove_chains = table.remove_chains
        rules = table.rules
        remove_rules = table.remove_rules

        if not current_lines:
            fake_table = ['#Generated by nova',
                          '*' + table_name, 'COMMIT',
                          '#Completed by nova']
            current_lines = fake_table

        # Remove any trace of our rules
        new_filter = [line for line in current_lines
                      if binary_name not in line]

        top_rules = []
        bottom_rules = []

        if self.iptables_top_regex:
            regex = re.compile(self.iptables_top_regex)
            temp_filter = [line for line in new_filter if regex.search(line)]
            for rule_str in temp_filter:
                new_filter = [s for s in new_filter
                              if s.strip() != rule_str.strip()]
            top_rules = temp_filter

        if self.iptables_bottom_regex:
            regex = re.compile(self.iptables_bottom_regex)
            temp_filter = [line for line in new_filter if regex.search(line)]
            for rule_str in temp_filter:
                new_filter = [s for s in new_filter
                              if s.strip() != rule_str.strip()]
            bottom_rules = temp_filter

        seen_chains = False
        rules_index = 0
        for rules_index, rule in enumerate(new_filter):
            if not seen_chains:
                if rule.startswith(':'):
                    seen_chains = True
            else:
                if not rule.startswith(':'):
                    break

        if not seen_chains:
            rules_index = 2

        our_rules = top_rules
        bot_rules = []
        for rule in rules:
            rule_str = str(rule)
            if rule.top:
                # rule.top == True means we want this rule to be at the top.
                # Further down, we weed out duplicates from the bottom of the
                # list, so here we remove the dupes ahead of time.

                # We don't want to remove an entry if it has non-zero
                # [packet:byte] counts and replace it with [0:0], so let's
                # go look for a duplicate, and over-ride our table rule if
                # found.

                # ignore [packet:byte] counts at beginning of line
                if rule_str.startswith('['):
                    rule_str = rule_str.split(']', 1)[1]
                dup_filter = [s for s in new_filter
                              if rule_str.strip() in s.strip()]

                new_filter = [s for s in new_filter
                              if rule_str.strip() not in s.strip()]
                # if no duplicates, use original rule
                if dup_filter:
                    # grab the last entry, if there is one
                    dup = list(dup_filter)[-1]
                    rule_str = str(dup)
                else:
                    rule_str = str(rule)
                rule_str.strip()

                our_rules += [rule_str]
            else:
                bot_rules += [rule_str]

        our_rules += bot_rules

        new_filter = list(new_filter)
        new_filter[rules_index:rules_index] = our_rules

        new_filter[rules_index:rules_index] = [':%s - [0:0]' % (name,)
                                               for name in unwrapped_chains]
        new_filter[rules_index:rules_index] = [':%s-%s - [0:0]' %
                                               (binary_name, name,)
                                               for name in chains]

        commit_index = new_filter.index('COMMIT')
        new_filter[commit_index:commit_index] = bottom_rules
        seen_lines = set()

        def _weed_out_duplicates(line):
            # ignore [packet:byte] counts at beginning of lines
            if line.startswith('['):
                line = line.split(']', 1)[1]
            line = line.strip()
            if line in seen_lines:
                return False
            else:
                seen_lines.add(line)
                return True

        def _weed_out_removes(line):
            # We need to find exact matches here
            if line.startswith(':'):
                # it's a chain, for example, ":nova-billing - [0:0]"
                # strip off everything except the chain name
                line = line.split(':')[1]
                line = line.split('- [')[0]
                line = line.strip()
                for chain in remove_chains:
                    if chain == line:
                        remove_chains.remove(chain)
                        return False
            elif line.startswith('['):
                # it's a rule
                # ignore [packet:byte] counts at beginning of lines
                line = line.split(']', 1)[1]
                line = line.strip()
                for rule in remove_rules:
                    # ignore [packet:byte] counts at beginning of rules
                    rule_str = str(rule)
                    rule_str = rule_str.split(' ', 1)[1]
                    rule_str = rule_str.strip()
                    if rule_str == line:
                        remove_rules.remove(rule)
                        return False

            # Leave it alone
            return True

        # We filter duplicates, letting the *last* occurrence take
        # precedence.  We also filter out anything in the "remove"
        # lists.
        new_filter = list(new_filter)
        new_filter.reverse()
        new_filter = filter(_weed_out_duplicates, new_filter)
        new_filter = filter(_weed_out_removes, new_filter)
        new_filter = list(new_filter)
        new_filter.reverse()

        # flush lists, just in case we didn't find something
        remove_chains.clear()
        for rule in remove_rules:
            remove_rules.remove(rule)

        return new_filter

    def get_gateway_rules(self, bridge):
        interfaces = self.forward_bridge_interface
        if 'all' in interfaces:
            return [('FORWARD', '-i %s -j ACCEPT' % bridge),
                    ('FORWARD', '-o %s -j ACCEPT' % bridge)]
        rules = []
        for iface in self.forward_bridge_interface:
            if iface:
                rules.append(('FORWARD', '-i %s -o %s -j ACCEPT' % (bridge,
                                                                    iface)))
                rules.append(('FORWARD', '-i %s -o %s -j ACCEPT' % (iface,
                                                                    bridge)))
        rules.append(('FORWARD', '-i %s -o %s -j ACCEPT' % (bridge, bridge)))
        rules.append(('FORWARD', '-i %s -j %s' % (bridge,
                                                  self.iptables_drop_action)))
        rules.append(('FORWARD', '-o %s -j %s' % (bridge,
                                                  self.iptables_drop_action)))
        return rules
