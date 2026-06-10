# VANET V2V/V2I Collision Warning Simulation Report

## Experiment cases

| case_id                  | case_name                                 | communication_mode   | protocol   |   packet_size_bytes | control_algorithm   |   collisions |   target_receivers |   unique_warning_receivers |   receiver_coverage |   warnings_sent |   warnings_delivered |   lost_packets |   packet_pdr |   pdr |   avg_delay_s |   max_delay_s |   first_warning_time_s | reaction_gain_s   |   min_gap_m |   bytes_sent |   bytes_delivered |   channel_load |   data_rate_bps |   v2v_warnings_sent |   v2v_warnings_delivered |   v2v_lost_packets |   v2v_bytes_sent |   v2i_warnings_sent |   v2i_warnings_delivered |   v2i_lost_packets |   v2i_bytes_sent |   rsu_count |
|:-------------------------|:------------------------------------------|:---------------------|:-----------|--------------------:|:--------------------|-------------:|-------------------:|---------------------------:|--------------------:|----------------:|---------------------:|---------------:|-------------:|------:|--------------:|--------------:|-----------------------:|:------------------|------------:|-------------:|------------------:|---------------:|----------------:|--------------------:|-------------------------:|-------------------:|-----------------:|--------------------:|-------------------------:|-------------------:|-----------------:|------------:|
| C12_v2v_cv2x_packet_600B | Protocol test - V2V C-V2X-like, 600 bytes | v2v                  | CV2X_PC5   |                 600 | ttc_adaptive        |            1 |                  1 |                         12 |                  12 |              29 |                   29 |              0 |            1 |     1 |      0.318813 |       0.83548 |                   47.4 |                   |         nan |        17400 |             17400 |    0.000154667 |           1e+07 |                  29 |                       29 |                  0 |            17400 |                   0 |                        0 |                  0 |                0 |           0 |


## Metric definitions

- **communication_mode**: `none`, `v2v`, `v2i`, or `hybrid`.

- **protocol**: abstract communication protocol profile used by the delay/packet model.

- **packet_size_bytes**: warning packet size. Larger packets increase transmission delay and communication overhead.

- **packet_pdr**: packet-level delivery ratio = delivered packets / sent packets.

- **receiver_coverage**: warned affected vehicles / target affected vehicles. This is separated from packet PDR.

- **avg_delay_s** and **max_delay_s**: delay from accident creation to warning reception.

- **bytes_sent** and **channel_load**: communication overhead indicators.

- **collisions** and **min_gap_m**: traffic safety indicators. Lower collisions and higher gap are better.


## Recommended discussion

Compare the no-warning baseline against V2V, V2I, and hybrid communication. Direct V2V is usually fast and infrastructure-free, but its range is limited. Multi-hop V2V increases coverage but can increase delay and packet overhead. V2I uses roadside units, so coverage depends on RSU placement and RSU range. The hybrid mode combines local V2V warning with infrastructure-assisted warning and is expected to provide the most robust coverage at the cost of higher overhead.


## Packet-size/protocol discussion

Use the generated packet-size plots to explain how larger packets increase transmission time, bytes sent, and channel load. If packet loss is enabled, packet PDR and receiver coverage may decrease. This gives a direct experiment for evaluating the impact of communication protocol parameters and packet size on VANET safety performance.
