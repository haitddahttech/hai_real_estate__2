# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # Fields have been moved to product.template
    # and will be inherited automatically via Odoo product architecture
    pass
