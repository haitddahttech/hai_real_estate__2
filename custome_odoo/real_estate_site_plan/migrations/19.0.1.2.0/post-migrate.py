# -*- coding: utf-8 -*-
"""
Migration 19.0.1.1.0 -> 19.0.1.2.0

Sinh ra 2 model cấu hình mới:
  - payment.schedule.template (header)
  - payment.schedule.template.line (chi tiết đợt)

Tại thời điểm post-migrate:
  - Bảng payment_schedule_template và payment_schedule_template_line đã được ORM tạo.
  - Seed data XML (data/payment_schedule_template_data.xml) đã chạy → có 1 template
    `payment_schedule_default` với 12 dòng line (dat_coc → thong_bao_so_hong).

Script này:
  1. Verify seed đã load.
  2. Link template mặc định với toàn bộ product.category đang có trong DB
     (để template áp được cho mọi sản phẩm BĐS hiện tại; user có thể chỉnh lại sau).
  3. Log số category đã link + cảnh báo nếu seed không có.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        # Fresh install — seed XML tự lo. Không cần migrate dữ liệu cũ.
        return

    # 1) Verify seed
    cr.execute("""
        SELECT res_id
        FROM ir_model_data
        WHERE module = 'real_estate_site_plan'
          AND name = 'payment_schedule_default'
    """)
    row = cr.fetchone()
    if not row:
        _logger.warning(
            "[payment-schedule-migration] Không tìm thấy seed `payment_schedule_default`. "
            "Có thể data/payment_schedule_template_data.xml chưa được load. Bỏ qua linking."
        )
        return

    template_id = row[0]
    _logger.info("[payment-schedule-migration] Template mặc định id=%s.", template_id)

    # 2) Đếm số line của template
    cr.execute("SELECT COUNT(*) FROM payment_schedule_template_line WHERE template_id = %s",
               (template_id,))
    line_count = cr.fetchone()[0]
    _logger.info("[payment-schedule-migration] Template có %s đợt thanh toán đã seed.", line_count)
    if line_count < 12:
        _logger.warning(
            "[payment-schedule-migration] Số dòng seed (%s) ít hơn mong đợi (12). "
            "Có thể seed XML không load đầy đủ.",
            line_count,
        )

    # 3) Link với toàn bộ product.category hiện có (relation table M2m).
    #    Bỏ qua các record đã có sẵn (ON CONFLICT DO NOTHING) để idempotent.
    cr.execute("SELECT COUNT(*) FROM product_category")
    total_cat = cr.fetchone()[0]
    if total_cat == 0:
        _logger.info("[payment-schedule-migration] DB chưa có product.category — bỏ linking.")
        return

    # Kiểm tra xem đã link sẵn chưa (user có thể chạy migrate này 2 lần)
    cr.execute("""
        SELECT COUNT(*) FROM payment_schedule_template_categ_rel
        WHERE template_id = %s
    """, (template_id,))
    already_linked = cr.fetchone()[0]
    if already_linked > 0:
        _logger.info(
            "[payment-schedule-migration] Template đã link với %s category — bỏ qua linking.",
            already_linked,
        )
        return

    # Link tất cả categories. INSERT ... SELECT để 1 truy vấn.
    cr.execute("""
        INSERT INTO payment_schedule_template_categ_rel (template_id, category_id)
        SELECT %s, id FROM product_category
        ON CONFLICT DO NOTHING
    """, (template_id,))
    linked = cr.rowcount
    _logger.info(
        "[payment-schedule-migration] Đã link template mặc định với %s/%s product.category.",
        linked, total_cat,
    )
