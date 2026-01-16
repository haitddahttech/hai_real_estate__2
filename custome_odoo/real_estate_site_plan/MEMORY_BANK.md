# Memory Bank: Real Estate Site Plan Module

## 1. Project Overview
Module **Real Estate Site Plan** (`real_estate_site_plan`) cho phép quản lý bản đồ mặt bằng bất động sản trực quan trên Odoo.
- **Mục tiêu:** Cho phép upload ảnh quy hoạch, vẽ các lô đất (polygon/rectangle) trực tiếp trên ảnh, và liên kết mỗi lô đất với một sản phẩm (Product Template).
- **Phạm vi:** Backend (vẽ và quản lý), Frontend Portal (khách hàng xem bản đồ tương tác).
- **Ngôn ngữ:** Python (Odoo Models), JavaScript (OWL & Canvas API), XML (Views).

---

## 2. Technical Architecture

### 2.1. Models Structure
*   **`site.plan`**:
    *   Chứa ảnh gốc bản đồ (`image`).
    *   Quản lý danh sách các lô đất (`polygon_ids`).
    *   Logic active/archive dự án.
*   **`site.plan.polygon`**:
    *   Lưu tọa độ hình vẽ (`coordinates`: JSON Array các điểm `{x, y}`).
    *   Liên kết 1-1 với `product.template`.
    *   Loại hình: Đa giác (`polygon`) hoặc Hình chữ nhật (`rectangle`).
*   **`product.template` (Inherited)**:
    *   Được mở rộng để chứa thông tin BĐS:
        *   `site_plan_polygon_id`: Link ngược lại lô đất.
        *   `area`, `construction_area`: Diện tích đất/xây dựng.
        *   `list_price`: Giá bán (dùng field gốc Odoo).
        *   `price_per_m2`: Đơn giá trung bình (Computed).
        *   Các loại thuế phí: `land_tax`, `vat_tax`, `maintenance_fee`...
        *   Trạng thái: `is_sold` (Đã bán/Còn trống).

### 2.2. Frontend (Backend View - OWL)
*   **Component:** `SitePlanCanvasWidget` (`static/src/js/site_plan_canvas.js`).
*   **Công nghệ:** Odoo OWL Framework + HTML5 Canvas API.
*   **Hệ tọa độ:**
    *   Canvas backend chuẩn hóa ở kích thước logic **1200x800**.
    *   Mọi tọa độ lưu vào DB đều dựa trên hệ quy chiếu 1200x800 này để đảm bảo hiển thị đúng trên mọi màn hình.
    *   Khi vẽ, tọa độ chuột được scale từ kích thước thật của element về hệ 1200x800.
*   **Tính năng chính:**
    *   Modes: Select (chọn/kéo hình), Polygon (vẽ đa giác), Rectangle (vẽ hcn), Edit (di chuyển điểm).
    *   Zoom/Pan: Hỗ trợ zoom lên tới **10x**. Middle mouse hoặc thanh trượt để zoom. Right-click để pan.
    *   Tự động tính toán scale để fit ảnh vào canvas.

### 2.3. Frontend (Portal View)
*   **Controller:** `controllers/portal.py`.
*   **Script:** `static/src/js/portal_site_map.js` (Vanilla JS, không dùng OWL).
*   **Tính năng:**
    *   Hiển thị bản đồ (Read-only).
    *   Popup thông tin khi click vào lô đất.
    *   Trạng thái màu sắc: Xanh (Còn trống) / Xám (Đã bán) / Đỏ (Đang chọn).
    *   Zoom/Pan tương tự backend (Max zoom **10x**).
    *   Font chữ tự động scale theo mức zoom để luôn dễ đọc.

---

## 3. Key Logic Flows

### 3.1. Quy trình vẽ và lưu lô đất
1.  Người dùng upload ảnh vào `site.plan`.
2.  Mở tab "Vẽ Bản Đồ", chọn công cụ vẽ.
3.  Click các điểm trên canvas (Canvas Widget xử lý tọa độ).
4.  Khi hoàn tất (Double click hoặc Enter), Widget gọi `savePolygonDialog`.
5.  Dialog hiện ra (dùng `SelectCreateDialog` của Odoo) để chọn/tạo `product.template`.
    *   *Lưu ý:* Chỉ hiện các Product chưa được gán cho lô đất nào (`domain=['id', 'not in', used_ids]`).
6.  Sau khi chọn Product, Widget gọi `orm.create` để lưu `site.plan.polygon` với `product_template_id` và `coordinates`.

### 3.2. Đồng bộ dữ liệu
*   Khi `site.plan.polygon` được tạo/sửa/xóa, các constraints đảm bảo:
    *   Một Product chỉ thuộc 1 Polygon.
    *   Tên Polygon là duy nhất trong Site Plan.
*   Thông tin hiển thị trên Portal (Giá, Diện tích...) được lấy trực tiếp từ `product.template`.

---

## 4. Current State & Configuration
*   **Ngôn ngữ hiển thị:** Tiếng Việt (Hardcoded trong XML/JS theo yêu cầu).
*   **Zoom Limit:** 0.1x đến 10x.
*   **Màu mặc định:** #3498db (Xanh dương).
*   **Field Mapping:**
    *   `list_price` -> Giá bán.
    *   `area` -> Diện tích đất.
    *   `product_template_id` -> Liên kết sản phẩm.

## 5. Maintenance Notes
*   **Updates:** Khi sửa model `site_plan_polygon`, nhớ cập nhật cả JS (`loadPolygons`, `savePolygon`) vì các field name được hardcode trong `searchRead`.
*   **Views:** View XML của `site_plan` chứa định nghĩa template cho Canvas Widget.
*   **Portal:** File JS portal chạy độc lập, không phụ thuộc OWL registry, cần đảm bảo biến `siteMapData` được render đúng từ Controller.
