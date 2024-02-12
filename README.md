# Smoothie: Dynamic Path Load Balancer for Data Center Networks

## Overview

Smoothie is a dynamic path load balancer specifically designed for real-time congestion management in contemporary Data Center Networks (DCNs). It optimizes resource utilization and prevents congestion by leveraging Inband Network Telemetry (\inband) for collecting network state information and Segment Routing Version 6 (\srsix) for rerouting traffic. Built with the programmable P4 programming language, Smoothie effectively achieves its goals, showcasing superior performance over conventional Equal-Cost Multipath (\ecmp) routing and competitive results compared to other congestion-aware load balancing solutions.

### Code Base for INT and SRv6

Smoothie's development draws inspiration from and collaborates with existing projects in the domains of Inband Network Telemetry (INT) and Segment Routing Version 6 (SRv6). The code base for INT can be found at [INT Platforms](https://github.com/GEANT-DataPlaneProgramming/int-platforms), and for SRv6, you can refer to [NGSDN Tutorial](https://github.com/opennetworkinglab/ngsdn-tutorial).

## Key Features

- **Proactive Congestion Response:** Smoothie minimizes the necessity for TCP congestion window resizing by employing proactive congestion response mechanisms.
- **Intelligent Rerouting:** The ability to intelligently reroute flows onto optimal paths substantially reduces route flapping, enhancing overall network stability.
- **P4 Programmability:** Leveraging the programmable nature of the P4 programming language for dynamic and efficient network management.
- **Inband Network Telemetry (INT):** Collecting real-time network state information for effective congestion management.
- **Segment Routing Version 6 (SRv6):** Rerouting traffic dynamically to optimize resource utilization.
- **Centralized Controller:** Enhanced manageability, ease of maintenance, and simplified deployment through a centralized controller.

## Additionnal information

Check our paper at [paper](link-to-paper)

## Getting Started

To get started with Smoothie, follow the installation and configuration instructions in the [documentation](link-to-documentation).

## Contributing

We welcome contributions! If you'd like to contribute to Smoothie, feel free to contact us (see contact informations below).

## License

Smoothie is licensed under the [MIT License](link-to-license).

## Acknowledgments

We would like to acknowledge [contributors](https://scholar.google.com/citations?user=NFa1AfIAAAAJ&hl=en) who have contributed to the development of Smoothie.

## Contact

For any questions or issues, feel free to contact us at [email@example.com](mailto:lchampagne@uliege.be).