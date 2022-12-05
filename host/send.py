#!/usr/bin/python

# Copyright 2013-present Barefoot Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from scapy.all import Ether, IP, sendp, get_if_hwaddr, get_if_list, TCP, Raw, UDP
import sys
import random, string
import time
from p4utils.utils.helper import *

def randomword(max_length):
    length = random.randint(1, max_length)
    return ''.join(random.choice(string.ascii_lowercase) for i in range(length))

def read_topo():
    nb_hosts = 0
    nb_switches = 0
    links = []
    with open("topo.txt", "r") as f:
        line = f.readline()[:-1]
        w, nb_switches = line.split()
        assert(w == "switches")
        line = f.readline()[:-1]
        w, nb_hosts = line.split()
        assert(w == "hosts")
        for line in f:
            if not f: break
            a, b = line.split()
            links.append( (a, b) )
    return int(nb_hosts), int(nb_switches), links

def mac_to_v4(mac):
    mac_value = int(mac.translate({ord(' '): None, ord('.'): None, ord(':'): None, ord('-'): None}), 16)

    #port = mac_value >> 32 & 0xff
    high1 = mac_value >> 24 & 0xff
    high2 = mac_value >> 16 & 0xff
    low1 = mac_value >> 8 & 0xff
    low2 = mac_value & 0xff

    return '{}.{}.{}.{}'.format(high1, high2, low1, low2)

def ip_from_topo(n_id):
    conf = load_conf("topology.json")
    nodes = conf.get("nodes")
    for x in nodes:
        if x.get("id") == n_id:
            return x.get("ip").split('/')[0]

def send_random_traffic(dst):
    dst_mac = None
    dst_ip = None
    src_inf = [i for i in get_if_list() if i.endswith('-eth0')]
    if len(src_inf) < 1:
        print ("No interface for output")
        sys.exit(1)
    src_mac = get_if_hwaddr(src_inf[0])

    src_ip = mac_to_v4(src_mac)

    dst_ip = ip_from_topo(dst)
    if dst_ip == None:
        print ("Invalid host to send to")
        sys.exit(1)
    dst_mac = ip_address_to_mac(dst_ip) % (0)

    total_pkts = 0
    random_ports = random.sample(range(1024, 65535), 1)
    for port in random_ports:
        # num_packets = random.randint(50, 250)
        num_packets = 1000
        for i in range(num_packets):
            # data = randomword(100)
            data = randomword(1)
            p = Ether(dst=dst_mac,src=src_mac)/IP(dst=dst_ip,src=src_ip)
            p = p/UDP(dport=port)/Raw(load=data)
            # p = p/TCP(dport=port)/Raw(load=data)
            print (p.show())
            sendp(p, iface = src_inf[0])
            total_pkts += 1
            time.sleep(0.1)
    print ("Sent %s packets in total" % total_pkts)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python send.py dst_host_name")
        sys.exit(1)
    else:
        dst_name = sys.argv[1]
        send_random_traffic(dst_name)
