# Copyright (C) 2019-2020 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import unittest

from vyos.configsession import ConfigSession
from netifaces import ifaddresses, AF_INET, AF_INET6
from vyos.validate import is_intf_addr_assigned, is_ipv6_link_local
from vyos.ifconfig import Interface

class BasicInterfaceTest:
    class BaseTest(unittest.TestCase):
        _test_mtu = False
        _base_path = []
        _options = {}
        _interfaces = []

        def setUp(self):
            self.session = ConfigSession(os.getpid())

            self._test_addr = ['192.0.2.1/26', '192.0.2.255/31', '192.0.2.64/32',
                                '2001:db8:1::ffff/64', '2001:db8:101::1/112']
            self._test_mtu = False
            self._options = {}

        def tearDown(self):
            # we should not remove ethernet from the overall CLI
            if 'ethernet' in self._base_path:
                for intf in self._interfaces:
                    # when using a dedicated interface to test via TEST_ETH environment
                    # variable only this one will be cleared in the end - usable to test
                    # ethernet interfaces via SSH
                    self.session.delete(self._base_path + [intf])
                    self.session.set(self._base_path + [intf])
            else:
                self.session.delete(self._base_path)

            self.session.commit()
            del self.session

        def test_add_description(self):
            """
            Check if description can be added to interface
            """
            for intf in self._interfaces:
                test_string='Description-Test-{}'.format(intf)
                self.session.set(self._base_path + [intf, 'description', test_string])
                for option in self._options.get(intf, []):
                    self.session.set(self._base_path + [intf] + option.split())

            self.session.commit()

            # Validate interface description
            for intf in self._interfaces:
                test_string='Description-Test-{}'.format(intf)
                with open('/sys/class/net/{}/ifalias'.format(intf), 'r') as f:
                    tmp = f.read().rstrip()
                    self.assertTrue(tmp, test_string)

        def test_add_address_single(self):
            """
            Check if a single address can be added to interface.
            """
            addr = '192.0.2.0/31'
            for intf in self._interfaces:
                self.session.set(self._base_path + [intf, 'address', addr])
                for option in self._options.get(intf, []):
                    self.session.set(self._base_path + [intf] + option.split())

            self.session.commit()

            for intf in self._interfaces:
                self.assertTrue(is_intf_addr_assigned(intf, addr))

        def test_add_address_multi(self):
            """
            Check if IPv4/IPv6 addresses can be added to interface.
            """

            # Add address
            for intf in self._interfaces:
                for addr in self._test_addr:
                    self.session.set(self._base_path + [intf, 'address', addr])
                    for option in self._options.get(intf, []):
                        self.session.set(self._base_path + [intf] + option.split())

            self.session.commit()

            # Validate address
            for intf in self._interfaces:
                for af in AF_INET, AF_INET6:
                    for addr in ifaddresses(intf)[af]:
                        # checking link local addresses makes no sense
                        if is_ipv6_link_local(addr['addr']):
                            continue

                        self.assertTrue(is_intf_addr_assigned(intf, addr['addr']))


        def test_change_mtu(self):
            """
            Check if MTU can be changed on interface.
            Test MTU size will be 1400 bytes.
            """
            if not self._test_mtu:
                return None

            # choose MTU which works on every interface - 1280 is minimum for IPv6 so
            # it will always work.
            mtu = '1280'
            for intf in self._interfaces:
                self.session.set(self._base_path + [intf, 'mtu', mtu])
                for option in self._options.get(intf, []):
                    self.session.set(self._base_path + [intf] + option.split())

            self.session.commit()

            # Validate interface description
            for intf in self._interfaces:
                with open('/sys/class/net/{}/mtu'.format(intf), 'r') as f:
                    tmp = f.read().rstrip()
                    self.assertEqual(tmp, mtu)


        def test_8021q_vlan(self):
            if not self._test_vlan:
                return None

            vlan_range = ['100', '200', '300', '2000']
            for intf in self._interfaces:
                for vlan in vlan_range:
                    address = '192.0.2.1/24'
                    # choose MTU which works on every interface - 1280 is minimum for IPv6 so
                    # it will always work.
                    mtu = '1280'

                    base = self._base_path + [intf, 'vif', vlan]
                    self.session.set(base + ['address', address])
                    self.session.set(base + ['mtu', mtu])

            self.session.commit()

            # Validate interface description
            for intf in self._interfaces:
                for vlan in vlan_range:
                    vif = f'{intf}.{vlan}'
                    with open(f'/sys/class/net/{vif}/mtu', 'r') as f:
                        tmp = f.read().rstrip()
                        self.assertEqual(tmp, mtu)

                    self.assertTrue(is_intf_addr_assigned(vif, address))
