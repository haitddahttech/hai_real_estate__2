# -*- coding: utf-8 -*-
"""product.discount.config.apply_stage trở thành bắt buộc (mặc định loại A).

Trước phiên bản này apply_stage chỉ để hiển thị/lọc nên được phép bỏ trống và
có thêm mốc 'dat_coc'. Nay nó quyết định chiết khấu bị trừ vào đợt nào trên
lịch thanh toán, chỉ còn ba mốc A/B/C và đã required=True:
  - bản ghi còn NULL sẽ chặn việc thêm ràng buộc NOT NULL;
  - bản ghi còn 'dat_coc' sẽ trỏ vào một giá trị không còn trong selection.

Cả hai trường hợp đều được đưa về loại A (trừ thẳng vào đợt Ký HĐMB), đúng
bằng giá trị mặc định của trường. Idempotent: chạy lại không khớp dòng nào.
"""

import logging

_logger = logging.getLogger(__name__)

DEFAULT_STAGE = 'ky_hop_dong'
DROPPED_STAGES = ('dat_coc',)


def migrate(cr, version):
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
