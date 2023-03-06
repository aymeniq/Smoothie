import sys
import numpy as np
import networkx as nx
import matplotlib
from p4utils.utils.helper import ip_address_to_mac

import sys
sys.path.append('../src')
from helper import *

def id_to_mac(SP_id, L_id, is_SP):
    #"{:02x}".format(12)
    if is_SP:
        return '00:{:02x}:0a:00:{:02x}:{:02x}'.format(2, SP_id, L_id)
    else:
        return '00:{:02x}:0a:00:{:02x}:{:02x}'.format(1, SP_id, L_id)

class File_generator():
    """docstring for File_generator"""
    def __init__(self, file, G, switches, links, nb_leaf, hosts_per_leaf=1):
        self.file = file
        self.G = G
        self.switches = switches
        self.links = links
        self.nb_leaf = nb_leaf
        self.hosts_per_leaf = hosts_per_leaf
        self.hosts = []

    def get_mac(self, src, dst):
        return self.links(src+dst)

    def generate_command(self, s, idx, nbr_h, proportion, timeout):
        output = "set_queue_depth 64\n"

        l = len(self.G.edges(idx))
        if s.startswith("SP"):
            is_spine = True
        else: 
            is_spine = False

        if not is_spine: l+=nbr_h

        if not is_spine:
            for x in range(1, nbr_h+1):
                output+= "table_add tb_activate_flow_dest set_timeout {} => {}\n".format(x, timeout)
                output+= "table_add tb_activate_source activate_source {} => {}\n".format(x, proportion)
                output+= "table_add host_port NoAction {} =>\n".format(x)

            output += "table_add tb_intv6_source configure_source 2002::a00:101&&&0xFFFFFFFFFFFFFFFFFFFFFFFFFFFF0000 2002::a00:202&&&0xFFFFFFFFFFFFFFFFFFFFFFFFFFFF0000 0x11FF&&&0x0000 0x22FF&&&0x0000 => 4 10 8 0xFF00 0\n"

            output += "mirroring_add 1 {}\n".format(l+1)
            for x in range(1, nbr_h+1):
                output += "table_add tb_int_sink configure_sink {} => {}\n".format(x, l+1)

            output += "table_add tb_int_reporting send_report => 00:00:0a:00:01:01  10.0.1.1  f6:61:c0:6a:14:21  10.0.0.254  6000\n"

        output += "table_add tb_int_transit configure_transit => {} 1500\n".format(idx+1)

        nbr_uplink=0
        cnt=0

        for i, x in enumerate(self.G.edges(idx)):
            if is_spine:
                mac = id_to_mac(idx+1, x[1]+1, not is_spine)
            else:
                mac = id_to_mac(x[1]+1, idx+1, not is_spine)
            ip = mac_to_ipv6_linklocal(mac)

            if is_spine:
                output += "table_add ipv6_lpm ipv6_forward {}/128 => {} {}\n".format(ip, mac, i+1)
                output += "table_add ipv4_lpm ipv4_forward 10.0.{}.0/24 => {} {}\n".format(i+1, mac, i+1)
                output += "table_add ipv6_lpm ipv6_forward 2002::a00:{}00/120 => {} {}\n".format(i+1, mac, i+1)
            else:
                output += "table_add ipv6_lpm ipv6_forward {}/128 => {} {}\n".format(ip, mac, i+nbr_h+1)
                output += "table_add ecmp_group_to_nhop ipv6_forward 1 {} =>  {} {}\n".format(cnt, mac, i+nbr_h+1)
                nbr_uplink+=1
                cnt+=1

        if not is_spine:
            output += "table_add ipv6_lpm ecmp_group 2002::/96 => 1 {}\n".format(nbr_uplink)
            output += "table_add ipv4_lpm ipv4_forward 10.0.0.0/8 => 00:00:00:00:00:00 {}\n".format(self.hosts_per_leaf+1) #forward to the first spine   
            for x in range(1, self.hosts_per_leaf+1):
                ip = "10.0.{}.{}".format(idx+1, x)
                output += "table_add ipv6_lpm ipv6_forward {}/128 => {} {}\n".format(converttov6(ip), ip_address_to_mac(ip)%(0), x)
                output += "table_add ipv4_lpm ipv4_forward {}/32 => {} {}\n".format(ip, ip_address_to_mac(ip)%(0), x)
                output+="table_add srv6_my_sid srv6_end {}/128 =>\n".format(mac_to_ipv6_linklocal(ip_address_to_mac(ip)%(1)))

        for x in self.G.edges(idx):
            if is_spine:
                ip = mac_to_ipv6_linklocal(id_to_mac(idx+1, x[1]+1, is_spine))
            else:
                ip = mac_to_ipv6_linklocal(id_to_mac(x[1]+1, idx+1, is_spine))
            
            output+="table_add srv6_my_sid srv6_end {}/128 =>\n".format(ip)

        output += "table_add l2_exact_table drop 33:33:00:00:00:16 =>\ntable_add l2_exact_table drop 33:33:00:00:00:02 =>\ntable_add l2_exact_table drop 33:33:00:00:00:fb =>\n"

        output += "mc_mgrp_create 1\n"
        output+="mc_node_create 0 "

        for x in range(1, l+1):
            output+="{} ".format(x)
        output += "\n"
        output += "mc_node_associate 1 0\n"

        output += "table_add l2_ternary_table set_multicast_group 33:33:00:00:00:00&&&0xFFFF00000000 => 1 0\n"

        return output
        
    def generate_commands(self, proportion, timeout):
        for i, x in enumerate(self.switches):
            res = self.generate_command(x, i, self.hosts_per_leaf, proportion, timeout)
            f = open(x+".txt", "w")
            f.write(res)
            f.close()

    def write_to_file(self):
        config = "\"p4_src\": \"p4_src/int.p4\",\n\"cli\": true,\n\"pcap_dump\": true,\n\"enable_log\": true,"
        assignment_strategy = "\"assignment_strategy\": \"mixed\""
        output=""

        id_h=1
        id_s=1
        for n in self.switches:
            if n.startswith("LE"):
                for x in range(1, self.hosts_per_leaf+1):
                    ip = "10.0.{}.{}".format(id_s, ((id_h-1)%self.hosts_per_leaf)+1)
                    print(ip)
                    self.hosts.append(("H"+str(id_h), ip))
                    self.links.append([n,"H"+str(id_h), ip_address_to_mac(ip) % (1), ip_address_to_mac(ip) % (0)])
                    id_h+=1
            id_s+=1

        

        output += "{" + config + "\n"
        output += "\"topology\": {\n"
        output += assignment_strategy + ",\n"
        output += "\"default\": {\"bw\": 2},\n"
        output += "\"links\": ["

        for x in self.links:
            if len(x) == 2:
                    x.append(id_to_mac(int(x[1][2:]), int(x[0][2:]), False))
                    x.append(id_to_mac(int(x[1][2:]), int(x[0][2:]), True))

            output += "[\"" + x[0] + "\", " + "\"" + x[1] + "\"" + ",{\"bw\": 3, \"addr1\": \""+ x[2] +"\", \"addr2\": \"" + x[3] + "\"}],"

        #print(links)

        output = output[:-1] + "],\n"

        output += "\"hosts\": {"

        for x in self.hosts:
            output += "\"" + x[0] + "\": {},"

        output = output[:-1] + '}, \n'
        

        output += "\"switches\": {"
        for x in self.switches:
            output += "\"" + x + "\": {{\"cli_input\": \"topos/{}.txt\"}},".format(x)

        output = output[:-1] + '} \n'

        output += "}\n"
        output += "}\n"

        f = open(self.file, "w")
        f.write(output)
        f.close()

    #print(output)
 
