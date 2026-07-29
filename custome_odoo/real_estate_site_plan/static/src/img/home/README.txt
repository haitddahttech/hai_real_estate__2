HỒNG HẠC CITY — ẢNH TRANG CHỦ
=============================

Thả các ảnh sau vào ĐÚNG thư mục này với ĐÚNG tên (phân biệt hoa/thường):

  hero-poster.jpg   (BẮT BUỘC) — Ảnh tĩnh hero khi video đang tải / mobile. 1920x1080, JPG.
  logo-white.png    (tùy chọn) — Logo trắng/mono nền TRONG SUỐT, hiện trên video tối. PNG.

  feature-1.jpg  ... feature-7.jpg   (7 ảnh nổi bật — full màn hình)
      - Mỗi ảnh: 1920x1080 (hoặc 2560x1440 cho màn retina), JPG, nên ≤ ~1MB.
      - Bố cục chừa khoảng trống cho chữ (giữa / trái / phải) — thứ tự caption:
          feature-1 = Hồng Phát (giữa)
          feature-2 = Hồng Thịnh (chữ căn TRÁI)
          feature-3 = Hồng Phúc (chữ căn PHẢI)
          feature-4 = Chất Sống Xanh (giữa)
          feature-5 = Chất Sống Kinh Bắc (chữ căn TRÁI) — NAY DÙNG VIDEO,
                      xem ../../video/README.txt. feature-5.jpg chỉ còn làm poster.
          feature-6 = Cộng Đồng Hạnh Phúc (chữ căn PHẢI)
          feature-7 = Đô Thị Văn Minh (giữa)

Ghi chú:
- THIẾU FILE = ẨN SECTION. Section feature-N nào không tìm thấy file media sẽ
  không được render (trước đây hiện ra một khung đen rỗng).
- Ảnh sẽ có hiệu ứng Ken Burns (zoom nhẹ) + lớp phủ tối để chữ nổi rõ.
- Muốn đổi CHỮ trên mỗi ảnh: sửa HOME_FEATURES trong
  controllers/portal.py (đã chuyển khỏi template).
- Ảnh card từng DỰ ÁN không đặt ở đây — set ở field "Ảnh đại diện" (cover_image)
  của từng site.plan trong backend Odoo (khuyến nghị 1200x900).
- Sau khi thả file, chỉ cần reload trang (không cần update module).
