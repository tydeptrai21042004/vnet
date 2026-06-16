# Mô phỏng cảnh báo VANET: SUMO giữ nguyên và mô phỏng Python không cần SUMO

Repository này cung cấp **hai luồng chạy độc lập**:

1. **Luồng SUMO hiện có**: giữ nguyên toàn bộ cách chạy cũ, bao gồm tiền xử lý bản đồ OSM, chạy SUMO không giao diện và chạy SUMO GUI.
2. **Luồng NO-SUMO mới**: mô phỏng đoàn xe hoàn toàn bằng Python, không gọi SUMO/TraCI, đồng thời tạo Excel, biểu đồ và mô phỏng hành vi tương tác cho từng case.

> Các tệp cấu hình và lệnh SUMO cũ vẫn giữ nguyên. Phần bổ sung chỉ nằm ở lệnh `no-sumo`, cấu hình `configs/no_sumo_30_cases.json`, mô-đun trực quan hóa và script `run_no_sumo_30_cases.sh`.

---

## 1. Cấu trúc quan trọng

```text
vnet-main/
├── configs/
│   ├── default_cases.json           # Cấu hình SUMO cũ, không thay đổi
│   ├── v2v_v2i_packet_cases.json    # Cấu hình SUMO cũ, không thay đổi
│   ├── stress_50cars_cases.json     # Cấu hình SUMO cũ, không thay đổi
│   └── no_sumo_30_cases.json        # 30 case dành riêng cho mô phỏng Python
├── src/vanet_osm_warning/
│   ├── synthetic_runner.py          # Mô hình đoàn xe Python
│   ├── traci_runner.py              # Luồng SUMO/TraCI cũ
│   └── behavior_viz.py              # Replay hành vi và biểu đồ NO-SUMO
├── run_no_sumo_30_cases.sh          # Chạy trọn bộ 30 case không cần SUMO
├── run_vanet_osm_ubuntu.sh          # Script SUMO cũ
├── run_case_gui.sh                  # Script SUMO GUI cũ
└── main.py
```

---

# 2. Chạy trên Windows bằng WSL

## 2.1. Cài WSL và Ubuntu

Mở **PowerShell bằng quyền Administrator** và chạy:

```powershell
wsl --install -d Ubuntu
```

Khởi động lại Windows nếu được yêu cầu. Sau đó mở ứng dụng **Ubuntu** và tạo tài khoản Linux.

Kiểm tra WSL:

```powershell
wsl --status
```

Khuyến nghị sử dụng WSL 2:

```powershell
wsl --set-default-version 2
```

---

## 2.2. Cài công cụ Python trong Ubuntu/WSL

Trong cửa sổ Ubuntu:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip unzip git
```

Luồng NO-SUMO **không cần cài SUMO**.

---

## 2.3. Giải nén repository trong WSL

Ví dụ tệp ZIP nằm trong thư mục Downloads của Windows:

```bash
cd ~
mkdir -p projects
cd projects
unzip /mnt/c/Users/<TEN_WINDOWS>/Downloads/vnet-main.zip
cd vnet-main
```

Thay `<TEN_WINDOWS>` bằng tên tài khoản Windows thực tế.

Có thể kiểm tra đường dẫn Windows bằng:

```bash
ls /mnt/c/Users
```

> Nên chạy dự án trong thư mục Linux như `~/projects/vnet-main`, không nên chạy trực tiếp trong `/mnt/c/...` vì thao tác nhiều tệp thường chậm hơn.

---

# 3. Chạy 30 case hoàn toàn bằng Python, không dùng SUMO

## Cách đơn giản nhất

```bash
cd ~/projects/vnet-main
chmod +x run_no_sumo_30_cases.sh
./run_no_sumo_30_cases.sh
```

Script sẽ tự động:

1. tạo môi trường `.venv`;
2. cài dependencies;
3. chạy đủ 30 case trong `configs/no_sumo_30_cases.json`;
4. xuất CSV và Excel;
5. tạo biểu đồ tĩnh;
6. tạo replay HTML tương tác cho từng case;
7. tạo trang tổng hợp toàn bộ case.

Kết quả chính:

```text
results/no_sumo_30_cases/
├── results.xlsx
├── summary_metrics.csv
├── summary_report.md
├── events_<case_id>.csv
├── trajectories_<case_id>.csv
├── plots/
└── behavior_visualization/
    ├── index.html
    ├── replay_C0_normal_no_incident.html
    ├── ...
    └── replay_C29_dsrc_congested_latency.html
```

---

## 3.1. Mở dashboard từ WSL

```bash
explorer.exe "$(wslpath -w results/no_sumo_30_cases/behavior_visualization/index.html)"
```

Mở Excel:

```bash
explorer.exe "$(wslpath -w results/no_sumo_30_cases/results.xlsx)"
```

Mở thư mục kết quả:

```bash
explorer.exe "$(wslpath -w results/no_sumo_30_cases)"
```

---

## 3.2. Chạy thủ công

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

python main.py no-sumo \
  --config configs/no_sumo_30_cases.json \
  --out results/no_sumo_30_cases \
  --seeds 42
```

