# -*- coding: utf-8 -*-

from odoo import models, fields

class ProductDiscountConfig(models.Model):
    _name = 'product.discount.config'
    _description = 'Cấu hình giảm giá'
    _order = 'name'

    name = fields.Char(string='Tên chương trình', required=True)
    qty = fields.Integer(string='Số lượng', default=1, help="Số lượng mua tối thiểu để áp dụng")
    discount_type = fields.Selection([
        ('percent', 'Phần trăm (%)'),
        ('amount', 'Số tiền cố định')
    ], string='Loại giảm giá', required=True, default='percent')
    discount_value = fields.Float(string='Giá trị giảm', required=True)
    active = fields.Boolean(string='Đang hoạt động', default=True)
