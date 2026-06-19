# -*- coding: utf-8 -*-
"""
Migration 19.0.1.3.0 -> 19.0.1.4.0

Thay doi nghiep vu:
  - Nut "Cap nhat lich thanh toan" them vao template form (model method).
  - Constraint moi: moi product.category chi nam trong 1 template (1-1 mapping).
  - Ngu nghia moi: product_category_ids = trong nghia la KHONG ap dung cho ai
    (truoc day ngam dinh ap cho tat ca).

Migration nay:
  1. Unlink default template ("payment_schedule_default") khoi 7 category
     da duoc auto-link boi migration 19.0.1.2.0. Ly do: do la auto-link "fallback
     ap cho moi cai", nay phai ngat de:
       (a) khoi conflict voi constraint moi
       (b) khop voi ngu nghia moi (empty = none)
     User can tu link cu the lai sau khi cap nhat.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT res_id FROM ir_model_data
        WHERE module = 'real_estate_site_plan'
          AND name = 'payment_schedule_default'
    """)
    row = cr.fetchone()
    if not row:
        _logger.info("[v140] payment_schedule_default khong ton tai, bo qua cleanup.")
        return

    default_tpl_id = row[0]
    cr.execute(
        "SELECT COUNT(*) FROM payment_schedule_template_categ_rel WHERE template_id = %s",
        (default_tpl_id,),
    )
    existing = cr.fetchone()[0]
    if not existing:
        _logger.info("[v140] Default template khong link category nao, bo qua.")
        return

    cr.execute(
        "DELETE FROM payment_schedule_template_categ_rel WHERE template_id = %s",
        (default_tpl_id,),
    )
    _logger.info(
        "[v140] Da unlink %s category khoi default template (id=%s) "
        "de chuan bi cho constraint 1-1 va ngu nghia moi (empty = none).",
        existing, default_tpl_id,
    )