Một seed chung giúp các case có điều kiện ngẫu nhiên so sánh được với nhau.

---

## 3.3. Chạy một case cụ thể

Ví dụ kiểm tra kênh DSRC có BER/loss cao:

```bash
source .venv/bin/activate
python main.py no-sumo \
  --config configs/no_sumo_30_cases.json \
  --case C28_dsrc_high_error_channel \
  --out results/no_sumo_C28 \
  --seeds 42
```

Mở replay:

```bash
explorer.exe "$(wslpath -w results/no_sumo_C28/behavior_visualization/index.html)"
```

---

## 3.4. Chạy nhiều seed để lấy thống kê

```bash
source .venv/bin/activate
python main.py no-sumo \
  --config configs/no_sumo_30_cases.json \
  --out results/no_sumo_30_cases_multiseed \
  --seeds 42,43,44
```

Kết quả thống kê được lưu trong:

```text
results/no_sumo_30_cases_multiseed/multi_seed_statistics.csv
results/no_sumo_30_cases_multiseed/results.xlsx
```

Replay sử dụng replication của seed đầu tiên; số liệu tổng hợp sử dụng toàn bộ seed.

---

# 4. Replay hành vi thể hiện gì?

Mỗi case có một tệp HTML riêng, cho phép quan sát trực tiếp:

- vị trí và chuyển động của từng xe;
- xe gây sự cố;
- thời điểm sự cố bắt đầu;
- xe nhận cảnh báo đầu tiên;
- thứ tự các xe nhận cảnh báo;
- truyền trực tiếp V2V;
- chuyển tiếp V2V nhiều hop;
- truyền V2I/hybrid;
- packet thành công và packet loss;
- khoảng trống cảnh báo do mất gói;
- thời điểm xe bắt đầu giảm tốc;
- cảnh báo đến trước hay sau thời điểm nguy hiểm có thể nhìn thấy;
- tốc độ trung bình của đoàn xe;
- số xe đã nhận cảnh báo;
- số packet đã gửi;
- dòng thời gian sự kiện.

Replay có nút play/pause, thanh thời gian và tốc độ phát `0.5×`, `1×`, `2×`, `4×`.

---

# 5. So sánh bên trong cùng giao thức DSRC

30 case không chỉ so sánh V2V với V2I. Các case còn kiểm tra nhiều cấu hình cùng dùng:

```json
"protocol": "DSRC_80211p"
```

Các nhóm đáng chú ý:

| Mục tiêu | Case |
|---|---|
| Direct và multi-hop | `C2`, `C3` |
| Packet 100/300/600/1400 B | `C6`, `C3`, `C7`, `C8` |
| Bộ điều khiển phanh | `C2`, `C13`, `C15`, `C3`, `C14`, `C16` |
| Mật độ 12/30/50 xe | `C22`, `C23`, `C24` |
| Giảm vùng phủ xuống 40 m | `C27` so với `C3` |
| BER/loss cao | `C28` so với `C3` |
| Queue và rebroadcast delay cao | `C29` so với `C3` |

Nhờ đó có thể quan sát tác động của từng tham số đến tốc độ lan truyền cảnh báo và phản ứng phanh, dù tên giao thức vẫn là DSRC 802.11p.

---

# 6. Tạo lại replay từ CSV mà không chạy lại mô phỏng

```bash
source .venv/bin/activate
python main.py visualize-no-sumo \
  --results results/no_sumo_30_cases \
  --config configs/no_sumo_30_cases.json \
  --frame-step 0.25
```

Giảm kích thước HTML bằng:

```bash
python main.py visualize-no-sumo \
  --results results/no_sumo_30_cases \
  --config configs/no_sumo_30_cases.json \
  --frame-step 0.5
```

---

# 7. Luồng SUMO cũ vẫn giữ nguyên

Các lệnh dưới đây vẫn dùng logic SUMO/TraCI hiện có.

## 7.1. Cài SUMO trong WSL

```bash
sudo apt update
sudo apt install -y sumo sumo-tools
export SUMO_HOME=/usr/share/sumo
export PYTHONPATH="$SUMO_HOME/tools:$PYTHONPATH"
```

Có thể thêm vào `~/.bashrc`:

```bash
echo 'export SUMO_HOME=/usr/share/sumo' >> ~/.bashrc
echo 'export PYTHONPATH="$SUMO_HOME/tools:$PYTHONPATH"' >> ~/.bashrc
source ~/.bashrc
```

## 7.2. Chạy SUMO không GUI theo cách cũ

```bash
./run_vanet_osm_ubuntu.sh sumo \
  all \
  data/sumo/osm_map.sumocfg \
  results/sumo_no_gui
```

## 7.3. Chạy SUMO GUI theo cách cũ

WSLg trên Windows 11 thường hiển thị GUI trực tiếp:

```bash
./run_case_gui.sh all data/sumo/osm_map.sumocfg
```

Hoặc chạy một case:

```bash
./run_case_gui.sh C12_v2v_cv2x_packet_600B data/sumo/osm_map.sumocfg
```

## 7.4. Tiền xử lý bản đồ OSM theo cách cũ

