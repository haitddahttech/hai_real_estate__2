# -*- coding: utf-8 -*-
"""
Migration 19.0.1.6.0 -> 19.0.1.7.0

Thay doi:
  - product.discount.config them discount_type='percent_recalc' (Cong thuc %
    tinh lai tong gia).
  - Field qty (truoc kia chet) doi nghia thanh "% giam tren gia ban", type
    Integer -> Float. ORM se ALTER COLUMN tu dong.
  - discount_value bo required=True (vi percent_recalc khong dung).

Migration chi log, khong touch data.
"""
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT COUNT(*) FROM product_discount_config")
    n = cr.fetchone()[0]
    _logger.info(
        "[v170] %s discount.config records, them discount_type='percent_recalc'.", n,
    )
