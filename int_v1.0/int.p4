/*
 * Copyright 2020-2021 PSNC, FBK
 *
 * Author: Damian Parniewicz, Damu Ding
 *
 * Created in the GN4-3 project.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/////////////////////////////////////////////////////////////////////////////////////////////////////////

#include <core.p4>
#include <v1model.p4>
#include "include/headers.p4"
#include "include/parser.p4"
#include "include/int_source.p4"
#include "include/int_transit.p4"
#include "include/int_sink.p4"
#include "include/forward.p4"
#include "include/port_forward.p4"
#include "include/srv6.p4"
#include "include/flowlet.p4"

control ingress(inout headers hdr, inout metadata meta, inout standard_metadata_t ig_intr_md) {
	

	action ipv4_forward (bit<48> dstAddr, bit<9> port) {
        hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;
        hdr.ethernet.dstAddr = dstAddr;

        ig_intr_md.egress_spec = port;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    table ipv4_lpm {
        key = {hdr.ipv4.dstAddr:lpm;}
        actions = {
            ipv4_forward;
            NoAction;
        }
        size=256;
        default_action=NoAction;
    }

    action drop() {
        mark_to_drop(ig_intr_md);
    }


    // *** L2 BRIDGING
    //
    // Here we define tables to forward packets based on their Ethernet
    // destination address. There are two types of L2 entries that we
    // need to support:
    //
    // 1. Unicast entries: which will be filled in by the control plane when the
    //    location (port) of new hosts is learned.
    // 2. Broadcast/multicast entries: used replicate NDP Neighbor Solicitation
    //    (NS) messages to all host-facing ports;
    //
    // For (2), unlike ARP messages in IPv4 which are broadcasted to Ethernet
    // destination address FF:FF:FF:FF:FF:FF, NDP messages are sent to special
    // Ethernet addresses specified by RFC2464. These addresses are prefixed
    // with 33:33 and the last four octets are the last four octets of the IPv6
    // destination multicast address. The most straightforward way of matching
    // on such IPv6 broadcast/multicast packets, without digging in the details
    // of RFC2464, is to use a ternary match on 33:33:**:**:**:**, where * means
    // "don't care".
    //
    // For this reason, our solution defines two tables. One that matches in an
    // exact fashion (easier to scale on switch ASIC memory) and one that uses
    // ternary matching (which requires more expensive TCAM memories, usually
    // much smaller).

    // --- l2_exact_table (for unicast entries) --------------------------------

    action set_egress_port(port_num_t port_num) {
        ig_intr_md.egress_spec = port_num;
    }

    table l2_exact_table {
        key = {
            hdr.ethernet.dstAddr: exact;
        }
        actions = {
            set_egress_port;
            drop;
            NoAction;
        }
        const default_action = NoAction;
        // The @name annotation is used here to provide a name to this table
        // counter, as it will be needed by the compiler to generate the
        // corresponding P4Info entity.
        @name("l2_exact_table_counter")
        counters = direct_counter(CounterType.packets_and_bytes);
    }

    // --- l2_ternary_table (for broadcast/multicast entries) ------------------

    action set_multicast_group(mcast_group_id_t gid) {
        // gid will be used by the Packet Replication Engine (PRE) in the
        // Traffic Manager--located right after the ingress pipeline, to
        // replicate a packet to multiple egress ports, specified by the control
        // plane by means of P4Runtime MulticastGroupEntry messages.

        if(hdr.ipv6.isValid()) hdr.ipv6.hop_limit = hdr.ipv6.hop_limit - 1;
        ig_intr_md.mcast_grp = gid;
        meta.is_multicast = true;
    }

    table l2_ternary_table {
        key = {
            hdr.ethernet.dstAddr: ternary;
        }
        actions = {
            set_multicast_group;
            @defaultonly NoAction;
        }
        const default_action = NoAction;
        @name("l2_ternary_table_counter")
        counters = direct_counter(CounterType.packets_and_bytes);
    }


    // --- ndp_reply_table -----------------------------------------------------

    action ndp_ns_to_na(mac_addr_t target_mac) {
        hdr.ethernet.srcAddr = target_mac;
        hdr.ethernet.dstAddr = IPV6_MCAST_01;
        ipv6_addr_t host_ipv6_tmp = hdr.ipv6.src_addr;
        hdr.ipv6.src_addr = hdr.ndp.target_ipv6_addr;
        hdr.ipv6.dst_addr = host_ipv6_tmp;
        hdr.ipv6.next_hdr = IP_PROTO_ICMPV6;
        hdr.icmpv6.type = ICMP6_TYPE_NA;
        hdr.ndp.flags = NDP_FLAG_ROUTER | NDP_FLAG_OVERRIDE;
        hdr.ndp.type = NDP_OPT_TARGET_LL_ADDR;
        hdr.ndp.length = 1;
        hdr.ndp.target_mac_addr = target_mac;
        ig_intr_md.egress_spec = ig_intr_md.ingress_port;
    }

    table ndp_reply_table {
        key = {
            hdr.ndp.target_ipv6_addr: exact;
        }
        actions = {
            ndp_ns_to_na;
        }
        @name("ndp_reply_table_counter")
        counters = direct_counter(CounterType.packets_and_bytes);
    }

    // --- my_station_table ---------------------------------------------------

    table my_station_table {
        key = {
            hdr.ethernet.dstAddr: exact;
        }
        actions = { NoAction; }
        @name("my_station_table_counter")
        counters = direct_counter(CounterType.packets_and_bytes);
    }

    // --- routing_v6_table ----------------------------------------------------


    action ecmp_group(bit<14> ecmp_group_id, bit<16> num_nhops){
        hash(meta.ecmp_metadata.ecmp_hash,
        HashAlgorithm.crc16,
        (bit<1>)0,
        { hdr.ipv6.src_addr,
          hdr.ipv6.dst_addr,
          meta.layer34_metadata.l4_src,
          meta.layer34_metadata.l4_dst,
          hdr.ipv6.next_hdr},
        num_nhops);

        meta.ecmp_metadata.ecmp_group_id = ecmp_group_id;
    }

    action ipv6_forward (bit<48> dstAddr, bit<9> port) {
        hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;
        hdr.ethernet.dstAddr = dstAddr;

        ig_intr_md.egress_spec = port;
        hdr.ipv6.hop_limit = hdr.ipv6.hop_limit - 1;
    }


    table ecmp_group_to_nhop {
        key = {
            meta.ecmp_metadata.ecmp_group_id:    exact;
            meta.ecmp_metadata.ecmp_hash: exact;
        }
        actions = {
            drop;
            ipv6_forward;
        }
        size = 1024;
    }

    table ipv6_lpm {
        key = {hdr.ipv6.dst_addr:lpm;}
        actions = {
            ipv6_forward;
            ecmp_group;
            NoAction;
        }
        size=256;
        default_action=NoAction;
    }

    // *** ACL
    //
    // Provides ways to override a previous forwarding decision, for example
    // requiring that a packet is cloned/sent to the CPU, or dropped.
    //
    // We use this table to clone all NDP packets to the control plane, so to
    // enable host discovery. When the location of a new host is discovered, the
    // controller is expected to update the L2 and L3 tables with the
    // correspionding brinding and routing entries.

    action send_to_cpu() {
        ig_intr_md.egress_spec = CPU_PORT;
    }

    action clone_to_cpu() {
        // Cloning is achieved by using a v1model-specific primitive. Here we
        // set the type of clone operation (ingress-to-egress pipeline), the
        // clone session ID (the CPU one), and the metadata fields we want to
        // preserve for the cloned packet replica.
        return;
        //clone3(CloneType.I2E, CPU_CLONE_SESSION_ID, { ig_intr_md.ingress_port });
    }

    table acl_table {
        key = {
            ig_intr_md.ingress_port:        ternary;
            hdr.ethernet.dstAddr:           ternary;
            hdr.ethernet.srcAddr:           ternary;
            hdr.ethernet.etherType:         ternary;
            meta.ip_proto:                  ternary;
            meta.icmp_type:                 ternary;
            meta.layer34_metadata.l4_src:       ternary;
            meta.layer34_metadata.l4_dst:       ternary;
        }
        actions = {
            send_to_cpu;
            clone_to_cpu;
            drop;
        }
        @name("acl_table_counter")
        counters = direct_counter(CounterType.packets_and_bytes);
    }

	apply {


        if (hdr.cpu_out.isValid()) {
            ig_intr_md.egress_spec = hdr.cpu_out.egress_port;
            hdr.cpu_out.setInvalid();
            exit;
        }

        bool do_l3_l2 = true;

        if (hdr.icmpv6.isValid() && hdr.icmpv6.type == ICMP6_TYPE_NS) {
            if (ndp_reply_table.apply().hit) {
                do_l3_l2 = false;
            }
        }

        if (do_l3_l2) {

            if (hdr.ipv4.isValid()) ipv4_lpm.apply();

            //if (hdr.ipv6.isValid() && my_station_table.apply().hit) {

            if (hdr.udp.isValid() || hdr.tcp.isValid()) {
                // in case of INT source port add main INT headers
                Int_source.apply(hdr, meta, ig_intr_md);
            }

            if (hdr.ipv6.isValid()){
                SRv6.apply(hdr, meta, ig_intr_md);
                switch (ipv6_lpm.apply().action_run){
                    ecmp_group: {
                        ecmp_group_to_nhop.apply();
                    }
                }
                if(hdr.ipv6.hop_limit == 0) { drop(); }
            }

            // L2 bridging logic. Apply the exact table first...
            if (!l2_exact_table.apply().hit) {
                // ...if an entry is NOT found, apply the ternary one in case
                // this is a multicast/broadcast NDP NS packet.
                l2_ternary_table.apply();
                if(meta.is_multicast && hdr.ipv6.hop_limit < 252){mark_to_drop(ig_intr_md);}//drop multicast packet
            }

            if (hdr.udp.isValid() || hdr.tcp.isValid()){
                // in case of sink node make packet clone I2E in order to create INT report
                // which will be send to INT reporting port
                Int_sink_config.apply(hdr, meta, ig_intr_md);
            }

            Flowlet.apply(hdr, meta, ig_intr_md);
        }

        // Lastly, apply the ACL table.
        acl_table.apply();
	}
}

control egress(inout headers hdr, inout metadata meta, inout standard_metadata_t eg_intr_md) {
	apply {

        log_msg("Q depth: {}", {eg_intr_md.enq_qdepth});


        if (eg_intr_md.egress_port == CPU_PORT) {
            hdr.cpu_in.setValid();
            hdr.cpu_in.ingress_port = eg_intr_md.ingress_port;
            exit;
        }

        // If this is a multicast packet (flag set by l2_ternary_table), make
        // sure we are not replicating the packet on the same port where it was
        // received. This is useful to avoid broadcasting NDP requests on the
        // ingress port.
        if(eg_intr_md.egress_port == 1 &&
           hdr.ipv6.isValid()){hdr.ipv6.hop_limit = 255;}//no router in the network therefore packet will be dropped if hop_limit different
        if (meta.is_multicast == true &&
            eg_intr_md.ingress_port == eg_intr_md.egress_port) {
            mark_to_drop(eg_intr_md);
        }

		Int_transit.apply(hdr, meta, eg_intr_md);
		// in case of the INT sink port remove INT headers
		// when frame duplicate on the INT report port then reformat frame into INT report frame
		Int_sink.apply(hdr, meta, eg_intr_md);

        if(hdr.tcp.isValid()) meta.tcpLen = hdr.ipv4.totalLen - (bit<16>)(hdr.ipv4.ihl)*4;
	}
}

V1Switch(ParserImpl(), verifyChecksum(), ingress(), egress(), computeChecksum(), DeparserImpl()) main;





