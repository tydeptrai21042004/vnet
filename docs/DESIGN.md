# Modular VANET Accident-Warning Design

## 1. Corrected system components

| Thành phần | Vai trò trong hệ thống mô phỏng |
|---|---|
| Vehicle / Node | Mỗi xe là một nút mạng VANET, có ID, vị trí, vận tốc, gia tốc, làn đường và trạng thái cảnh báo. |
| OBU / Communication Interface | Module truyền thông trên xe, chịu trách nhiệm gửi/nhận gói cảnh báo. Trong code được mô hình hóa bởi `V2VChannel`. |
| V2V Communication | Truyền cảnh báo trực tiếp từ xe gặp nguy hiểm tới xe lân cận trong phạm vi phủ sóng. |
| Multi-hop Broadcast | Xe đã nhận cảnh báo phát lại cho các xe phía sau để cảnh báo lan truyền trong đoàn xe dài. |
| RSU | Không bắt buộc trong mô phỏng chính; có thể đưa vào phần lý thuyết hoặc mở rộng V2I sau này. |
| Collision Warning Module | Tính TTC, khoảng cách an toàn, phát hiện phanh gấp và quyết định có phát cảnh báo hay không. |
| Driver / Vehicle Control Module | Mô phỏng phản ứng của xe: không có cảnh báo thì phản ứng muộn, có cảnh báo thì phanh sớm hơn. |
| Wireless Channel Model | Mô phỏng phạm vi truyền, độ trễ, mất gói và số hop truyền. |
| OSM/SUMO Preprocessing | Chuyển bản đồ OpenStreetMap sang `.net.xml`, tạo route `.rou.xml`, tạo config `.sumocfg`. |
| Metrics Logger | Ghi collision, PDR, delay, reaction gain, min gap, event log và trajectory. |
| Plot Module | Vẽ biểu đồ collision, PDR, delay, min gap, trajectory và speed. |

## 2. Required scenarios and baselines

| Case ID | Loại | Mô tả | Mục đích |
|---|---|---|---|
| C0_normal_no_incident_baseline | Baseline | Xe chạy bình thường, không có sự cố | Kiểm tra mô phỏng ổn định |
| C1_sudden_brake_no_warning_baseline | Baseline chính | Xe trước phanh gấp, không cảnh báo | Đo mức nguy hiểm khi không có VANET |
| C2_sudden_brake_direct_v2v | Kịch bản 2 | Xe trước phanh gấp, gửi cảnh báo V2V trực tiếp | So sánh hiệu quả cảnh báo trực tiếp |
| C3_platoon_no_warning_baseline | Baseline cho đoàn xe | Nhiều xe chạy theo đoàn, xe đầu phanh gấp, không cảnh báo | So sánh với multi-hop |
| C4_platoon_direct_v2v_limited_range | Baseline kỹ thuật | Đoàn xe dài, V2V trực tiếp nhưng vùng phủ ngắn | Chứng minh giới hạn truyền một chặng |
| C5_platoon_multihop_broadcast | Kịch bản 3 | Đoàn xe dài, cảnh báo được phát lại nhiều chặng | Kiểm tra cảnh báo lan truyền |
| C6_v2v_delay_loss_stress | Stress case | Có cảnh báo nhưng delay cao và mất gói | Đánh giá độ bền của hệ thống |

## 3. Metrics

| Metric | Ý nghĩa |
|---|---|
| collisions | Số va chạm phát hiện được. Càng thấp càng tốt. |
| PDR | Packet Delivery Ratio, tỷ lệ xe cần cảnh báo đã nhận cảnh báo. Càng cao càng tốt. |
| avg_delay_s | Độ trễ cảnh báo trung bình. Càng thấp càng tốt. |
| reaction_gain_s | Mức phản ứng sớm hơn so với phát hiện bằng mắt/logic cục bộ. Càng cao càng tốt. |
| min_gap_m | Khoảng cách nhỏ nhất giữa hai xe. Càng cao càng an toàn. |

## 4. Code architecture

```text
src/vanet_osm_warning/
├── cli.py                 # Command-line interface
├── config.py              # Read JSON config
├── models.py              # Vehicle, message, event, metric dataclasses
├── collision_warning.py   # TTC and safe-distance formulas
├── channel.py             # V2V channel: range, delay, loss, hop
├── synthetic_runner.py    # Pure-Python fallback demo
├── sumo_tools.py          # OSM -> SUMO preprocessing
├── traci_runner.py        # SUMO/TraCI OSM-map simulation
├── metrics.py             # CSV output
├── plots.py               # PNG plots
└── report.py              # Markdown report
```
