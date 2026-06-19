# -*- coding: utf-8 -*-

from odoo import models, fields, api


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
             'Bỏ trống nghĩa là áp cho mọi danh mục.',
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
