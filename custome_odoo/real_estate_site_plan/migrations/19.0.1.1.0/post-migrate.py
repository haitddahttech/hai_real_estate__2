# -*- coding: utf-8 -*-
"""
Migration 19.0.1.0.0 -> 19.0.1.1.0

Đổi `product.template.direction` từ Selection (varchar) sang Many2one
(`product.template.direction_id` trỏ tới `real.estate.direction`).

Tại thời điểm post-migrate:
  - Cột mới `direction_id` (int) đã được ORM tạo nhờ removal Selection + add Many2one.
  - Cột cũ `direction` (varchar) VẪN còn nguyên (Odoo không tự DROP khi field bị xoá).
  - Seed 14 record `real.estate.direction` đã được load qua data XML.

Script này:
  1. Map mỗi record product_template có direction (varchar) -> direction_id (int)
     bằng cách lookup code trong real_estate_direction.
  2. Log số dòng được migrate + những value không khớp (nếu có).
  3. DROP cột cũ `direction` để tránh nhập nhằng.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        # Fresh install — không cần migrate dữ liệu cũ.
        return

    # 1) Cột cũ phải còn tồn tại; nếu không, có nghĩa là DB đã được migrate trước đó.
    cr.execute("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'product_template' AND column_name = 'direction'
    """)
    if not cr.fetchone():
        _logger.info("[direction-migration] Cột product_template.direction không còn — bỏ qua.")
        return

    # 2) Bản đồ code -> id từ bảng real_estate_direction (đã được seed bởi data XML).
    cr.execute("SELECT code, id FROM real_estate_direction")
    code_to_id = dict(cr.fetchall())
    if not code_to_id:
        _logger.warning(
            "[direction-migration] real_estate_direction trống. "
            "Kiểm tra data/real_estate_direction_data.xml có được load trước post-migrate không."
        )
        return

    # 3) Tổng số dòng có direction để báo cáo.
    cr.execute("""
        SELECT direction, COUNT(*)
        FROM product_template
        WHERE direction IS NOT NULL AND direction <> ''
        GROUP BY direction
    """)
    rows = cr.fetchall()
    total = sum(c for _, c in rows)
    _logger.info("[direction-migration] Có %s product_template cần migrate (%s mã khác nhau).",
                 total, len(rows))

    # 4) UPDATE: set direction_id từ map code -> id.
    cr.execute("""
        UPDATE product_template pt
        SET direction_id = d.id
        FROM real_estate_direction d
        WHERE d.code = pt.direction
          AND pt.direction IS NOT NULL
          AND pt.direction <> ''
    """)
    updated = cr.rowcount
    _logger.info("[direction-migration] Đã set direction_id cho %s product_template.", updated)

    # 5) Cảnh báo các code mồ côi (có trong dữ liệu nhưng không có trong bảng cấu hình).
    cr.execute("""
        SELECT DISTINCT pt.direction
        FROM product_template pt
        WHERE pt.direction IS NOT NULL
          AND pt.direction <> ''
          AND pt.direction_id IS NULL
    """)
    orphans = [r[0] for r in cr.fetchall()]
    if orphans:
        _logger.warning(
            "[direction-migration] Các mã direction sau không khớp seed data, "
            "direction_id để NULL: %s. Hãy tạo record real.estate.direction "
            "tương ứng rồi UPDATE thủ công nếu muốn giữ.",
            orphans,
        )

    # 6) Xoá cột cũ để tránh nhập nhằng key/label sau này.
    cr.execute("ALTER TABLE product_template DROP COLUMN direction")
    _logger.info("[direction-migration] Đã DROP cột cũ product_template.direction.")
