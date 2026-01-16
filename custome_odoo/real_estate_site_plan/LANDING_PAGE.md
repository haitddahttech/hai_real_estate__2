# 🏠 Landing Page - Real Estate Site Plan

## 📍 Truy Cập Landing Page

Landing page có thể được truy cập qua URL:

```
http://your-domain.com/real-estate
```

hoặc

```
http://your-domain.com/real-estate/
```

## ✨ Tính Năng

### 1. **Hero Section** (Phần Giới Thiệu)
- Tiêu đề lớn với gradient background đẹp mắt
- Call-to-action button "Xem Dự Án"
- Animation fade-in khi load trang

### 2. **Stats Section** (Thống Kê)
- Hiển thị số lượng dự án
- Tổng số lô đất
- Số lô đất còn trống
- Cards với hover effect

### 3. **Projects Section** (Dự Án Nổi Bật)
- Grid layout hiển thị tối đa 6 dự án
- Mỗi card project có:
  - Icon dự án
  - Tên dự án
  - Mô tả (nếu có)
  - Số lượng lô đất
  - Button "Xem Bản Đồ"
- Hover effect với shadow và transform
- Button "Xem Tất Cả Dự Án" ở cuối

### 4. **Features Section** (Tính Năng Nổi Bật)
- 6 tính năng chính:
  1. Bản Đồ Tương Tác
  2. Tìm Kiếm Nhanh
  3. Thông Tin Chi Tiết
  4. Responsive Design
  5. Cập Nhật Realtime
  6. An Toàn Bảo Mật
- Icon gradient cho mỗi feature
- Hover effect

### 5. **CTA Section** (Call-to-Action)
- Background màu vàng gold (#c9a63f)
- Button "Liên Hệ Ngay"
- Link đến trang contact

## 🎨 Design Highlights

- **Color Scheme:**
  - Primary: Gradient purple (#667eea → #764ba2)
  - Secondary: Gold (#c9a63f)
  - Background: Light gray (#f8f9fa)

- **Typography:**
  - Hero Title: 3.5rem, Bold
  - Section Titles: 2.5rem, Bold
  - Body Text: Responsive sizes

- **Animations:**
  - Fade-in on scroll
  - Hover transforms
  - Smooth transitions

- **Responsive:**
  - Desktop: 3 columns
  - Tablet: 2 columns
  - Mobile: 1 column

## 🔗 Navigation Flow

```
Landing Page (/real-estate)
    ↓
    ├─→ Xem Dự Án → Projects List (/my/site-plans)
    │                    ↓
    │                    └─→ Site Plan Detail (/my/site-plan/{id})
    │                              ↓
    │                              └─→ Property Detail (/my/property/{id})
    │
    └─→ Liên Hệ Ngay → Contact Page (/contactus)
```

## 📱 Screenshots

### Desktop View
- Full-width hero section
- 3-column project grid
- 3-column features grid

### Mobile View
- Stacked sections
- Single column layout
- Touch-friendly buttons

## 🚀 Cách Sử Dụng

1. **Cài đặt module:**
   ```bash
   # Update module
   odoo-bin -u real_estate_site_plan -d your_database
   ```

2. **Truy cập landing page:**
   - Mở browser
   - Vào `http://localhost:8069/real-estate`

3. **Tùy chỉnh:**
   - Chỉnh sửa file: `views/portal/portal_landing_page.xml`
   - Thay đổi text, colors, images theo ý muốn
   - Restart Odoo và update module

## 🎯 SEO Optimization

Landing page đã được tối ưu cho SEO:
- ✅ Semantic HTML5
- ✅ Proper heading hierarchy (H1, H2, H3)
- ✅ Meta tags (inherited from website.layout)
- ✅ Fast loading (inline CSS)
- ✅ Mobile-friendly
- ✅ Accessible (ARIA labels)

## 🔧 Customization

### Thay đổi màu sắc:

```css
/* Trong portal_landing_page.xml, tìm và sửa: */

/* Hero gradient */
background: linear-gradient(135deg, #YOUR_COLOR_1 0%, #YOUR_COLOR_2 100%);

/* Gold color */
background: #YOUR_GOLD_COLOR;
```

### Thay đổi số lượng dự án hiển thị:

```xml
<!-- Tìm dòng: -->
<t t-set="site_plans" t-value="request.env['site.plan'].sudo().search([('active', '=', True)], limit=6)"/>

<!-- Thay 6 thành số khác -->
```

### Thêm/Bớt features:

Tìm section `features-section` và thêm/xóa các `feature-card` div.

## 📞 Support

Nếu có vấn đề, vui lòng liên hệ team phát triển.

---

**Version:** 1.0.0  
**Last Updated:** 2026-01-14
