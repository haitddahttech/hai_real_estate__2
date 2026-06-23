# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class PaymentScheduleTemplate(models.Model):
    _name = 'payment.schedule.template'
    _description = 'Mẫu lịch thanh toán'
    _order = 'sequence, name'

    name = fields.Char(
        string='Tên lịch thanh toán',
        required=True,
        translate=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    product_category_ids = fields.Many2many(
        comodel_name='product.category',
        relation='payment_schedule_template_categ_rel',
        column1='template_id',
        column2='category_id',
        string='Danh mục sản phẩm áp dụng',
        help='Mẫu lịch này sẽ áp cho các sản phẩm thuộc các danh mục được chọn. '
             'Để trống nghĩa là KHÔNG áp cho danh mục nào.',
    )
    line_ids = fields.One2many(
        comodel_name='payment.schedule.template.line',
        inverse_name='template_id',
        string='Đợt thanh toán',
        copy=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        readonly=True,
    )
    total_percentage = fields.Float(
        string='Tổng % cấu hình',
        compute='_compute_totals',
        help='Tổng % của các dòng cấu hình theo % giá trị BĐS. Lý tưởng bằng 100%.',
    )
    line_count = fields.Integer(
        string='Số đợt',
        compute='_compute_totals',
    )

    @api.depends('line_ids.amount_type', 'line_ids.percentage')
    def _compute_totals(self):
        for tpl in self:
            tpl.line_count = len(tpl.line_ids)
            tpl.total_percentage = sum(
                l.percentage for l in tpl.line_ids if l.amount_type == 'percentage'
            )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('product_category_ids')
    def _check_category_uniqueness(self):
        """Mỗi product.category chỉ được nằm trong 1 lịch thanh toán duy nhất."""
        for tpl in self:
            if not tpl.product_category_ids:
                continue
            others = self.search([
                ('id', '!=', tpl.id),
                ('product_category_ids', 'in', tpl.product_category_ids.ids),
            ])
            for other in others:
                conflicts = tpl.product_category_ids & other.product_category_ids
                if conflicts:
                    raise ValidationError(_(
                        "Danh mục \"%(cat)s\" đã được dùng trong lịch thanh toán \"%(tpl)s\". "
                        "Mỗi danh mục chỉ được nằm trong 1 lịch thanh toán."
                    ) % {
                        'cat': conflicts[0].display_name,
                        'tpl': other.display_name,
                    })

    # ------------------------------------------------------------------
    # Action button: regenerate timelines for all products in categories
    # ------------------------------------------------------------------
    def action_regenerate_timelines(self):
        """Cập nhật lịch thanh toán mới cho tất cả product.template thuộc
        các product.category đã chọn của template này."""
        self.ensure_one()
        if not self.product_category_ids:
            raise UserError(_(
                "Template chưa chọn danh mục sản phẩm nào. "
                "Vui lòng chọn danh mục trước khi cập nhật."
            ))
        if not self.line_ids:
            raise UserError(_("Template chưa có dòng đợt thanh toán nào."))

        products = self.env['product.template'].search([
            ('categ_id', 'child_of', self.product_category_ids.ids),
        ])
        if not products:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Không có sản phẩm"),
                    'message': _("Không tìm thấy sản phẩm nào trong danh mục đã chọn."),
                    'type': 'warning',
                    'sticky': False,
                },
            }

        for product in products:
            self._generate_timelines_for_product(product)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Cập nhật thành công"),
                'message': _("Đã cập nhật lịch thanh toán cho %s sản phẩm.") % len(products),
                'type': 'success',
                'sticky': False,
            },
        }

    def _generate_timelines_for_product(self, product):
        """Sinh lại payment_timeline_ids cho 1 product.template dựa trên line_ids
        của template hiện tại. Áp dụng logic gộp (is_mergeable) tương tự
        compute_payment_timeline cũ, nhưng đọc cấu hình từ template.

        Special-case theo `code` để giữ tương thích nghiệp vụ cũ:
        - dat_coc + fixed_amount=0    -> dùng product.deposit
        - trong_3_ngay (%)            -> trừ tiền product.deposit (5% trừ cọc)
        - ky_hop_dong (%)             -> trừ paid_amount tích lũy (bù cho đủ %)
        - quy_bao_tri + fixed=0       -> dùng product.maintenance_fee
        - quy_bao_tri                 -> bank cộng thêm maintenance_fee
        """
        self.ensure_one()
        currency = self.env.company.currency_id
        company = self.env.company

        deposit_date = product.deposit_date or fields.Date.today()
        if product.site_plan_polygon_ids:
            fixed_anchor = (
                product.site_plan_polygon_ids[0].site_plan_id.deposit_date
                or deposit_date
            )
        else:
            fixed_anchor = deposit_date

        # Marker = NGÀY HIỆN TẠI (không phải ngày ký HĐ giả tạo như logic cũ).
        # Một đợt bị gộp khi line_date < today, hoặc khoảng cách < nearby_day.
        today_marker = fields.Date.today()
        nearby_day = company.nearby_day or 0

        early_codes = ('dat_coc', 'trong_3_ngay', 'ky_hop_dong')

        paid_amount = 0.0
        acc_amount = acc_vat = acc_bank = 0.0
        acc_share = 0.0  # % tích lũy cho mô tả "X% +VAT tương ứng"
        vals_list = []

        for line in self.line_ids.sorted('sequence'):
            line_share = (line.percentage or 0.0) if line.amount_type == 'percentage' else 0.0
            # ---- DATE ----
            if line.date_type == 'fixed':
                line_date = line.fixed_date
            elif line.date_type == 'no_date':
                line_date = False
            else:
                base = deposit_date if line.code in early_codes else fixed_anchor
                line_date = base + relativedelta(
                    months=line.offset_months or 0,
                    days=line.offset_days or 0,
                )

            # ---- AMOUNT (giá nhà) ----
            if line.amount_type == 'fixed':
                amount = line.fixed_amount or 0.0
                if not amount and line.code == 'dat_coc':
                    amount = product.deposit or 0.0
                elif not amount and line.code == 'quy_bao_tri':
                    amount = product.maintenance_fee or 0.0
            else:
                amount = currency.round(
                    product.price_include_land_tax * (line.percentage or 0.0) / 100.0
                )
                if line.code == 'trong_3_ngay':
                    amount = amount - (product.deposit or 0.0)
                elif line.code == 'ky_hop_dong':
                    amount = amount - paid_amount

            paid_amount += amount

            # ---- VAT ----
            vat_amount = currency.round(
                product.vat_tax * (line.vat_share or 0.0) / 100.0
            ) if line.vat_share else 0.0

            # ---- BANK ----
            bank_amount = currency.round(
                product.price_include_land_tax * (line.bank_share or 0.0) / 100.0
                + product.vat_tax * (line.bank_vat_share or 0.0) / 100.0
            )
            if line.code == 'quy_bao_tri':
                bank_amount += product.maintenance_fee or 0.0

            # ---- MERGE (gộp dữ liệu theo ngày) ----
            if line.is_mergeable and line.is_merge_by_date and line_date:
                days_gap = (line_date - today_marker).days
                if line_date < today_marker or (nearby_day > 0 and days_gap < nearby_day):
                    acc_amount += amount
                    acc_vat += vat_amount
                    acc_bank += bank_amount
                    acc_share += line_share
                    continue  # khong tao record cho dot nay, gop vao dot ke

            # ---- NAME (mô tả "Số tiền thanh toán") ----
            # Cột này hiển thị HOW MUCH ("5%", "Đủ 20% +VAT"...), KHÔNG phải tên đợt.
            if line.amount_type == 'fixed':
                name_str = line.name  # Fixed amount: dùng tên đợt làm mô tả
            elif line.code == 'ky_hop_dong':
                name_str = "Đủ %g%% +VAT" % (line.percentage or 0)
            elif line.code == 'giao_nha':
                name_str = "%g%% +VAT còn lại" % (line.percentage or 0)
            elif line.code == 'quy_bao_tri':
                name_str = "%g%%" % (line.percentage or 0.5)
            elif line.is_mergeable:
                # Đợt mergeable: hiển thị cumulative % (gồm tích lũy nếu vừa drain merge)
                name_str = "%.2f%% +VAT tương ứng" % (acc_share + line_share)
            else:
                name_str = "%g%%" % (line.percentage or 0)

            # ---- CREATE record (cộng dồn tích lũy nếu có) ----
            vals_list.append((0, 0, {
                'product_tmpl_id': product.id,
                'type': line.code or '',
                'type_name': line.name or '',
                'date': line_date,
                'name': name_str,
                'amount': amount + acc_amount,
                'vat_amount': vat_amount + acc_vat,
                'bank_amount': bank_amount + acc_bank,
                'bank_note': line.note or '',
                'bank_group': line.group_merge or '' if line.is_mergeable else '',
                'is_merge_title': line.is_merge_title if line.is_mergeable else False,
            }))
            acc_amount = acc_vat = acc_bank = 0.0
            acc_share = 0.0

        # Nếu vẫn còn tích lũy (toàn bộ trailing lines đều mergeable + quá hạn)
        # thì dồn vào dòng cuối cùng đã tạo
        if vals_list and (acc_amount or acc_vat or acc_bank):
            last_vals = vals_list[-1][2]
            last_vals['amount'] += acc_amount
            last_vals['vat_amount'] += acc_vat
            last_vals['bank_amount'] += acc_bank

        # Wipe & recreate
        product.payment_timeline_ids.unlink()
        product.write({'payment_timeline_ids': vals_list})


