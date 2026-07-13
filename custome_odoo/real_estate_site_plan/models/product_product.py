# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductProduct(models.Model):
    _inherit = 'product.product'

    is_inhouse_cart = fields.Boolean(
        string='Thuộc giỏ hàng Inhouse',
        related='product_tmpl_id.is_inhouse_cart',
        readonly=False,
        store=True,
        help='Đánh dấu sản phẩm này thuộc giỏ hàng Inhouse trên portal.'
    )

    is_agency_cart = fields.Boolean(
        string='Thuộc giỏ hàng Đại lý',
        related='product_tmpl_id.is_agency_cart',
        readonly=False,
        store=True,
        help='Đánh dấu sản phẩm này thuộc giỏ hàng Đại lý trên portal.'
    )

    def _auto_init(self):
        """
        Extra safeguard for product_product table.
        """
        self.env.cr.execute("""
            SELECT data_type FROM information_schema.columns 
            WHERE table_name = 'product_product' AND column_name = 'color'
        """)
        res = self.env.cr.fetchone()
        if res and res[0] in ('character varying', 'text'):
            self.env.cr.execute("ALTER TABLE product_product RENAME COLUMN color TO color_hex_backup")
            self.env.cr.commit()
            
        return super()._auto_init()

    @api.onchange('is_inhouse_cart')
    def _onchange_is_inhouse_cart(self):
        for product in self:
            if product.is_inhouse_cart:
                product.is_agency_cart = False

    @api.onchange('is_agency_cart')
    def _onchange_is_agency_cart(self):
        for product in self:
            if product.is_agency_cart:
                product.is_inhouse_cart = False

    @api.constrains('is_inhouse_cart', 'is_agency_cart')
    def _check_cart_membership(self):
        for product in self:
            if product.is_inhouse_cart and product.is_agency_cart:
                raise ValidationError(
                    _('Một sản phẩm không thể đồng thời thuộc cả giỏ hàng Inhouse và Đại lý.')
                )
