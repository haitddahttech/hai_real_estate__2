# -*- coding: utf-8 -*-
"""Chuyển hồ sơ pháp lý từ 5 trường cứng sang tệp đính kèm của bản ghi site.plan.

Trước đây mỗi phân khu chỉ có tối đa 5 file qua project_legal_1..5
(Binary attachment=True → lưu trong ir_attachment kèm res_field).
Nay portal đọc thẳng đính kèm của bản ghi (res_field IS NULL), số lượng tuỳ ý.

Migration này gỡ res_field trên các bản ghi cũ để chúng trở thành đính kèm
thường và tiếp tục hiển thị trên portal — không tệp nào bị mất.
Idempotent: chạy lại lần nữa sẽ không khớp dòng nào.
"""

import logging

_logger = logging.getLogger(__name__)

LEGACY_FIELDS = (
    'project_legal_1',
    'project_legal_2',
    'project_legal_3',
    'project_legal_4',
    'project_legal_5',
)


def migrate(cr, version):
    # Đặt tên hiển thị trước khi gỡ res_field: đính kèm sinh từ trường Binary
    # đôi khi có name trùng tên kỹ thuật của trường, nhìn rất khó hiểu trên portal.
    cr.execute(
        """
        UPDATE ir_attachment
           SET name = COALESCE(NULLIF(store_fname, ''), name)
         WHERE res_model = 'site.plan'
           AND res_field = ANY(%s)
           AND (name IS NULL OR name = '' OR name = res_field)
        """,
        (list(LEGACY_FIELDS),),
    )

    cr.execute(
        """
        UPDATE ir_attachment
           SET res_field = NULL
         WHERE res_model = 'site.plan'
           AND res_field = ANY(%s)
        """,
        (list(LEGACY_FIELDS),),
    )
    _logger.info(
        '[HongHac] Đã chuyển %s hồ sơ pháp lý site.plan sang tệp đính kèm thường.',
        cr.rowcount,
    )
