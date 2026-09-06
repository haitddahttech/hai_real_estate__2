# -*- coding: utf-8 -*-
"""
Migration 19.0.1.9.0 -> 19.0.2.0.0

Thay doi:
  - product_template.vat_tax va maintenance_fee doi tu field nhap tay sang
    stored compute (readonly=False) theo dung cong thuc nghiep vu:
        vat_tax         = 10%  x price_exclude_land_tax
        maintenance_fee = 0,5% x price_include_land_tax  (lam tron nghin)
  - list_price khong con bi ghi de tu compute cua price_include_land_tax nua,
    ma duoc dong bo trong create/write:
        list_price = price_include_land_tax + vat_tax + maintenance_fee

Odoo KHONG tu tinh lai cac dong da ton tai khi mot field chuyen sang compute,
nen migration nay quet toan bo san pham co nhap gia BDS va chi sua nhung dong
LECH so voi cong thuc. Du lieu da dung -> khong bi dong toi, portal/report hien
thi y nguyen.

Sau do sinh lai lich thanh toan cho rieng nhung san pham bi doi VAT, vi
payment.schedule.template dung vat_tax lam co so chia VAT cho tung dot.
"""

import logging

from odoo import api, SUPERUSER_ID
from odoo.addons.real_estate_site_plan.models.product_template import (
    compute_maintenance_fee,
    compute_vat_tax,
)

_logger = logging.getLogger(__name__)


def _differs(currency, current, expected):
    if currency:
        return currency.compare_amounts(current or 0.0, expected or 0.0) != 0
    return abs((current or 0.0) - (expected or 0.0)) > 0.01


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    products = env['product.template'].search([
        '|',
        ('price_exclude_land_tax', '!=', 0),
        ('land_tax', '!=', 0),
    ])
    if not products:
        _logger.info("[v200] Khong co san pham nao co gia BDS, bo qua.")
        return

    _logger.info("[v200] Kiem tra %s san pham co nhap gia BDS.", len(products))

    vat_changed = env['product.template']
    n_vat = n_maint = n_list = 0

    for product in products:
        currency = product.currency_id
        expected_include = product.price_exclude_land_tax + product.land_tax
        expected_vat = compute_vat_tax(product.price_exclude_land_tax)
        expected_maint = compute_maintenance_fee(expected_include)
        expected_list = expected_include + expected_vat + expected_maint

        vals = {}
        if _differs(currency, product.vat_tax, expected_vat):
            _logger.info(
                "[v200] %s: VAT %s -> %s",
                product.name, product.vat_tax, expected_vat,
            )
            vals['vat_tax'] = expected_vat
        if _differs(currency, product.maintenance_fee, expected_maint):
            _logger.info(
                "[v200] %s: Quy bao tri %s -> %s",
                product.name, product.maintenance_fee, expected_maint,
            )
            vals['maintenance_fee'] = expected_maint

        if vals:
            try:
                product.write(vals)
            except Exception as e:
                _logger.warning(
                    "[v200] Loi cap nhat product id=%s (%s): %s",
                    product.id, product.name, e,
                )
                continue
            if 'vat_tax' in vals:
                vat_changed |= product
                n_vat += 1
            if 'maintenance_fee' in vals:
                n_maint += 1

        # write() o tren da tu dong dong bo list_price; day la lo con lai cho
        # nhung san pham co VAT/quy bao tri dung nhung list_price van lech.
        if _differs(currency, product.list_price, expected_list):
            _logger.info(
                "[v200] %s: Gia niem yet %s -> %s",
                product.name, product.list_price, expected_list,
            )
            product.write({'list_price': expected_list})
            n_list += 1

    _logger.info(
        "[v200] Da chuan hoa: VAT %s dong, quy bao tri %s dong, gia niem yet %s dong.",
        n_vat, n_maint, n_list,
    )

    # Chi regen lich thanh toan cho san pham bi doi VAT.
    n_regen = 0
    for product in vat_changed:
        template = product._find_payment_schedule_template()
        if not template:
            continue
        try:
            template._generate_timelines_for_product(product)
            n_regen += 1
        except Exception as e:
            _logger.warning(
                "[v200] Loi regen lich thanh toan cho product id=%s: %s",
                product.id, e,
            )

    _logger.info("[v200] Da sinh lai lich thanh toan cho %s san pham.", n_regen)
