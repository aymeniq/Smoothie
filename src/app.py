import argparse

from src.Network_API import NetworkAPI
from src.networking import create_int_collection_network


parser = argparse.ArgumentParser(description='Mininet demo')
parser.add_argument('--influx', help='INT collector DB access (InfluxDB host:port)', const="InfluxDB 172.18.0.3:8086",
                    type=str, action="store", nargs='?')
args = parser.parse_args()


net = NetworkAPI()

# Network general options
net.setLogLevel('info')

switches={}
# Network definition
for x in range(1,4,1):
	s = net.addP4Switch('s'+str(x), cli_input='commands/commands'+str(x)+'.txt')
	switches[x] = s

#net.addP4Switch('s2', cli_input='commands/commands2.txt')
#net.addP4Switch('s3', cli_input='commands/commands3.txt')

net.setP4SourceAll('int_v1.0/int.p4')

net.addHost('h1')
net.addHost('h2')
net.addHost('h3')

net.addLink("h1", "s1")
net.addLink("h2", "s2")
net.addLink("h3", "s3")
net.addLink("s1", "s2")
net.addLink("s1", "s3")
net.addLink("s2", "s3")

# Assignment strategy
net.mixed()

# Nodes general options
net.enablePcapDumpAll()
net.enableLogAll()
net.enableCli()


print(net.modules['net'])
#create_int_collection_network(net.switches, influxdb=args.influx)
#net.startNetwork()