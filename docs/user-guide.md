# DX-FSM User Guide

## Giới thiệu

DX-FSM là nền tảng quản lý dịch vụ thực địa (Field Service Management) giúp tự động hóa quy trình tiếp nhận, phân loại và xử lý yêu cầu từ khách hàng.

## Các vai trò

| Vai trò | Mô tả |
|---|---|
| **Admin** | Quản trị hệ thống |
| **Manager** | Quản lý team, theo dõi dashboard |
| **Technician** | Tiếp nhận và xử lý ticket |
| **Customer** | Tạo yêu cầu hỗ trợ |

## Quy trình xử lý ticket

```
1. Customer tạo ticket → AI tự động phân loại (category, priority)
2. AI gợi ý KTV phù hợp → Manager giao ticket
3. KTV nhận và xử lý → Cập nhật trạng thái
4. Hoàn thành → Customer xác nhận đóng ticket
```

## Tạo ticket mới

1. Đăng nhập → vào **Tickets**
2. Click **+ Tạo Ticket**
3. Điền thông tin:
   - Tiêu đề (bắt buộc)
   - Mô tả chi tiết vấn đề
   - Danh mục (hardware/software/network/electrical)
   - Mức ưu tiên
   - Thông tin liên hệ
4. Submit → Ticket được tạo + AI phân loại tự động

## Trạng thái ticket

| Trạng thái | Màu | Ý nghĩa |
|---|---|---|
| Mới | Xanh dương | Chờ tiếp nhận |
| Đã giao | Tím | Đã gán cho KTV |
| Đang xử lý | Cam | KTV đang làm |
| Chờ | Xám | Chờ phản hồi/thông tin |
| Đã giải quyết | Xanh lá | Xong chờ đóng |
| Đã đóng | Đen | Hoàn tất |
| Đã hủy | Đỏ | Hủy bỏ |

## SLA

| Mức ưu tiên | Thời gian xử lý |
|---|---|
| Critical | 4 giờ |
| High | 24 giờ |
| Medium | 72 giờ |
| Low | 168 giờ (7 ngày) |

## AI Features

- **Auto-classification**: Tự động phân loại ticket dựa trên tiêu đề và mô tả
- **Priority detection**: Gợi ý mức ưu tiên
- **Technician recommendation**: Gợi ý KTV phù hợp nhất

## Dashboard

Dashboard hiển thị:
- Tổng số ticket theo trạng thái
- Ticket quá hạn SLA
- Thời gian xử lý trung bình
- Tải của từng KTV

## Demo Credentials

| User | Password | Role |
|---|---|---|
| admin | <DEMO_PASSWORD> | Admin |
| manager | <DEMO_PASSWORD> | Manager |
| technician | <DEMO_PASSWORD> | Technician |
| customer | <DEMO_PASSWORD> | Customer |
