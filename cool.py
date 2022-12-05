import argparse
import time
import socket
import struct
import binascii
import pprint
import logging
import matplotlib
import random
import networkx as nx
from copy import copy, deepcopy
from influxdb import InfluxDBClient
from ipaddress import IPv6Address

from src.helper import *

from p4utils.utils.helper import *
from p4utils.utils.sswitch_thrift_API import SimpleSwitchThriftAPI
from p4utils.utils.thrift_API import UIn_Error
from p4utils.utils.helper import load_topo

class NetGraph(object):
    def __init__(self):
        self.G = load_topo('topology.json')
        self.max_bw = 0 #used to normalize link capacity between [0, 1]
        self.delta = 0.001
        self.detour = 1

        #self.conf = load_conf(conf)

        ## Load topology
        # topology = self.conf.get('topology')
        # if topology is None:
        #     raise Exception('no topology defined in {}.'.format(self.conf))

        # # Import topology components
        # unparsed_links = topology.get('links')
        # if unparsed_links is not None:
        #     self.parse_links(unparsed_links)

        self.hosts = [x for x in self.G.nodes if self.G.isHost(x)]
        self.host_prefix = self.hosts[0][0]

        self.switches = [x for x in self.G.nodes if self.G.isP4Switch(x)]
        #print(self.switches)
        self.host_per_s = len(self.G.get_hosts_connected_to(self.switches[0]))

        self.thrift_switches = [None] * len(self.switches)

        for link in list(self.G.edges(data=True)):
            node1 = link[0]
            node2 = link[1]

            if self.G.node_to_node_interface_bw(node1, node2) > self.max_bw:
                self.max_bw = self.G.node_to_node_interface_bw(node1, node2)
            link[2][node1+"weight"] = 0
            link[2][node2+"weight"] = 0
            
        print(self.G.node_to_node_mac("SP6", "LE1"))
        #print(self.select_path("H1", "H4", 1))

        nx.draw(self.G)
        matplotlib.pyplot.show()
            

    def update_infos(self, report):
        start_time = time.time()
        dst = src = 0
        queue_load = 0
        current_path = []
        src_host = get_host_name(ipv6_to_v4(report.flow_id["srcip"]))
        dst_host = get_host_name(ipv6_to_v4(report.flow_id["dstip"]))
        for i, hop in enumerate(report.hop_metadata):
            if i == 0:
                dst = hop.switch_id
                continue
            else:
                queue_load = hop.queue_occupancy
                src = hop.switch_id

            src_node = self.switches[src-1]
            dst_node = self.switches[dst-1]
            current_path.insert(0, dst_node)
            
            if queue_load > 0:
                #self.G.nodes[dst_node]["q_load"] = queue_load
                self.G.edges[src_node, dst_node][dst_node+"weight"] = (queue_load/queue_size) / (self.G.node_to_node_interface_bw(src_node, dst_node) / self.max_bw)

            dst = src

        current_path.insert(0, src_node)
        current_path.insert(0, src_host)
        current_path.append(dst_host)
        print(current_path)

        if report.update_path and report.ethertype == 0x86dd:
            
            p = self.select_path(src_host, dst_host, self.detour)
            if self.weight_path(current_path) < self.weight_path(p)+self.delta:
                return

            res = self.path_to_ips(p)
            self.export_path(res, self.G.get_p4switch_id(p[1]), self.G.get_thrift_port(p[1]))
            print("update_infos : --- %s seconds ---" % (time.time() - start_time))


    def weight_path(self, p):
        src = p[0]
        w = 0
        for n in p[1:]:
            #print("nodes: {} {}".format(src, n))
            w += self.G.edges[src, n][n+"weight"]
            #w += (self.G.nodes[n]["q_load"]/queue_size) / (self.G.edges[src, n]["bw"] / self.max_bw)
            src = n
        return w

    def compare_paths(self, p1, p2):
        return p1 if self.weight_path(p1) < self.weight_path(p2) else p2

    def select_path(self, src, dst, detour):
        #generator = nx.all_shortest_paths(self.G, source=src, target=dst)
        spl = nx.shortest_path_length(self.G, source=src, target=dst)
        generator = nx.all_simple_paths(self.G, source=src, target=dst, cutoff=spl+detour)#generate all paths with a detour of at most "detour" nodes more than the shortest path
        paths = list(generator)
        len_p = len(paths)

        if len_p == 0:
            return None

        if len_p == 1:
            return paths[0]

        ids = random.sample(range(len_p), 2)
        p1 = paths[ids[0]]
        p2 = paths[ids[1]]

        print("p1 = {}  w={}".format(p1, self.weight_path(p1)))
        print("p2 = {}  w={}".format(p2, self.weight_path(p2)))

        return self.compare_paths(p1, p2)

    def path_to_ips(self, p):
        src = p[0]
        ips = []
        for n in p[1:]:
            if self.G.isHost(n):
                ips.append(converttov6(mac_to_v4(self.G.get_host_mac(n))))
            else:
                ips.append(mac_to_ipv6_linklocal(self.G.node_to_node_mac(n, src)))
                src = n
        return ips

    def export_path(self, p, id_s, port):
        #id_s = ipv6_to_id(p[0], self.host_per_s)
        # port = 9090 + id_s - 1
        p = p[1:]

        if not self.thrift_switches[id_s]:
            self.thrift_switches[id_s] = SimpleSwitchThriftAPI(port, "192.168.0.1")

        len_p = len(p)

        # start_time = time.time()
        # try:
        #     self.thrift_switches[id_s].table_delete_match('srv6_transit', [(p[-1]+"/128")])
        # except Exception as e:
        #     pass

        # print("table_delete_match : --- %s seconds ---" % (time.time() - start_time))
        # self.thrift_switches[id_s].table_add('srv6_transit', 'srv6_t_insert_'+str(len_p), [(p[-1]+"/128")], p)

        try:
            self.thrift_switches[id_s].table_modify_match('srv6_transit', 'srv6_t_insert_'+str(len_p), [(p[-1]+"/128")], p)
        except UIn_Error as e:
            self.thrift_switches[id_s].table_add('srv6_transit', 'srv6_t_insert_'+str(len_p), [(p[-1]+"/128")], p)


NetGraph()