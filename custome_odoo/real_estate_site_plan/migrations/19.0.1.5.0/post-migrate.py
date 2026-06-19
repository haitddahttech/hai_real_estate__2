# -*- coding: utf-8 -*-
"""
Migration 19.0.1.4.0 -> 19.0.1.5.0

Thay doi chinh:
  - product_template.payment_timeline_ids: doi Many2many -> One2many (dung
    ban chat field, qua inverse product_tmpl_id).
  - compute_payment_timeline: refactor de DOC tu payment.schedule.template
    (gan theo product.categ_id) thay vi hard-code. today_marker doi sang
    fields.Date.today() (truoc kia la deposit_date + 1 thang).
  - San pham co categ_id KHONG nam trong template nao -> giu nguyen lich cu,
    khong sinh tu dong (ngu nghia moi: empty product_category_ids = none).

DB schema khong doi: payment_timeline.product_tmpl_id van la FK ton tai.
Du lieu trong payment_timeline khong bi xoa boi migration nay.

Script chi log so luong timeline hien tai + canh bao neu phat hien rac
(san pham co > 30 timeline => dau hieu duplicate tu compute cu).
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT COUNT(*) AS total,
               COUNT(DISTINCT product_tmpl_id) AS products
        FROM payment_timeline
    """)
    total, products = cr.fetchone()
    _logger.info(
        "[v150] payment_timeline hien co %s records cho %s product.template.",
        total, products,
    )

    cr.execute("""
        SELECT product_tmpl_id, COUNT(*) AS n
        FROM payment_timeline
        GROUP BY product_tmpl_id
        HAVING COUNT(*) > 30
        ORDER BY n DESC
        LIMIT 5
    """)
    bloated = cr.fetchall()
    if bloated:
        _logger.warning(
            "[v150] Phat hien %s product co > 30 timeline (duplicate tu compute cu). "
            "Top: %s. User nen click 'Cap nhat lich thanh toan' tren template form "
            "de wipe + regenerate sach.",
            len(bloated), bloated[:3],
        )
