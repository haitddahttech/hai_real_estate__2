# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ProductDiscountConfig(models.Model):
    _name = 'product.discount.config'
    _description = 'Cấu hình giảm giá'
    _order = 'sequence, name'

    name = fields.Char(string='Tên chương trình', required=True)
    sequence = fields.Integer(string='Thứ tự', default=10, help="Thứ tự hiển thị, số nhỏ hơn sẽ hiển thị trước")
    qty = fields.Integer(string='Số lượng', default=1, help="Số lượng mua tối thiểu để áp dụng")
    discount_type = fields.Selection([
        ('percent', 'Phần trăm (%)'),
        ('amount', 'Số tiền cố định'),
        ('formula', 'Công thức theo sản phẩm')
    ], string='Loại giảm giá', required=True, default='percent')
    discount_value = fields.Float(string='Giá trị giảm', required=True,
        help="Với loại 'Công thức': đây là hệ số nhân (ví dụ: 24 cho 24 tháng)")
    formula_type = fields.Selection([
        ('management_fee', 'Phí quản lý × Diện tích × Hệ số'),
        ('maintenance_fee', 'Phí bảo trì × Diện tích × Hệ số'),
        ('custom', 'Tùy chỉnh')
    ], string='Loại công thức', default='management_fee',
        help="Chọn công thức tính chiết khấu theo sản phẩm")
    active = fields.Boolean(string='Đang hoạt động', default=True)

    def compute_discount_for_product(self, product):
        """Tính giá trị chiết khấu cho một sản phẩm cụ thể"""
        self.ensure_one()
        if self.discount_type == 'percent':
            return product.list_price * self.discount_value / 100.0
        elif self.discount_type == 'amount':
            return self.discount_value
        elif self.discount_type == 'formula':
            if self.formula_type == 'management_fee':
                # Phí quản lý × Diện tích đất × Hệ số (số tháng)
                management_fee = product.management_fee or 0
                area = product.area or 0
                return management_fee * area * self.discount_value
            elif self.formula_type == 'maintenance_fee':
                # Phí bảo trì × Diện tích đất × Hệ số
                maintenance_fee = product.maintenance_fee or 0
                area = product.area or 0
                return maintenance_fee * area * self.discount_value
            else:
                # Custom - trả về giá trị mặc định
                return self.discount_value
        return 0
