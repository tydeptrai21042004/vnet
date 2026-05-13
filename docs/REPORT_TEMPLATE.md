# Report section template for thesis

## Mô hình mô phỏng

Hệ thống mô phỏng gồm các xe di chuyển trên bản đồ đường bộ. Mỗi xe được xem là một nút trong mạng VANET và có khả năng gửi/nhận cảnh báo thông qua module OBU. Khi xe phía trước phanh gấp, hệ thống phát hiện sự kiện nguy hiểm và gửi gói cảnh báo khẩn cấp tới các xe phía sau bằng truyền thông V2V. Trong trường hợp đoàn xe dài, cơ chế multi-hop broadcast được sử dụng để xe đã nhận cảnh báo tiếp tục phát lại cảnh báo cho các xe phía sau.

## Công thức đánh giá nguy cơ va chạm

Thời gian tới va chạm được tính bằng:

```text
TTC = d / (v_rear - v_front)
```

Trong đó:

- `d`: khoảng cách giữa xe sau và xe trước;
- `v_rear`: vận tốc xe sau;
- `v_front`: vận tốc xe trước.

Nếu `TTC` nhỏ hơn ngưỡng an toàn, hệ thống xem tình huống là nguy hiểm.

## Kịch bản mô phỏng

| Kịch bản | Mô tả | Vai trò |
|---|---|---|
| C0 | Xe chạy bình thường, không có sự cố | Baseline ổn định |
| C1 | Xe trước phanh gấp, không cảnh báo | Baseline chính |
| C2 | Xe trước phanh gấp, cảnh báo V2V trực tiếp | Đánh giá V2V trực tiếp |
| C3 | Đoàn xe, không cảnh báo | Baseline đoàn xe |
| C4 | Đoàn xe, V2V trực tiếp, vùng phủ ngắn | Kiểm tra giới hạn một chặng |
| C5 | Đoàn xe, multi-hop broadcast | Kiểm tra cảnh báo lan truyền |
| C6 | Delay/mất gói cao | Stress test |

## Chỉ số đánh giá

| Chỉ số | Ý nghĩa |
|---|---|
| Collision count | Số va chạm, càng thấp càng tốt |
| PDR | Tỷ lệ nhận gói cảnh báo, càng cao càng tốt |
| Average delay | Độ trễ cảnh báo trung bình, càng thấp càng tốt |
| Minimum gap | Khoảng cách nhỏ nhất giữa hai xe, càng cao càng an toàn |
| Reaction gain | Mức phản ứng sớm hơn so với baseline |

## Câu phân tích kết quả mẫu

Kết quả cho thấy kịch bản không sử dụng cảnh báo VANET có số va chạm cao hơn do xe phía sau chỉ phản ứng khi khoảng cách đã quá gần. Khi sử dụng cảnh báo V2V trực tiếp, các xe nằm trong vùng phủ sóng nhận được thông tin phanh gấp sớm hơn, từ đó giảm tốc kịp thời. Tuy nhiên, với đoàn xe dài và phạm vi truyền thông giới hạn, một số xe phía sau không nhận được cảnh báo nếu chỉ dùng truyền trực tiếp một chặng. Cơ chế multi-hop broadcast cải thiện phạm vi lan truyền cảnh báo và làm tăng PDR. Trong trường hợp độ trễ và mất gói cao, hiệu quả cảnh báo giảm, cho thấy các ứng dụng an toàn trong VANET cần đảm bảo độ trễ thấp và độ tin cậy truyền tin cao.
