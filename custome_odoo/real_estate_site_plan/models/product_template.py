# -*- coding: utf-8 -*-

from odoo import models, fields, api


# ---------------------------------------------------------------------------
# Quy tac gia bat dong san
#
# Chi co 2 truong nhap tay: price_exclude_land_tax va land_tax.
# Moi truong con lai deu suy ra tu day:
#
#   price_include_land_tax = price_exclude_land_tax + land_tax
#   vat_tax                = price_exclude_land_tax x VAT_RATE
#   maintenance_fee        = round(price_include_land_tax x MAINTENANCE_RATE, -3)
#   list_price             = price_include_land_tax + vat_tax + maintenance_fee
#   price_per_m2           = list_price / area
#
# Hai ty le duoi day cung duoc product.discount.config dung lai cho loai chiet
# khau 'percent_recalc' (dung lai thap gia sau khi giam %), nen de o mot cho.
# ---------------------------------------------------------------------------
VAT_RATE = 0.10
MAINTENANCE_RATE = 0.005
MAINTENANCE_ROUNDING = -3  # lam tron quy bao tri ve boi 1.000 dong


def compute_vat_tax(price_exclude_land_tax):
    """VAT = 10% gia nha chua bao gom thue su dung dat."""
    return (price_exclude_land_tax or 0.0) * VAT_RATE