def genFatTree(maxSNum, file=None):  #SNum must be 10,15,20,25,30...
    sys.setrecursionlimit(1000000)
    swSum = 10
    topoLists = []

    swSum = maxSNum//5 * 5
    if swSum < 10: swSum = 10

    L1 = int(swSum/5)
    L2 = L1*2
    L3 = L2

    topoList = [[0 for i in range(swSum)] for i in range(swSum)]
    hostList = [0 for i in range(swSum)]
    linkNum = 0

    core = [0 for i in range(L1)]
    agg = [0 for i in range(L2)]
    edg = [0 for i in range(L3)]

    # add core switches
    for i in range(L1):
        core[i] = i

    # add aggregation switches
    for i in range(L2):
        agg[i] = L1 + i

    # add edge switches
    for i in range(L3):
        edg[i] = L1 + L2 + i

    # add links between core and aggregation switches
    for i in range(L1):
        for j in agg[:]:
            topoList[core[i]][j] = 1
            topoList[j][core[i]] = 1
            linkNum += 2

    # add links between aggregation and edge switches
    for step in range(0, L2, 2):
        for i in agg[step:step+2]:
            for j in edg[step:step+2]:
                topoList[i][j] = 1
                topoList[j][i] = 1
                linkNum += 2
    # hostList
    for i in range((L1+L2), swSum):
        hostList[i] = 1

    return topoList

def genSpineLeaf(maxSNum, proportion=1, timeout=200000, file=None):  #SNum must be 3,6,9,12,15...
    sys.setrecursionlimit(1000000)
    swSum = 3
    links = []
    switches = []

    swSum = maxSNum//3 * 3
    if swSum < 3: swSum = 3

    L2 = int(swSum/3)
    L1 = L2*2

    topoList = [[0 for i in range(swSum)] for i in range(swSum)]

    for i in range(L1):
        for j in range(L1, swSum):
            topoList[i][j] = 1
            topoList[j][i] = 1

    if file:
        for i in range(L1):
            switches.append("LE"+str(i+1))
            for j in range(L1, swSum):
                links.append(["LE"+str(i+1), "SP"+str(j+1)])

        for j in range(L1, swSum):
            switches.append("SP"+str(j+1))

        print(switches)

        f = File_generator(file, nx.from_numpy_matrix(np.array(topoList)), switches, links, L1, 2)
        f.write_to_file()
        f.generate_commands(proportion, timeout)

    #print(switches)
    #print(links)
    
    return topoList

def calOddNum(topoMatrix, sNum):
    count = 0
    for i in range(sNum):
        degreeSum = 0
        for j in range(sNum):
            degreeSum += topoMatrix[i][j]
        if degreeSum%2 == 1:
            count += 1
    return count

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("Usage: python TopoGenerator.py nbr_switches proportion_of_Int flowlet_timeout")
        sys.exit(1)
    
    topoList1 = genSpineLeaf(int(sys.argv[1]), sys.argv[2], sys.argv[3], file="test.json")
    print(len(topoList1))
    #print(topoList1)
    A = np.array(topoList1)
    G = nx.from_numpy_matrix(A)

    print(G.edges(0))
    nx.draw(G)
    matplotlib.pyplot.show()