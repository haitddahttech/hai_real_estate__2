# -*- coding: utf-8 -*-
"""product.discount.config.apply_stage trở thành bắt buộc (mặc định loại A).

Trước phiên bản này apply_stage chỉ để hiển thị/lọc nên được phép bỏ trống và
có thêm mốc 'dat_coc'. Nay nó quyết định chiết khấu bị trừ vào đợt nào trên
lịch thanh toán, chỉ còn ba mốc A/B/C và đã required=True:
  - bản ghi còn NULL sẽ chặn việc thêm ràng buộc NOT NULL;
  - bản ghi còn 'dat_coc' sẽ trỏ vào một giá trị không còn trong selection.

Cả hai trường hợp đều được đưa về loại A (trừ thẳng vào đợt Ký HĐMB), đúng
bằng giá trị mặc định của trường. Idempotent: chạy lại không khớp dòng nào.

LƯU Ý: đây là pre-migrate, chạy TRƯỚC khi ORM cập nhật schema. Cột apply_stage
chỉ tồn tại nếu DB đã từng đi qua phiên bản có trường này. Khi nâng cấp nhảy
cóc từ một bản cũ hơn (vd 19.0.1.x -> 19.0.2.7.0) thì cột chưa hề được tạo,
không có dữ liệu cũ nào để dọn, và ORM sẽ tự tạo cột với default = loại A ngay
sau đó. Vì vậy phải kiểm tra sự tồn tại của cột trước khi UPDATE, nếu không
toàn bộ quá trình nâng cấp sẽ dừng với lỗi UndefinedColumn.
"""

import logging

_logger = logging.getLogger(__name__)

DEFAULT_STAGE = 'ky_hop_dong'
DROPPED_STAGES = ('dat_coc',)


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = %s
           AND column_name = %s
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not _column_exists(cr, 'product_discount_config', 'apply_stage'):
        _logger.info(
            "product.discount.config: chua co cot apply_stage (nang cap nhay coc "
            "tu ban cu) — khong co du lieu cu de don, ORM se tao cot voi "
            "default = '%s'.",
            DEFAULT_STAGE,
        )
        return

    cr.execute(
        """
        UPDATE product_discount_config
           SET apply_stage = %s
         WHERE apply_stage IS NULL
            OR apply_stage IN %s
        """,
        (DEFAULT_STAGE, DROPPED_STAGES),
    )
    if cr.rowcount:
        _logger.info(
            "product.discount.config: dat apply_stage = '%s' cho %s ban ghi "
            "con trong hoac dang dung moc da bo.",
            DEFAULT_STAGE, cr.rowcount,
        )
