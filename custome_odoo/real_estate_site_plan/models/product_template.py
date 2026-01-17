# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import timedelta
from dateutil.relativedelta import relativedelta


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    site_plan_polygon_id = fields.Many2one(
        comodel_name='site.plan.polygon',
        string='Site Plan Polygon',
        help='The polygon on the site plan linked to this product',
        ondelete='set null'
    )
    
    is_real_estate = fields.Boolean(
        string='Is Real Estate',
        compute='_compute_is_real_estate',
        store=True,
        help='Indicates if this product is linked to a site plan polygon'
    )

    color = fields.Char(
        string='Color',
        compute='_compute_color',
        store=True,
        readonly=False,
        help='Hex color code for polygon display (inherited from category by default)'
    )
    
    # Real Estate specific fields
    area = fields.Float(
        string='Diện tích đất (m²)',
        digits=(10, 2),
        help='Diện tích đất của lô'
    )

    construction_area = fields.Float(
        string='Diện tích xây dựng (m²)',
        digits=(10, 2),
        help='Diện tích sàn xây dựng'
    )

    price_exclude_land_tax = fields.Monetary(
        string='Giá nhà chưa bao gồm thuế SDĐ',
        currency_field='currency_id',
        help='Giá trị nhà không bao gồm thuế sử dụng đất (tự động tính từ giá bao gồm thuế)'
    )

    land_tax = fields.Monetary(
        string='Thuế sử dụng đất',
        currency_field='currency_id',
    )

    vat_tax = fields.Monetary(
        string='Thuế VAT',
        currency_field='currency_id',
    )

    maintenance_fee = fields.Monetary(
        string='Quỹ bảo trì',
        currency_field='currency_id',
    )

    price_include_land_tax = fields.Monetary(
        string='Giá nhà bao gồm thuế SDĐ',
        currency_field='currency_id',
        help='Giá trị nhà bao gồm thuế sử dụng đất (trường chính - nhập trực tiếp)',
        compute='_compute_price_include_land_tax',
        store=True,
    )
    
    deposit = fields.Monetary(
        string='Đặt cọc',
        currency_field='currency_id',
        help='Số tiền đặt cọc'
    )
    
    discount_config_ids = fields.Many2many(
        comodel_name='product.discount.config',
        string='Giảm giá được phép',
        help='Các chương trình giảm giá có thể áp dụng cho sản phẩm này'
    )
    
    final_price = fields.Monetary(
        string='Giá cuối cùng',
        currency_field='currency_id',
        compute='_compute_final_price',
        store=True,
        help='Giá sau khi trừ các khoản giảm giá (mặc định bằng giá niêm yết)'
    )
    
    price_per_m2 = fields.Monetary(
        string='Đơn giá trung bình',
        currency_field='currency_id',
        compute='_compute_price_per_m2',
        store=True,
        help='Đơn giá trung bình trên m2 đất'
    )
    
    property_type = fields.Selection(
        selection=[
            ('townhouse_garden', 'Liền kề vườn'),
            ('detached_villa', 'Biệt thự đơn lập'),
            ('semi_detached_villa', 'Biệt thự song lập'),
            ('shophouse', 'Shophouse'),
        ],
        string='Loại hình',
        help='Loại hình bất động sản'
    )
    
    direction = fields.Selection(
        selection=[
            ('north', 'Bắc'),
            ('northeast', 'Đông Bắc'),
            ('east', 'Đông'),
            ('southeast', 'Đông Nam'),
            ('south', 'Nam'),
            ('southwest', 'Tây Nam'),
            ('west', 'Tây'),
            ('northwest', 'Tây Bắc'),
        ],
        string='Hướng',
        help='Hướng của bất động sản'
    )
    deposit_date = fields.Date(
        string='Ngày đặt cọc',
        help='Ngày thực hiện đặt cọc'
    )
    payment_timeline_ids = fields.Many2many(
        comodel_name='payment.timeline',
        compute='compute_payment_timeline',
        # inverse_name='product_tmpl_id',
        string='Lịch trình thanh toán',
        help='Payment milestones associated with this product'
    )

    @api.depends('deposit_date', 'price_include_land_tax', 'vat_tax')
    @api.onchange('deposit_date', 'price_include_land_tax', 'vat_tax')
    def compute_payment_timeline(self):
        """Auto-fill payment timeline based on deposit date and total price"""
        currency = self.env.company.currency_id
        for product in self:
            deposit_date = product.deposit_date or fields.Date.today()
            paid_amount = 0.0
            total_price_incl_vat = product.price_include_land_tax + product.vat_tax + product.maintenance_fee
            
            vals_1 = {
                'product_tmpl_id': product.id,
                'type': 'dat_coc',
                'date': deposit_date,#12/12
                'name': 'Đặt cọc',
                'amount': product.deposit,
                'vat_amount': 0.0,
                'bank_amount': 0.0,
                'bank_note': 'KH 20%',
            }
            paid_amount += product.deposit
            vals_2 = {
                'product_tmpl_id': product.id,
                'type': 'trong_3_ngay',
                'date': deposit_date + relativedelta(days=3),#15/12
                'name': '5%',
                'amount': currency.round(product.price_include_land_tax * 0.05) - product.deposit,
                'vat_amount': 0.0,
                'bank_amount': 0,
                'bank_note': 'KH 20%',
            }
            paid_amount += vals_2['amount']
            vals_3 = {
                'product_tmpl_id': product.id,
                'type': 'ky_hop_dong',
                'date': deposit_date + relativedelta(months=1),#12/01
                'name': 'Đủ 20% +VAT',
                'amount': currency.round(product.price_include_land_tax * 0.20) - paid_amount,
                'vat_amount': currency.round(product.vat_tax * 0.20),
                'bank_amount': 0.0,
                'bank_note': 'KH 20%',
            }
            vals_1_2_3_total = currency.round(product.price_include_land_tax * 0.20) + currency.round(product.vat_tax * 0.20)
            vals_1['bank_amount'] = vals_1_2_3_total

            vals_4 = {
                'product_tmpl_id': product.id,
                'type': 'dot_4',
                'date': deposit_date + relativedelta(months=2),#10/02
                'name': '5% +VAT tương ứng',
                'amount': currency.round(product.price_include_land_tax * 0.05),
                'vat_amount': currency.round(product.vat_tax * 0.05),
                'bank_amount': currency.round(product.price_include_land_tax * 0.3 + product.vat_tax * 0.30),
                'bank_note': 'NGÂN HÀNG 30% KHÔNG LÃI, ÂN HẠN GỐC',
            }
            vals_5 = {
                'product_tmpl_id': product.id,
                'type': 'dot_5',
                'date': deposit_date + relativedelta(months=4),#10/04
                'name': '5% +VAT tương ứng',
                'amount': currency.round(product.price_include_land_tax * 0.05),
                'vat_amount': currency.round(product.vat_tax * 0.05),
                'bank_amount': 0.0,
                'bank_note': 'NGÂN HÀNG 30% KHÔNG LÃI, ÂN HẠN GỐC',
            }
            vals_6 = {
                'product_tmpl_id': product.id,
                'type': 'dot_6',
                'date': deposit_date + relativedelta(months=6),#10/06
                'name': '5% +VAT tương ứng',
                'amount': currency.round(product.price_include_land_tax * 0.05),
                'vat_amount': currency.round(product.vat_tax * 0.05),
                'bank_amount': 0.0,
                'bank_note': 'NGÂN HÀNG 30% KHÔNG LÃI, ÂN HẠN GỐC',
            }
            vals_7 = {
                'product_tmpl_id': product.id,
                'type': 'dot_7',
                'date': deposit_date + relativedelta(months=9),#10/09
                'name': '5% +VAT tương ứng',
                'amount': currency.round(product.price_include_land_tax * 0.05),
                'vat_amount': currency.round(product.vat_tax * 0.05),
                'bank_amount': 0.0,
                'bank_note': 'NGÂN HÀNG 30% KHÔNG LÃI, ÂN HẠN GỐC',
            }
            vals_8 = {
                'product_tmpl_id': product.id,
                'type': 'dot_8',
                'date': deposit_date + relativedelta(months=12),#10/12
                'name': '5% +VAT tương ứng',
                'amount': currency.round(product.price_include_land_tax * 0.05),
                'vat_amount': currency.round(product.vat_tax * 0.05),
                'bank_amount': 0.0,
                'bank_note': 'NGÂN HÀNG 30% KHÔNG LÃI, ÂN HẠN GỐC',
            }
            vals_9 = {
                'product_tmpl_id': product.id,
                'type': 'dot_9',
                'date': deposit_date + relativedelta(months=15),#10/03
                'name': '5% +VAT tương ứng',
                'amount': currency.round(product.price_include_land_tax * 0.05),
                'vat_amount': currency.round(product.vat_tax * 0.05),
                'bank_amount': 0.0,
                'bank_note': 'NGÂN HÀNG 30% KHÔNG LÃI, ÂN HẠN GỐC',
            }
            vals_10 = {
                'product_tmpl_id': product.id,
                'type': 'giao_nha',
                'date': deposit_date + relativedelta(months=18),#10/06
                'name': '45% +VAT còn lại',
                'amount': currency.round(product.price_include_land_tax * 0.45),
                'vat_amount': currency.round(product.vat_tax * 0.50),
                'bank_amount': currency.round(product.price_include_land_tax * 0.35 + product.vat_tax * 0.40),
                'bank_note': 'NGÂN HÀNG 35%',
            }
            vals_11 = {
                'product_tmpl_id': product.id,
                'type': 'quy_bao_tri',
                'date': deposit_date + relativedelta(months=18),#10/06
                'name': '0.5%',
                'amount': currency.round(product.maintenance_fee),
                'vat_amount': 0.0,
                'bank_amount': currency.round(product.price_include_land_tax * 0.10 + product.vat_tax * 0.10 + product.maintenance_fee),
                'bank_note': 'KH 10% + QBT',
            }
            vals_12 = {
                'product_tmpl_id': product.id,
                'type': 'thong_bao_so_hong',
                'date': False,
                'name': '5%',
                'amount': currency.round(product.price_include_land_tax * 0.05),
                'vat_amount': 0.0,
                'bank_amount': currency.round(product.price_include_land_tax * 0.05),
                'bank_note': 'NGÂN HÀNG 5%',
            }
            timeline_vals_list = [
                (0, 0, vals_1),
                (0, 0, vals_2),
                (0, 0, vals_3),
                (0, 0, vals_4),
                (0, 0, vals_5),
                (0, 0, vals_6),
                (0, 0, vals_7),
                (0, 0, vals_8),
                (0, 0, vals_9),
                (0, 0, vals_10),
                (0, 0, vals_11),
                (0, 0, vals_12)
            ]
            # Clear existing timelines
            product.payment_timeline_ids.unlink()
            # Create new timelines
            product.write({
                'payment_timeline_ids': timeline_vals_list
            })


    @api.depends('is_real_estate')
    def _compute_is_real_estate(self):
        for product in self:
            product.is_real_estate = bool(product.site_plan_polygon_id)
    
    @api.depends('list_price')
    def _compute_final_price(self):
        for product in self:
            product.final_price = product.list_price

    @api.depends('categ_id', 'categ_id.color')
    def _compute_color(self):
        """Auto-fill color from category if not set"""
        for product in self:
            if not product.color and product.categ_id and product.categ_id.color:
                product.color = product.categ_id.color
            elif not product.color:
                product.color = '#3498db'  # Default blue
    
    @api.depends('list_price', 'area')
    def _compute_price_per_m2(self):
        for product in self:
            if product.area and product.area > 0:
                product.price_per_m2 = product.list_price / product.area
            else:
                product.price_per_m2 = 0.0

    @api.onchange('price_exclude_land_tax', 'land_tax')
    @api.depends('price_exclude_land_tax', 'land_tax')
    def _compute_price_include_land_tax(self):
        for product in self:
            product.sudo().write({
                'price_include_land_tax':product.price_exclude_land_tax + product.land_tax
            })

    # @api.depends('price_include_land_tax')
    # def _inverse_price_exclude_land_tax(self):
    #     for product in self:
    #         product.sudo().write({
    #             'price_exclude_land_tax':product.price_include_land_tax - product.land_tax
    #         })

    @api.onchange('price_include_land_tax', 'vat_tax', 'maintenance_fee')
    @api.depends('price_include_land_tax', 'vat_tax', 'maintenance_fee')
    def compute_list_price(self):
        for product in self:
            product.list_price = product.price_include_land_tax + product.vat_tax + product.maintenance_fee