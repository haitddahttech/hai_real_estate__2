# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ProductDiscountConfig(models.Model):
    _name = 'product.discount.config'
    _description = 'Cấu hình giảm giá'
    _order = 'sequence, name'

    name = fields.Char(string='Tên chương trình', translate=True, required=True)
    sequence = fields.Integer(string='Thứ tự', default=10, help="Thứ tự hiển thị, số nhỏ hơn sẽ hiển thị trước")
    qty = fields.Float(string='% giảm trên giá bán', default=0,
        help="Chỉ dùng cho loại 'Công thức % tính lại tổng giá'. "
             "Nhập 1 nghĩa là 1% giảm trên giá bán chưa TSDĐ, kéo theo VAT và Quỹ bảo trì tính lại.")
    discount_type = fields.Selection([
        ('percent',        'Phần trăm (%)'),
        ('amount',         'Số tiền cố định'),
        ('formula',        'Công thức theo sản phẩm'),
        ('percent_recalc', 'Công thức % tính lại tổng giá'),
    ], string='Loại giảm giá', required=True, default='percent')
    discount_value = fields.Float(string='Giá trị giảm', default=0,
        help="Phần trăm/số tiền/hệ số nhân tuỳ theo loại giảm giá. "
             "Không dùng cho loại 'Công thức % tính lại tổng giá' (dùng % giảm trên giá bán).")
    formula_type = fields.Selection([
        ('management_fee', 'Phí quản lý × Diện tích × Hệ số'),
        ('maintenance_fee', 'Phí bảo trì × Diện tích × Hệ số'),
        ('custom', 'Tùy chỉnh')
    ], string='Loại công thức', default='management_fee',
        help="Chọn công thức tính chiết khấu theo sản phẩm")
    active = fields.Boolean(string='Đang hoạt động', default=True)
    product_categ_ids = fields.Many2many('product.category', string='Áp dụng cho Danh mục',
        help="Để trống nếu áp dụng cho tất cả danh mục")

    def check_eligibility(self, product):
        """Kiểm tra xem sản phẩm có được phép áp dụng giảm giá này không"""
        self.ensure_one()
        # Nếu đã chọn danh mục cụ thể thì phải thuộc danh mục đó
        if self.product_categ_ids and product.categ_id not in self.product_categ_ids:
            return False
        return True

    def compute_discount_for_product(self, product):
        """Tính giá trị chiết khấu cho một sản phẩm cụ thể."""
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
        elif self.discount_type == 'percent_recalc':
            return self._compute_percent_recalc(product)
        return 0

    def _compute_percent_recalc(self, product):
        """Công thức % tính lại tổng giá:
            Giá bán sau   = round(price_exclude_land_tax × (100-qty)/100, 4)
            VAT sau       = 10% × Giá bán sau
            Quỹ BT sau    = round((Giá bán sau + land_tax) × 0.5%, -3)
            Tổng giá sau  = Giá bán sau + land_tax + VAT sau + Quỹ BT sau

        Trả về số tiền giảm = list_price (tổng gốc) − Tổng giá sau.
        """
        self.ensure_one()
        q = self.qty or 0.0
        if q <= 0 or q >= 100:
            return 0.0
        sale = product.price_exclude_land_tax or 0.0
        land = product.land_tax or 0.0
        list_price = product.list_price or 0.0
        new_sale  = round(sale * (100.0 - q) / 100.0, 4)
        new_vat   = 0.10 * new_sale
        new_maint = round((new_sale + land) * 0.005, -3)        # làm tròn về bội 1000 VND
        new_total = new_sale + land + new_vat + new_maint
        return list_price - new_total
