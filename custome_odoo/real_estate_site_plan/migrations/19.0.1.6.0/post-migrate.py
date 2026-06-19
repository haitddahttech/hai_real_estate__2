# -*- coding: utf-8 -*-
"""
Migration 19.0.1.5.0 -> 19.0.1.6.0

Fix UX: cot "So tien thanh toan" (name) tren payment_timeline truoc kia
hien tu line.name ("Dot 4") thay vi mo ta % ("3% +VAT tuong ung").

Migration tu dong regenerate lich thanh toan cho moi product co category
khop voi 1 template — de ten cot duoc cap nhat sang format moi.
San pham khong khop template nao: bo qua (giu lich cu).
"""

import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    # Tat ca template active
    templates = env['payment.schedule.template'].search([('active', '=', True)])
    if not templates:
        _logger.info("[v160] Khong co template active nao, bo qua regen.")
        return

    # Build map: category_id -> template
    cat_to_tpl = {}
    for tpl in templates:
        for cat in tpl.product_category_ids:
            cat_to_tpl[cat.id] = tpl

    if not cat_to_tpl:
        _logger.info("[v160] Khong template nao link category, bo qua regen.")
        return

    _logger.info(
        "[v160] Co %s template active, %s category co template gan.",
        len(templates), len(cat_to_tpl),
    )

    # Loop product trong cac category nay
    cat_ids = list(cat_to_tpl.keys())
    products = env['product.template'].search([('categ_id', 'child_of', cat_ids)])
    if not products:
        _logger.info("[v160] Khong product nao trong cac category, bo qua.")
        return

    fixed = 0
    for product in products:
        # Find matching template via product's category chain
        tpl = None
        cat = product.categ_id
        while cat:
            if cat.id in cat_to_tpl:
                tpl = cat_to_tpl[cat.id]
                break
            cat = cat.parent_id
        if not tpl:
            continue
        try:
            tpl._generate_timelines_for_product(product)
            fixed += 1
        except Exception as e:
            _logger.warning(
                "[v160] Loi regen cho product id=%s: %s", product.id, e,
            )

    _logger.info("[v160] Da regen lich thanh toan cho %s/%s product.", fixed, len(products))
