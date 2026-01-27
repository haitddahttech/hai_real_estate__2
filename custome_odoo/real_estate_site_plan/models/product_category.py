# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductCategory(models.Model):
    _inherit = 'product.category'

    real_estate_color = fields.Char(
        string='Màu sắc',
        default='#3498db',
        help='Mã màu Hex cho các sản phẩm trong danh mục này (ví dụ: #3498db)'
    )

    def _auto_init(self):
        """
        FIX: If the 'color' column in DB is Char (due to previous incorrect version), village
        rename it to avoid Odoo base trying to convert it to Integer and crashing.
        """
        self.env.cr.execute("""
            SELECT data_type FROM information_schema.columns 
            WHERE table_name = 'product_category' AND column_name = 'color'
        """)
        res = self.env.cr.fetchone()
        if res and res[0] in ('character varying', 'text'):
            self.env.cr.execute("ALTER TABLE product_category RENAME COLUMN color TO color_hex_backup")
            self.env.cr.commit()
            
        return super()._auto_init()
    
    
    def write(self, vals):
        """Update all products' color when category color changes"""
        res = super(ProductCategory, self).write(vals)
        
        if 'real_estate_color' in vals:
            # Update all products in this category
            for category in self:
                products = self.env['product.template'].search([
                    ('categ_id', '=', category.id)
                ])
                if products:
                    products.write({'real_estate_color': vals['real_estate_color']})
        
        return res
