# -*- coding: utf-8 -*-
"""
Migration 19.0.1.2.0 -> 19.0.1.3.0

Thay doi:
  - Model payment.schedule.template.line bo sung 3 truong: vat_share,
    bank_share, bank_vat_share (Float). ORM tu tao cot.
  - Seed moi: template "Hong Hac City - Biet thu don lap (14 dot)" qua
    data/payment_schedule_hong_hac_villa_data.xml.

Script chi verify seed da load + log so dot.
User se tu link product.category qua UI.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT res_id FROM ir_model_data
        WHERE module = 'real_estate_site_plan'
          AND name = 'payment_schedule_hong_hac_villa'
    """)
    row = cr.fetchone()
    if not row:
        _logger.warning("[hong-hac-migration] Khong tim thay seed payment_schedule_hong_hac_villa.")
        return
    tpl_id = row[0]

    cr.execute(
        "SELECT COUNT(*) FROM payment_schedule_template_line WHERE template_id = %s",
        (tpl_id,),
    )
    n = cr.fetchone()[0]
    _logger.info(
        "[hong-hac-migration] Template Hong Hac Villa id=%s da seed %s dong (mong doi 14).",
        tpl_id, n,
    )