class PaymentScheduleTemplateLine(models.Model):
    _name = 'payment.schedule.template.line'
    _description = 'Đợt trong mẫu lịch thanh toán'
    _order = 'template_id, sequence, id'

    template_id = fields.Many2one(
        comodel_name='payment.schedule.template',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(
        string='Tên kỳ thanh toán',
        required=True,
        translate=True,
        help='Ví dụ: Đặt cọc, Đợt 4, Giao nhà...',
    )
    code = fields.Char(
        string='Mã',
        help='Mã định danh kỹ thuật (vd: dat_coc, dot_4). Tuỳ chọn — dùng cho tích hợp.',
    )

    # --- Ngày thanh toán ---
    date_type = fields.Selection(
        selection=[
            ('offset', 'Số tháng/ngày kể từ ngày đặt cọc'),
            ('fixed', 'Ngày cố định'),
            ('no_date', 'Không xác định'),
        ],
        string='Loại ngày',
        default='offset',
        required=True,
    )
    offset_months = fields.Integer(string='Số tháng', default=0)
    offset_days = fields.Integer(string='Số ngày', default=0)
    fixed_date = fields.Date(string='Ngày cố định')

    # --- Số tiền ---
    amount_type = fields.Selection(
        selection=[
            ('percentage', '% giá trị BĐS'),
            ('fixed', 'Số tiền cố định'),
        ],
        string='Loại số tiền',
        default='percentage',
        required=True,
    )
    percentage = fields.Float(
        string='% giá trị',
        digits=(7, 4),
        help='Nhập 5 nghĩa là 5%. Chỉ dùng khi "Loại số tiền" = %.',
    )
    fixed_amount = fields.Monetary(
        string='Số tiền',
        currency_field='currency_id',
        help='Số tiền cố định. Chỉ dùng khi "Loại số tiền" = cố định.',
    )
    vat_share = fields.Float(
        string='% VAT',
        digits=(7, 4),
        help='Phần trăm VAT khách trả cho đợt này. '
             'Vd Giao nhà có thể là 50% mặc dù giá nhà chỉ 45%.',
    )
    bank_share = fields.Float(
        string='% NH (giá nhà)',
        digits=(7, 4),
        help='Phần trăm giá nhà được ngân hàng hỗ trợ ở đợt này. '
             'Cộng vào "Tiền ngân hàng hỗ trợ" trên dòng lịch.',
    )
    bank_vat_share = fields.Float(
        string='% NH (VAT)',
        digits=(7, 4),
        help='Phần trăm VAT được ngân hàng hỗ trợ ở đợt này.',
    )
    currency_id = fields.Many2one(
        related='template_id.currency_id',
        readonly=True,
    )

    # --- Flags hành vi ---
    is_mergeable = fields.Boolean(
        string='Cho phép gộp đợt',
        default=True,
        help='Khi đến lúc sinh lịch, nếu đợt này đã quá hạn hoặc gần ngày ký HĐ '
             '(theo cấu hình "nearby_day" của công ty) thì gộp tiền vào đợt kế tiếp.',
    )
    group_merge = fields.Selection(
        selection=[
            ('1', 'Nhóm 1'),
            ('2', 'Nhóm 2'),
            ('3', 'Nhóm 3'),
            ('4', 'Nhóm 4'),
            ('5', 'Nhóm 5'),
        ],
        string='Nhóm gộp NH',
        help='Các đợt cùng nhóm sẽ được gộp cột "Hỗ trợ ngân hàng" trên bảng lịch thanh toán. '
             'Chỉ áp dụng khi "Cho phép gộp đợt" được bật.',
    )
    is_merge_by_date = fields.Boolean(
        string='Gộp theo ngày TT',
        default=True,
        help='Khi bật, nếu ngày thanh toán đã quá hạn hoặc gần ngày ký HĐ '
             '(theo cấu hình "nearby_day") thì gộp tiền vào đợt kế tiếp.\n'
             'Tắt để giữ nguyên từng dòng (chỉ gộp cột ngân hàng nếu cùng nhóm).',
    )
    is_merge_title = fields.Boolean(
        string='Gộp tiêu đề',
        default=False,
        help='Mặc định chỉ gộp 2 cột con của "Hỗ trợ ngân hàng". '
             'Bật để gộp toàn bộ dòng thành 1 hàng.',
    )
    note = fields.Char(
        string='Ghi chú',
        translate=True,
        help='Vd: "KH 20%", "NGÂN HÀNG 35%"...',
    )

    @api.onchange('date_type')
    def _onchange_date_type(self):
        if self.date_type != 'offset':
            self.offset_months = 0
            self.offset_days = 0
        if self.date_type != 'fixed':
            self.fixed_date = False

    @api.onchange('amount_type')
    def _onchange_amount_type(self):
        if self.amount_type != 'percentage':
            self.percentage = 0.0
        if self.amount_type != 'fixed':
            self.fixed_amount = 0.0
