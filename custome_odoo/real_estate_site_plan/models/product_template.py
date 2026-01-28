# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import timedelta
from dateutil.relativedelta import relativedelta


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    site_plan_polygon_ids = fields.One2many(
        comodel_name='site.plan.polygon',
        inverse_name='product_template_id',
        string='Site Plan Polygons',
        help='The polygons on the site plan linked to this product'
    )

    site_plan_polygon_id = fields.Many2one(
        comodel_name='site.plan.polygon',
        string='Site Plan Polygon',
        compute='_compute_site_plan_polygon_id',
        store=True,
        help='Primary polygon (for backward compatibility)',
        ondelete='set null'
    )
    
    is_real_estate = fields.Boolean(
        string='Is Real Estate',
        compute='_compute_is_real_estate',
        store=True,
        help='Indicates if this product is linked to one or more site plan polygons'
    )
    
    is_decoration = fields.Boolean(
        string='Là vật trang trí',
        help='Đánh dấu sản phẩm này là vật trang trí trên bản đồ (cây, hồ nước, tiện ích...) '
             'để có thể gán cho nhiều polygon và hiển thị thông tin rút gọn.'
    )

    decoration_note = fields.Text(
        string='Mô tả về vật trang trí',
        help='Nội dung giới thiệu hoặc mô tả ngắn sẽ hiển thị trên popup bản đồ.'
    )

    real_estate_color = fields.Char(
        string='Màu sắc',
        compute='_compute_real_estate_color',
        store=True,
        readonly=False,
        help='Mã màu Hex cho polygon (mặc định lấy từ danh mục)'
    )

    def _auto_init(self):
        """
        FIX: If the 'color' column in DB is Char (due to previous incorrect version),
        rename it to avoid Odoo base trying to convert it to Integer and crashing.
        """
        # Check product_template
        self.env.cr.execute("""
            SELECT data_type FROM information_schema.columns 
            WHERE table_name = 'product_template' AND column_name = 'color'
        """)
        res = self.env.cr.fetchone()
        if res and res[0] in ('character varying', 'text'):
            # This is our poisoned column, rename it
            self.env.cr.execute("ALTER TABLE product_template RENAME COLUMN color TO color_hex_backup")
            self.env.cr.commit() # Commit rename immediately
        
        # Check product_category (also inherited and potentially poisoned)
        self.env.cr.execute("""
            SELECT data_type FROM information_schema.columns 
            WHERE table_name = 'product_category' AND column_name = 'color'
        """)
        res = self.env.cr.fetchone()
        if res and res[0] in ('character varying', 'text'):
            self.env.cr.execute("ALTER TABLE product_category RENAME COLUMN color TO color_hex_backup")
            self.env.cr.commit()

        return super()._auto_init()
    
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

    management_fee = fields.Monetary(
        string='Phí quản lý',
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
        relation='product_discount_available_rel',
        column1='product_id',
        column2='discount_id',
        string='Giảm giá được phép',
        help='Các chương trình giảm giá có thể áp dụng cho sản phẩm này'
    )
    
    selected_discount_ids = fields.Many2many(
        comodel_name='product.discount.config',
        relation='product_discount_selected_rel',
        column1='product_id',
        column2='discount_id',
        string='Giảm giá đã chọn',
        help='Các chương trình giảm giá đã được chọn để áp dụng (hiển thị trong PDF)'
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
            ('north_east', 'Bắc - Đông'),
            ('east_west', 'Đông - Tây'),
            ('south_north', 'Nam - Bắc'),
            ('south_east', 'Nam - Đông'),
            ('west_east', 'Tây - Đông'),
            ('southwest_northeast', 'Tây Nam - Đông Bắc'),
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
            if not product.site_plan_polygon_ids:
                fixed_deposit_date = product.deposit_date or fields.Date.today()
            else:
                fixed_deposit_date = product.site_plan_polygon_ids[0].site_plan_id.deposit_date or fields.Date.today()
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
                'date': deposit_date + relativedelta(days=2),#15/12
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

            # Logic gộp tiền cho các đợt từ 4 đến 9
            today = deposit_date + relativedelta(months=1)
            accumulated_amount = 0.0
            accumulated_share = 0.0
            accumulated_vat = 0.0
            accumulated_bank = 0.0
            
            # Danh sách cấu hình các đợt 4-9
            milestone_configs = [
                {'type': 'dot_4', 'months': 2, 'share': 0.05, 'vat_share': 0.05, 'bank_share': 0.3, 'bank_vat_share': 0.3, 'bank_note': 'NGÂN HÀN 30% ÂN HẠN GỐC, LÃI XUẤT ƯU ĐÃI'},
                {'type': 'dot_5', 'months': 4, 'share': 0.05, 'vat_share': 0.05, 'bank_share': 0, 'bank_vat_share': 0, 'bank_note': 'NGÂN HÀN 30% ÂN HẠN GỐC, LÃI XUẤT ƯU ĐÃI'},
                {'type': 'dot_6', 'months': 6, 'share': 0.05, 'vat_share': 0.05, 'bank_share': 0, 'bank_vat_share': 0, 'bank_note': 'NGÂN HÀN 30% ÂN HẠN GỐC, LÃI XUẤT ƯU ĐÃI'},
                {'type': 'dot_7', 'months': 9, 'share': 0.05, 'vat_share': 0.05, 'bank_share': 0, 'bank_vat_share': 0, 'bank_note': 'NGÂN HÀN 30% ÂN HẠN GỐC, LÃI XUẤT ƯU ĐÃI'},
                {'type': 'dot_8', 'months': 12, 'share': 0.05, 'vat_share': 0.05, 'bank_share': 0, 'bank_vat_share': 0, 'bank_note': 'NGÂN HÀN 30% ÂN HẠN GỐC, LÃI XUẤT ƯU ĐÃI'},
                {'type': 'dot_9', 'months': 15, 'share': 0.05, 'vat_share': 0.05, 'bank_share': 0, 'bank_vat_share': 0, 'bank_note': 'NGÂN HÀN 30% ÂN HẠN GỐC, LÃI XUẤT ƯU ĐÃI'},
            ]
            
            timeline_vals_list = [
                (0, 0, vals_1),
                (0, 0, vals_2),
                (0, 0, vals_3),
            ]
            
            for config in milestone_configs:
                m_date = fixed_deposit_date + relativedelta(months=config['months'])
                m_share = config['share']
                m_amount = currency.round(product.price_include_land_tax * config['share'])
                m_vat = currency.round(product.vat_tax * config['vat_share'])
                m_bank = currency.round(product.price_include_land_tax * config['bank_share'] + product.vat_tax * config['bank_vat_share'])
                
                if m_date < today:
                    # Nếu đợt này đã quá hạn, gom tiền vào biến tích lũy
                    accumulated_amount += m_amount
                    accumulated_share += m_share
                    accumulated_vat += m_vat
                    accumulated_bank += m_bank
                else:
                    # Nếu đợt này ở tương lai, cộng dồn tiền tích lũy vào đây
                    vals_m = {
                        'product_tmpl_id': product.id,
                        'type': config['type'],
                        'date': m_date,
                        'name': f"{((accumulated_share + m_share) * 100):.2f}" + '% +VAT tương ứng',
                        'amount': m_amount + accumulated_amount,
                        'vat_amount': m_vat + accumulated_vat,
                        'bank_amount': m_bank + accumulated_bank,
                        'bank_note': config['bank_note'],
                    }
                    timeline_vals_list.append((0, 0, vals_m))
                    # Reset biến tích lũy sau khi đã gộp
                    accumulated_amount = 0.0
                    accumulated_share = 0.0
                    accumulated_vat = 0.0
                    accumulated_bank = 0.0

            # Xử lý Đợt 10 (Giao nhà) - Nhận phần tiền tích lũy còn lại nếu tất cả 4-9 đều quá hạn
            vals_10 = {
                'product_tmpl_id': product.id,
                'type': 'giao_nha',
                'date': fixed_deposit_date + relativedelta(months=18),
                'name': '45% +VAT còn lại',
                'amount': currency.round(product.price_include_land_tax * 0.45) + accumulated_amount,
                'vat_amount': currency.round(product.vat_tax * 0.50) + accumulated_vat,
                'bank_amount': currency.round(product.price_include_land_tax * 0.35 + product.vat_tax * 0.40) + accumulated_bank,
                'bank_note': 'NGÂN HÀNG 35%',
            }
            timeline_vals_list.append((0, 0, vals_10))

            vals_11 = {
                'product_tmpl_id': product.id,
                'type': 'quy_bao_tri',
                'date': fixed_deposit_date + relativedelta(months=18),
                'name': '0.5%',
                'amount': currency.round(product.maintenance_fee),
                'vat_amount': 0.0,
                'bank_amount': currency.round(product.price_include_land_tax * 0.10 + product.vat_tax * 0.10 + product.maintenance_fee),
                'bank_note': 'KH 10% + QBT',
            }
            timeline_vals_list.append((0, 0, vals_11))

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
            timeline_vals_list.append((0, 0, vals_12))
            # Clear existing timelines
            product.payment_timeline_ids.unlink()
            # Create new timelines
            product.write({
                'payment_timeline_ids': timeline_vals_list
            })


    @api.depends('site_plan_polygon_ids')
    def _compute_site_plan_polygon_id(self):
        for product in self:
            product.site_plan_polygon_id = product.site_plan_polygon_ids[0] if product.site_plan_polygon_ids else False

    @api.depends('site_plan_polygon_ids')
    def _compute_is_real_estate(self):
        for product in self:
            product.is_real_estate = bool(product.site_plan_polygon_ids)
    
    @api.depends('list_price', 'selected_discount_ids', 'selected_discount_ids.discount_type', 'selected_discount_ids.discount_value')
    def _compute_final_price(self):
        for product in self:
            total_discount = 0.0
            for discount in product.selected_discount_ids:
                if discount.discount_type == 'percent':
                    total_discount += (product.list_price * (discount.discount_value / 100.0))
                else:
                    total_discount += discount.discount_value
            product.final_price = product.list_price - total_discount

    @api.depends('categ_id', 'categ_id.real_estate_color')
    def _compute_real_estate_color(self):
        """Auto-fill color from category if not set"""
        for product in self:
            if not product.real_estate_color and product.categ_id and product.categ_id.real_estate_color:
                product.real_estate_color = product.categ_id.real_estate_color
            elif not product.real_estate_color:
                product.real_estate_color = '#3498db'  # Default blue
    
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
            product.price_include_land_tax = product.price_exclude_land_tax + product.land_tax

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