# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import json


class SitePlanPolygon(models.Model):
    _name = 'site.plan.polygon'
    _description = 'Site Plan Polygon'
    _order = 'name'
    
    _sql_constraints = [
        ('unique_product_template', 'UNIQUE(product_template_id)', 
         'Mỗi sản phẩm chỉ được gán cho một lô đất!'),
    ]

    name = fields.Char(
        string='Tên lô đất',
        required=True,
        help='Tên lô đất (sẽ được dùng làm tên sản phẩm)'
    )
    
    site_plan_id = fields.Many2one(
        comodel_name='site.plan',
        string='Bản đồ mặt bằng',
        required=True,
        ondelete='cascade',
        help='Bản đồ chứa lô đất này'
    )
    
    product_template_id = fields.Many2one(
        comodel_name='product.template',
        string='Sản phẩm',
        required=True,
        ondelete='restrict',
        domain="[('id', 'not in', unavailable_product_template_ids)]",
        help='Sản phẩm liên kết với lô đất này (mỗi sản phẩm chỉ được gán cho 1 lô)'
    )
    
    unavailable_product_template_ids = fields.Many2many(
        comodel_name='product.template',
        compute='_compute_unavailable_products',
        help='Các sản phẩm đã được gán'
    )
    
    coordinates = fields.Text(
        string='Tọa độ',
        required=True,
        help='Mảng JSON tọa độ [{x: 0, y: 0}, ...]'
    )
    
    color = fields.Char(
        string='Màu sắc',
        default='#3498db',
        help='Mã màu Hex (ví dụ: #3498db)'
    )
    
    polygon_type = fields.Selection(
        selection=[
            ('polygon', 'Đa giác'),
            ('rectangle', 'Hình chữ nhật'),
        ],
        string='Loại hình',
        default='polygon',
        required=True
    )
    
    active = fields.Boolean(
        string='Đang hoạt động',
        default=True
    )
    
    @api.depends('site_plan_id')
    def _compute_unavailable_products(self):
        """Compute list of products already assigned to polygons"""
        for record in self:
            # Get all products already assigned to polygons (excluding current record)
            assigned_products = self.env['site.plan.polygon'].search([
                ('id', '!=', record.id),
                ('active', '=', True)
            ]).mapped('product_template_id')
            record.unavailable_product_template_ids = assigned_products
    
    @api.constrains('product_template_id')
    def _check_unique_product(self):
        """Ensure each product is only assigned to one polygon"""
        for record in self:
            domain = [
                ('product_template_id', '=', record.product_template_id.id),
                ('id', '!=', record.id),
                ('active', '=', True)
            ]
            if self.search_count(domain) > 0:
                raise ValidationError(
                    f'Sản phẩm "{record.product_template_id.name}" đã được gán cho lô đất khác. '
                    'Mỗi sản phẩm chỉ được gán cho 1 lô.'
                )
    
    @api.constrains('name', 'site_plan_id')
    def _check_unique_name_per_site_plan(self):
        """Ensure polygon names are unique within a site plan"""
        for record in self:
            domain = [
                ('name', '=', record.name),
                ('site_plan_id', '=', record.site_plan_id.id),
                ('id', '!=', record.id)
            ]
            if self.search_count(domain) > 0:
                raise ValidationError(
                    f'Tên lô đất "{record.name}" đã tồn tại trong bản đồ này. '
                    'Vui lòng chọn tên khác.'
                )
    
    @api.constrains('coordinates')
    def _check_coordinates(self):
        """Validate that coordinates is valid JSON"""
        for record in self:
            try:
                coords = json.loads(record.coordinates)
                if not isinstance(coords, list) or len(coords) < 3:
                    raise ValidationError(
                        'Tọa độ phải là mảng JSON với ít nhất 3 điểm.'
                    )
            except (json.JSONDecodeError, TypeError):
                raise ValidationError(
                    'Tọa độ phải là chuỗi JSON hợp lệ.'
                )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-fill name and color from product"""
        for vals in vals_list:
            if 'product_template_id' not in vals or not vals.get('product_template_id'):
                # Check legacy key if js hasn't updated
                if 'product_id' in vals:
                    vals['product_template_id'] = vals.pop('product_id')
                else:
                    raise ValidationError(
                        'Vui lòng chọn sản phẩm cho lô đất này.'
                    )
            
            product = self.env['product.template'].browse(vals['product_template_id'])
            
            # Auto-fill name from product if not provided
            if 'name' not in vals or not vals.get('name'):
                vals['name'] = product.name
            
            # Auto-fill color from product if not provided
            if 'color' not in vals or not vals.get('color'):
                if product.color:
                    vals['color'] = product.color
                else:
                    vals['color'] = '#3498db'  # Default blue color
        
        return super().create(vals_list)
    
    def write(self, vals):
        """Override write to sync product name if polygon name changes"""
        # Handle legacy key
        if 'product_id' in vals:
            vals['product_template_id'] = vals.pop('product_id')

        if 'name' in vals:
            for record in self:
                if record.product_template_id:
                    record.product_template_id.write({'name': vals['name']})
        
        return super().write(vals)
    
    def unlink(self):
        """Override unlink to handle product deletion"""
        result = super().unlink()
        return result
