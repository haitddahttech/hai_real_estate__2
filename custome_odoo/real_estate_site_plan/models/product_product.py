# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductProduct(models.Model):
    _inherit = 'product.product'

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