def compute_maintenance_fee(price_include_land_tax):
    """Quy bao tri = 0,5% gia nha da bao gom thue SDD, lam tron toi nghin dong."""
    return round((price_include_land_tax or 0.0) * MAINTENANCE_RATE,
                 MAINTENANCE_ROUNDING)


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

    is_inhouse_cart = fields.Boolean(
        string='Thuộc giỏ hàng Inhouse',
        related='product_variant_id.is_inhouse_cart',
        readonly=False,
        store=True,
        help='Đánh dấu sản phẩm này thuộc giỏ hàng Inhouse trên portal.'
    )

    is_agency_cart = fields.Boolean(
        string='Thuộc giỏ hàng Đại lý',
        related='product_variant_id.is_agency_cart',
        readonly=False,
        store=True,
        help='Đánh dấu sản phẩm này thuộc giỏ hàng Đại lý trên portal.'
    )

    decoration_note = fields.Text(
        string='Mô tả về vật trang trí',
        translate=True,
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
        help='TRƯỜNG NHẬP CHÍNH. VAT, quỹ bảo trì, giá bao gồm TSDĐ và giá niêm yết '
             'đều được tính tự động từ trường này.'
    )

    land_tax = fields.Monetary(
        string='Thuế sử dụng đất',
        currency_field='currency_id',
        help='Nhập tay — thuế SDĐ không suy ra được từ giá nhà (tỷ lệ khác nhau theo lô).'
    )

    vat_tax = fields.Monetary(
        string='Thuế VAT',
        currency_field='currency_id',
        compute='_compute_vat_tax',
        store=True,
        readonly=False,
        help='= 10% x Giá nhà chưa bao gồm thuế SDĐ. Vẫn sửa tay được khi cần, '
             'nhưng sẽ bị tính lại nếu giá nhà chưa TSDĐ thay đổi.'
    )

    maintenance_fee = fields.Monetary(
        string='Quỹ bảo trì',
        currency_field='currency_id',
        compute='_compute_maintenance_fee',
        store=True,
        readonly=False,
        help='= 0,5% x Giá nhà bao gồm thuế SDĐ, làm tròn tới nghìn đồng. '
             'Vẫn sửa tay được, nhưng sẽ bị tính lại khi giá nhà thay đổi.'
    )

    management_fee = fields.Monetary(
        string='Phí quản lý',
        currency_field='currency_id',
    )

    price_include_land_tax = fields.Monetary(
        string='Giá nhà bao gồm thuế SDĐ',
        currency_field='currency_id',
        help='= Giá nhà chưa bao gồm thuế SDĐ + Thuế sử dụng đất (tự động tính).',
        compute='_compute_price_include_land_tax',
        store=True,
    )
    
    deposit = fields.Monetary(
        string='Đặt cọc',
        currency_field='currency_id',
        help='Số tiền đặt cọc',
        default=200000000,
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
    
    direction_id = fields.Many2one(
        comodel_name='real.estate.direction',
        string='Hướng',
        ondelete='restrict',
        help='Hướng của bất động sản (cấu hình tại Bất động sản > Cấu hình > Hướng).'
    )
    deposit_date = fields.Date(
        string='Ngày đặt cọc',
        help='Ngày thực hiện đặt cọc'
    )
    payment_timeline_ids = fields.One2many(
        comodel_name='payment.timeline',
        inverse_name='product_tmpl_id',
        string='Lịch thanh toán',
        help='Lịch thanh toán của sản phẩm — sinh tự động qua compute_payment_timeline '
             'theo bảng cấu hình payment.schedule.template (gán theo product.categ_id).',
    )

    def _find_payment_schedule_template(self):
        """Tìm template lịch thanh toán áp dụng cho sản phẩm này.
        Khớp qua product.categ_id <-> payment.schedule.template.product_category_ids.
        Trả về recordset rỗng nếu không tìm thấy (có nghĩa là sản phẩm thuộc
        category chưa được gán template — không sinh lịch tự động)."""
        self.ensure_one()
        if not self.categ_id:
            return self.env['payment.schedule.template']
        return self.env['payment.schedule.template'].search([
            ('product_category_ids', 'in', self.categ_id.ids),
            ('active', '=', True),
        ], limit=1)

    @api.onchange('deposit_date', 'price_include_land_tax', 'vat_tax', 'categ_id')
    def compute_payment_timeline(self):
        """Sinh lại lịch thanh toán dựa trên payment.schedule.template tương ứng
        với category của sản phẩm. Nếu không có template nào áp cho category này,
        giữ nguyên lịch hiện tại (không xoá, không sinh mới)."""
        for product in self:
            template = product._find_payment_schedule_template()
            if not template:
                continue
            template._generate_timelines_for_product(product)


    @api.depends('site_plan_polygon_ids')
    def _compute_site_plan_polygon_id(self):
        for product in self:
            product.site_plan_polygon_id = product.site_plan_polygon_ids[0] if product.site_plan_polygon_ids else False

    @api.depends('site_plan_polygon_ids')
    def _compute_is_real_estate(self):
        for product in self:
            product.is_real_estate = bool(product.site_plan_polygon_ids)

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
    
    @api.depends('list_price', 'selected_discount_ids', 'selected_discount_ids.discount_type',
                 'selected_discount_ids.discount_value', 'selected_discount_ids.formula_type',
                 'selected_discount_ids.qty',
                 'price_exclude_land_tax', 'land_tax',
                 'management_fee', 'maintenance_fee', 'area')
    def _compute_final_price(self):
        for product in self:
            total_discount = 0.0
            for discount in product.selected_discount_ids:
                # Sử dụng method từ discount model để tính giá trị chiết khấu
                total_discount += discount.compute_discount_for_product(product)
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

    @api.depends('price_exclude_land_tax', 'land_tax')
    def _compute_price_include_land_tax(self):
        for product in self:
            product.price_include_land_tax = (
                product.price_exclude_land_tax + product.land_tax
            )

    @api.depends('price_exclude_land_tax')
    def _compute_vat_tax(self):
        for product in self:
            product.vat_tax = compute_vat_tax(product.price_exclude_land_tax)

    @api.depends('price_include_land_tax')
    def _compute_maintenance_fee(self):
        for product in self:
            product.maintenance_fee = compute_maintenance_fee(
                product.price_include_land_tax
            )

    # ------------------------------------------------------------------
    # Giá niêm yết (list_price)
    #
    # list_price là field gốc của Odoo, dùng cho MỌI sản phẩm chứ không riêng
    # BĐS, nên không chuyển sang compute được — làm vậy sẽ ghi 0 đè lên giá bán
    # của sản phẩm thường. Thay vào đó đồng bộ có điều kiện trong create/write,
    # chỉ chạm tới sản phẩm thực sự có nhập giá BĐS.
    # ------------------------------------------------------------------
    _REAL_ESTATE_PRICE_INPUTS = (
        'price_exclude_land_tax', 'land_tax', 'vat_tax', 'maintenance_fee',
    )

    def _has_real_estate_pricing(self):
        self.ensure_one()
        return bool(self.price_exclude_land_tax or self.land_tax)

    def _get_real_estate_list_price(self):
        self.ensure_one()
        return (
            self.price_include_land_tax + self.vat_tax + self.maintenance_fee
        )

    def _sync_real_estate_list_price(self):
        """Ghi lại list_price = Giá gồm TSDĐ + VAT + Quỹ bảo trì.

        Chỉ ghi khi giá trị thực sự lệch. Lần write lồng bên trong chỉ chứa
        'list_price' — không nằm trong _REAL_ESTATE_PRICE_INPUTS — nên không
        kích hoạt lại hàm này, không có đệ quy.
        """
        for product in self:
            if not product._has_real_estate_pricing():
                continue
            new_price = product._get_real_estate_list_price()
            currency = product.currency_id
            if currency:
                changed = currency.compare_amounts(product.list_price, new_price) != 0
            else:
                changed = product.list_price != new_price
            if changed:
                product.write({'list_price': new_price})

    @api.model_create_multi
    def create(self, vals_list):
        products = super().create(vals_list)
        products._sync_real_estate_list_price()
        return products

    def write(self, vals):
        res = super().write(vals)
        if any(field in vals for field in self._REAL_ESTATE_PRICE_INPUTS):
            self._sync_real_estate_list_price()
        return res

    @api.onchange('price_exclude_land_tax', 'land_tax', 'vat_tax', 'maintenance_fee')
    def _onchange_real_estate_list_price(self):
        """Cập nhật giá niêm yết ngay trên form, trước khi bấm lưu."""
        for product in self:
            if product._has_real_estate_pricing():
                product.list_price = product._get_real_estate_list_price()

    def action_recalculate_prices(self):
        """Tính lại toàn bộ giá theo đúng công thức chuẩn.

        Dùng cho dữ liệu cũ, hoặc khi VAT / quỹ bảo trì đã bị sửa tay và cần
        đưa về lại công thức.
        """
        for product in self:
            product.vat_tax = compute_vat_tax(product.price_exclude_land_tax)
            product.maintenance_fee = compute_maintenance_fee(
                product.price_include_land_tax
            )
        self._sync_real_estate_list_price()

    def get_available_discounts(self):
        """Trả về danh sách các discount config áp dụng được cho sản phẩm này"""
        self.ensure_one()
        # Nếu đã chọn cụ thể thì chỉ lấy những cái đó
        if self.discount_config_ids:
            return self.discount_config_ids
        
        # Nếu không chọn cụ thể, lấy tất cả active configs và lọc theo danh mục
        active_discounts = self.env['product.discount.config'].search([('active', '=', True)])
        # Filter in Python
        return active_discounts.filtered(lambda d: d.check_eligibility(self))