```bash
./run_vanet_osm_ubuntu.sh preprocess-osm \
  data/osm/map_td.osm \
  osm_map
```

> Luồng SUMO tiếp tục sử dụng các cấu hình cũ. Tệp `configs/no_sumo_30_cases.json` chỉ dành cho lệnh `no-sumo`.

---

# 8. Kiểm thử

```bash
source .venv/bin/activate
pytest -q
```

Kiểm tra nhanh riêng luồng NO-SUMO:

```bash
python main.py no-sumo \
  --config configs/no_sumo_30_cases.json \
  --case C3_v2v_multihop_dsrc_300B \
  --out results/smoke_no_sumo \
  --seeds 42

test -f results/smoke_no_sumo/results.xlsx
test -f results/smoke_no_sumo/behavior_visualization/index.html
```

---

# 9. Lưu ý diễn giải kết quả

Replay là trực quan hóa đầu ra của mô hình Python, không phải bằng chứng thực nghiệm độc lập cho chuẩn DSRC, C-V2X hoặc LTE/5G ngoài thực tế. Kết luận nên được viết theo dạng:

> Trong các giả định và tham số đã cấu hình, thiết lập A lan truyền cảnh báo sớm hơn và tạo phản ứng giảm tốc sớm hơn thiết lập B.

Không nên khẳng định một giao thức luôn vượt trội trong mọi môi trường nếu chưa hiệu chỉnh tham số bằng dữ liệu đo hoặc tài liệu thực nghiệm phù hợp.

---

# 8. Kiểm thử để xác nhận luồng NO-SUMO chạy được

Repository có bộ kiểm thử riêng cho nhánh Python không dùng SUMO. Bộ test này **không gọi SUMO, SUMO GUI hoặc TraCI**, do đó có thể chạy trực tiếp trên WSL sau khi cài Python.

## 8.1. Chạy toàn bộ kiểm thử NO-SUMO bằng một lệnh

```bash
cd ~/projects/vnet-main
chmod +x test_no_sumo_full.sh
./test_no_sumo_full.sh
```

Script thực hiện ba nhóm kiểm tra:

1. kiểm tra cấu hình có đúng 30 case và không trùng ID;
2. chạy nhanh đủ 30 case bằng `SyntheticPlatoonRunner`;
3. chạy một case hoàn chỉnh qua CLI và kiểm tra Excel, CSV, dashboard, replay HTML;
4. kiểm tra các case đại diện `none`, `v2v`, `v2i`, `hybrid` và DSRC lỗi cao;
5. kiểm tra channel, metrics, ma trận case và các điều kiện hợp lệ nghiên cứu.

Kết thúc thành công sẽ xuất hiện thông báo:

```text
OK: Bộ kiểm thử NO-SUMO đã hoàn thành.
```

## 8.2. Chạy riêng test mới cho 30 case

```bash
source .venv/bin/activate
pytest -q tests/test_no_sumo_30_cases.py
```

Các kiểm tra chính trong tệp này:

| Test | Nội dung xác nhận |
|---|---|
| Catalog 30 case | Có đúng 30 ID duy nhất từ `C0` đến `C29` |
| Load case đại diện | Các cấu hình none/V2V/V2I/hybrid được merge hợp lệ |
| Single-case CLI | Lệnh `python main.py no-sumo` chạy thành công |
| Output đầy đủ | Có `results.xlsx`, metrics CSV, event CSV, trajectory CSV |
| Replay | Có `index.html`, replay riêng và `case_catalog.json` |
| Thực thi 30 case | Tất cả case đều chạy qua mô hình Python và sinh CSV |

## 8.3. Chạy toàn bộ pytest của repository

```bash
source .venv/bin/activate
pytest -q
```

Lệnh này chạy cả các test liên quan đến phần SUMO và tích hợp cũ. Một số test tích hợp có thể lâu hơn bộ NO-SUMO nhanh. Khi chỉ cần xác nhận phần mới không dùng SUMO, ưu tiên:

```bash
./test_no_sumo_full.sh
```

## 8.4. Kiểm tra thủ công sau khi chạy 30 case

Chạy mô phỏng:

```bash
./run_no_sumo_30_cases.sh
```

Kiểm tra các tệp bắt buộc:

```bash
test -s results/no_sumo_30_cases/results.xlsx
test -s results/no_sumo_30_cases/summary_metrics.csv
test -s results/no_sumo_30_cases/behavior_visualization/index.html
```

Kiểm tra số replay phải bằng 30:

```bash
find results/no_sumo_30_cases/behavior_visualization \
  -maxdepth 1 -name 'replay_*.html' | wc -l
```

Kết quả mong đợi:

```text
30
```

Kiểm tra số event và trajectory CSV:

```bash
find results/no_sumo_30_cases -maxdepth 1 -name 'events_*.csv' | wc -l
find results/no_sumo_30_cases -maxdepth 1 -name 'trajectories_*.csv' | wc -l
```

Mỗi lệnh phải trả về:

```text
30
```

Mở dashboard trên Windows từ WSL:

```bash
explorer.exe "$(wslpath -w results/no_sumo_30_cases/behavior_visualization/index.html)"
```
