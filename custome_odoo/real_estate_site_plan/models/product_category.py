# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductCategory(models.Model):
    _inherit = 'product.category'

    color = fields.Char(
        string='Color',
        default='#3498db',
        help='Hex color code for polygons of products in this category (e.g., #3498db)'
    )
    
    def write(self, vals):
        """Update all products' color when category color changes"""
        res = super(ProductCategory, self).write(vals)
        
        if 'color' in vals:
            # Update all products in this category
            for category in self:
                products = self.env['product.template'].search([
                    ('categ_id', '=', category.id)
                ])
                if products:
                    products.write({'color': vals['color']})
        
        return res
