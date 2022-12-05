/*

*/

#define REGISTER_SIZE 8192
#define TIMESTAMP_WIDTH 48
#define ID_WIDTH 16
#define FLOWLET_TIMEOUT 48w200000

control Flowlet(inout headers hdr, inout metadata meta, inout standard_metadata_t standard_metadata) {

	//register<bit<ID_WIDTH>>(REGISTER_SIZE) flowlet_to_id;
    register<bit<TIMESTAMP_WIDTH>>(REGISTER_SIZE) flowlet_time_stamp;

    action read_flowlet_registers(){
        bit<128> ip_src;
        bit<128> ip_dst;

    	if (hdr.ipv4.isValid()){
    		ip_src = (bit<128>) hdr.ipv4.srcAddr;
            ip_dst = (bit<128>) hdr.ipv4.dstAddr;
    	} else {
    		ip_src = hdr.ipv6.src_addr;
            ip_dst = hdr.ipv6.dst_addr;
    	}

        //compute register index
        hash(meta.flowlet_register_index, HashAlgorithm.crc16,
            (bit<16>)0,
            { ip_src, ip_dst, meta.layer34_metadata.l4_src, meta.layer34_metadata.l4_dst, meta.layer34_metadata.l4_proto},
            (bit<14>)8192);

         //Read previous time stamp
        flowlet_time_stamp.read(meta.flowlet_last_stamp, (bit<32>)meta.flowlet_register_index);

        //Read previous flowlet id
        //flowlet_to_id.read(meta.flowlet_id, (bit<32>)meta.flowlet_register_index);

        //Update timestamp
        flowlet_time_stamp.write((bit<32>)meta.flowlet_register_index, standard_metadata.ingress_global_timestamp);
    }

    action update_path(){
       meta.update_path = 1;
    }
    
    // table used to activate flow monitoring for an egress port of the switch
    table tb_activate_flow_dest {
        actions = {
            NoAction;
        }
        key = {
            standard_metadata.egress_spec: exact;
        }
        size = 255;
    }

    apply {

        if (!tb_activate_flow_dest.apply().hit) return;

        meta.update_path = 0;

        @atomic {
            read_flowlet_registers();
            meta.flowlet_time_diff = standard_metadata.ingress_global_timestamp - meta.flowlet_last_stamp;

            log_msg("last time: {}", {meta.flowlet_last_stamp});

            //check if inter-packet gap is > FLOWLET_TIMEOUT
            if (meta.flowlet_time_diff > FLOWLET_TIMEOUT){
                update_path();
            }
        }
    }
}