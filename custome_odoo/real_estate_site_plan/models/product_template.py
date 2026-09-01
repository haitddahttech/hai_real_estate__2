# -*- coding: utf-8 -*-

from odoo import models, fields, api


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
        help='Đánh dấu biến thể này thuộc giỏ hàng Inhouse trên portal.'
    )

    is_agency_cart = fields.Boolean(
        string='Thuộc giỏ hàng Đại lý',
        help='Đánh dấu biến thể này thuộc giỏ hàng Đại lý trên portal.'
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
        help='Giá sau khi trừ các khoản giảm giá đã lưu trên sản phẩm '
             '(mặc định bằng giá niêm yết).\n'
             'KHÔNG lưu vào DB: chiết khấu là mô phỏng lúc xem, giá hiển thị '
             'trên portal và mẫu in được tính lại từ lựa chọn của người xem '
             '(xem get_display_prices).'
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

    def _get_schedule_discount_context(self, discounts=None):
        """Giá & tiền chiết khấu dùng để dựng lịch thanh toán của sản phẩm này.

        `discounts` là recordset product.discount.config cần áp; để None thì lấy
        chiết khấu đã lưu trên sản phẩm. Truyền tay vào để portal/mẫu in dựng
        được lịch theo lựa chọn của NGƯỜI ĐANG XEM mà không phải ghi lựa chọn đó
        lên sản phẩm.

        Xem product.discount.config.get_schedule_discount_context()."""
        self.ensure_one()
        if discounts is None:
            discounts = self.selected_discount_ids
        return discounts.get_schedule_discount_context(self)

    @api.onchange('deposit_date', 'price_include_land_tax', 'vat_tax', 'categ_id',
                  'selected_discount_ids')
    def compute_payment_timeline(self):
        """Sinh lại lịch thanh toán dựa trên payment.schedule.template tương ứng
        với category của sản phẩm. Nếu không có template nào áp cho category này,
        giữ nguyên lịch hiện tại (không xoá, không sinh mới)."""
        for product in self:
            template = product._find_payment_schedule_template()
            if not template:
                continue
            template._generate_timelines_for_product(product)

    def refresh_payment_timeline_dates(self):
        """Làm mới NGÀY của lịch thanh toán GỐC đang lưu trong DB.

        Sản phẩm chưa gán ngày đặt cọc thì lịch được neo tạm theo ngày hôm nay,
        nên số liệu lưu trong DB cũ dần. Hàm này sinh lại cho đúng ngày hiện tại.
        Sản phẩm ĐÃ có deposit_date thì không đụng tới: lịch của nó đã cố định.

        KHÔNG dùng cho portal hay mẫu in nữa: hai nơi đó gọi
        get_display_timelines(), vốn dựng lịch mới trong bộ nhớ ở mỗi lần render
        nên luôn đúng ngày mà không phải ghi gì xuống DB. Giữ lại cho màn hình
        backend / thao tác thủ công của nhân viên.
        """
        today = fields.Date.today()
        for product in self:
            if product.deposit_date:
                continue
            template = product._find_payment_schedule_template()
            if not template:
                continue
            rows = product.payment_timeline_ids
            # Đã sinh trong hôm nay rồi thì thôi, tránh unlink/create lại trên
            # mỗi request. rows rỗng cũng rơi vào đây để sinh lịch lần đầu.
            if rows and all(r.write_date and r.write_date.date() == today for r in rows):
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
                 'selected_discount_ids.qty', 'selected_discount_ids.sequence',
                 'selected_discount_ids.apply_stage',
                 'price_exclude_land_tax', 'land_tax',
                 'management_fee', 'maintenance_fee', 'area')
    def _compute_final_price(self):
        for product in self:
            # Chiết khấu loại percent_recalc cộng gộp % trong cùng mốc rồi
            # nhân chuỗi giữa các mốc A -> B -> C, nên không cộng dồn từng cái
            # được — phải tính cả nhóm một lượt.
            total_discount, _ = product.selected_discount_ids.compute_discounts_for_product(product)
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
            product.price_include_land_tax = product.price_exclude_land_tax + product.land_tax
        self.compute_list_price()

    # @api.depends('price_include_land_tax')
    # def _inverse_price_exclude_land_tax(self):
    #     for product in self:
    #         product.sudo().write({
    #             'price_exclude_land_tax':product.price_include_land_tax - product.land_tax
    #         })

    @api.depends('price_include_land_tax', 'vat_tax', 'maintenance_fee')
    def compute_list_price(self):
        for product in self:
            product.list_price = product.price_include_land_tax + product.vat_tax + product.maintenance_fee

    def action_recalculate_prices(self):
        """Action to manually recalculate prices (land tax, list price, avg price) for selected products"""
        for product in self:
            # Recompute price include land tax
            product.price_include_land_tax = product.price_exclude_land_tax + product.land_tax
            # Recompute list price
            product.list_price = product.price_include_land_tax + product.vat_tax + product.maintenance_fee
            # Recompute avg price per m2
            if product.area and product.area > 0:
                product.price_per_m2 = product.list_price / product.area
            else:
                product.price_per_m2 = 0.0

    def get_available_bank_accounts(self):
        """Tài khoản ngân hàng được phép hiển thị cho sản phẩm này.

        Dùng chung cho màn portal chi tiết sản phẩm và template PDF/ảnh.
        - Tài khoản KHÔNG chọn danh mục -> hiện ở mọi sản phẩm.
        - Tài khoản CÓ chọn danh mục    -> chỉ hiện nếu danh mục của sản phẩm
                                            nằm trong danh sách đã chọn.
        """
        self.ensure_one()
        banks = self.env.company.sudo().bank_account_ids.filtered(lambda b: b.active)
        categ = self.categ_id
        return banks.filtered(
            lambda b: not b.product_category_ids or categ in b.product_category_ids
        )

    def get_selected_bank_account(self, bank_id=None):
        """Tài khoản ngân hàng ĐANG HIỂN THỊ cho sản phẩm này.

        Portal bày các tài khoản thành tab và mở tab đầu tiên; nút tải PDF/ảnh
        đính kèm id của tab đang mở. Template in phải bám đúng quy tắc đó, nếu
        không PDF sẽ in ngân hàng khác với cái khách đang xem — nên cả hai bên
        dùng chung hàm này.

        bank_id không hợp lệ (rỗng, đã tắt, không thuộc danh mục sản phẩm) thì
        rơi về tài khoản đầu tiên, đúng bằng tab mặc định của portal.
        """
        self.ensure_one()
        accounts = self.get_available_bank_accounts()
        if bank_id is None:
            # Template PDF/ảnh không truyền tay: controller đã nhét id vào context
            bank_id = self.env.context.get('selected_bank_id')
        if bank_id:
            match = accounts.filtered(lambda b: b.id == int(bank_id))
            if match:
                return match[:1]
        return accounts[:1]

    # ------------------------------------------------------------------
    # Chiết khấu là MÔ PHỎNG LÚC XEM, không phải trạng thái của sản phẩm
    # ------------------------------------------------------------------
    # Ba hàm dưới đây dựng giá và lịch thanh toán theo đúng những chiết khấu mà
    # NGƯỜI ĐANG XEM tích trên portal (hoặc đính trong link tải PDF/ảnh), rồi
    # trả về cho template hiển thị. Không hàm nào ghi xuống DB.
    #
    # Nhờ vậy hai người cùng mở một căn không ghi đè lựa chọn của nhau, và bản
    # ghi sản phẩm không bao giờ mang số của một lần tích thử chiết khấu.

    def _resolve_display_discounts(self, discount_ids):
        """Lọc `discount_ids` (list id thô từ trình duyệt) xuống những chiết khấu
        THẬT SỰ áp được cho sản phẩm này.

        Bắt buộc lọc: id đến từ client nên không tin được — thiếu bước này thì
        bất kỳ ai cũng dựng được bảng giá với chương trình chiết khấu không dành
        cho căn đó. get_available_discounts() đã lo phần danh mục và cấu hình.
        """
        self.ensure_one()
        Discount = self.env['product.discount.config']
        if discount_ids is None:
            # Mẫu in PDF/ảnh không truyền tay được: controller nhét danh sách
            # vào context trước khi render.
            discount_ids = self.env.context.get('display_discount_ids')
        if not discount_ids:
            return Discount
        try:
            wanted = {int(d) for d in discount_ids}
        except (TypeError, ValueError):
            return Discount
        return self.get_available_discounts().filtered(lambda d: d.id in wanted)

    def get_display_prices(self, discount_ids=None):
        """Giá hiển thị theo các chiết khấu người xem đang tích.

        Trả về dict: discounts, total_discount, final_price, price_per_m2,
        amounts ({discount_id: tiền giảm của dòng đó}).
        """
        self.ensure_one()
        discounts = self._resolve_display_discounts(discount_ids)
        total_discount, per_discount = discounts.compute_discounts_for_product(self)
        final_price = (self.list_price or 0.0) - total_discount
        return {
            'discounts': discounts,
            'total_discount': total_discount,
            'final_price': final_price,
            'price_per_m2': (final_price / self.area) if self.area else 0.0,
            'amounts': per_discount,
        }

    # Hai chế độ xem lịch thanh toán. Người xem tự chọn trên portal; lựa chọn đó
    # đi kèm link tải nên PDF/ảnh in ra đúng bảng đang xem trên màn hình.
    SCHEDULE_MODE_ORIGINAL = 'original'      # lịch gốc, chưa trừ chiết khấu nào
    SCHEDULE_MODE_DISCOUNTED = 'discounted'  # lịch đã trừ chiết khấu đang tích

    def _resolve_schedule_discounts(self, discount_ids=None, schedule_mode=None):
        """Chiết khấu dùng để dựng BẢNG LỊCH THANH TOÁN.

        Khác với khối giá: người xem có thể đang tích chiết khấu để xem giá,
        nhưng vẫn muốn nhìn lịch GỐC. Chế độ 'original' trả về recordset rỗng
        nên lịch dựng ra không bị trừ đồng nào.
        """
        self.ensure_one()
        if schedule_mode is None:
            # Mẫu in PDF/ảnh không truyền tay được: controller nhét vào context.
            schedule_mode = self.env.context.get('display_schedule_mode')
        if schedule_mode == self.SCHEDULE_MODE_ORIGINAL:
            return self.env['product.discount.config']
        return self._resolve_display_discounts(discount_ids)

    def get_display_timelines(self, discount_ids=None, schedule_mode=None):
        """Lịch thanh toán hiển thị, đã trừ chiết khấu người xem đang tích.

        `schedule_mode='original'` thì dựng lịch GỐC, bỏ qua mọi chiết khấu.

        Trả về recordset payment.timeline ẢO (`.new()`) — chỉ tồn tại trong bộ
        nhớ, không có bản ghi nào được tạo. Dùng `.new()` thay vì list dict để
        template QWeb vẫn truy cập `.amount`, `.type_name`,
        `.get_bank_split_blocks()`... y như với bản ghi thật.

        Không có mẫu lịch cho danh mục của sản phẩm thì trả về lịch GỐC đang lưu
        (nếu có), để trang không trống trơn.
        """
        self.ensure_one()
        Timeline = self.env['payment.timeline']
        template = self._find_payment_schedule_template()
        if not template:
            return self.payment_timeline_ids
        discounts = self._resolve_schedule_discounts(discount_ids, schedule_mode)
        vals_list = template._build_timeline_vals(self, discounts)
        if not vals_list:
            return Timeline
        # concat (không phải union) để giữ nguyên thứ tự đợt và không gộp trùng
        return Timeline.concat(*[Timeline.new(vals) for vals in vals_list])

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
