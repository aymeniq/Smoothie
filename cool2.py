#!/usr/bin/env python3

from copy import deepcopy
from p4utils.utils.helper import *
import networkx as nx
import matplotlib
import random

queue_size = 64

class NetGraph(object):
    """docstring for ClassName"""
    def __init__(self):
        self.G = nx.Graph()
        for i in range(64):
            for j in range(128):
                self.G.add_edge("leaf{}".format(j), "spine{}".format(i), bw=10, weight=0.0)

    def set_weights(self):
        max_bw = 0 #used to normalize link capacity between [0, 1]

        for n in list(self.G.edges(data=True)):
            if n[2]["bw"] > max_bw:
                max_bw = n[2]["bw"]

        for n in list(self.G.edges(data=True)):
            n[2]["weight"] = (1/queue_size) / (n[2]["bw"] / max_bw)

        #generator = nx.all_shortest_paths(self.G, source="leaf40", target="leaf15")

        spl = nx.shortest_path_length(self.G, source="leaf40", target="leaf15")
        generator = nx.all_simple_paths(self.G, source="leaf40", target="leaf15", cutoff=spl+1)#generate all paths with a detour of at most n node(s) more than the shortest path
        paths = list(generator)
        len_p = len(paths)

        if len_p == 0:
            return None

        if len_p == 1:
            return paths[0]

        ids = random.sample(range(len_p), 2)
        p1 = paths[ids[0]]
        p2 = paths[ids[1]]

        print(p1)
        print(p2)
        #print(list(generator)[5])
        #print(next(generator))


NetGraph().set_weights()
