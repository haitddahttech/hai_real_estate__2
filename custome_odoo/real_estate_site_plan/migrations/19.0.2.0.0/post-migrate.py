# -*- coding: utf-8 -*-
"""Cài lại font brand vào hệ thống mỗi lần module được update lên 19.0.2.0.0+.

post_init_hook chỉ chạy khi INSTALL lần đầu; update module không gọi lại nó.
Migration này đảm bảo font luôn được đồng bộ vào server sau mỗi lần `-u`.
Idempotent — xem hooks.install_brand_fonts.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    try:
        from odoo.addons.real_estate_site_plan.hooks import install_brand_fonts
        install_brand_fonts()
    except Exception as err:  # noqa: BLE001 - không được để migration crash vì font
        _logger.warning('[HongHac fonts] Cài font trong migration thất bại: %s', err)
