# -*- coding: utf-8 -*-

import json

from odoo import models, fields, api


class PaymentTimeline(models.Model):
    _name = 'payment.timeline'

    product_tmpl_id = fields.Many2one(
        comodel_name='product.template',
        string='Product Template',
        required=True,
        ondelete='cascade',
        help='The product template associated with this payment timeline'
    )
    type = fields.Selection(
        selection=[
            ('dat_coc', 'Đặt cọc'),
            ('trong_3_ngay', 'Trong 3 ngày'),
            ('ky_hop_dong', 'Ký Hợp Đồng'),
            ('dot_4', 'Đợt 4'),
            ('dot_5', 'Đợt 5'),
            ('dot_6', 'Đợt 6'),
            ('dot_7', 'Đợt 7'),
            ('dot_8', 'Đợt 8'),
            ('dot_9', 'Đợt 9'),
            ('dot_10', 'Đợt 10'),
            ('dot_11', 'Đợt 11'),
            ('dot_12', 'Đợt 12'),
            ('dot_13', 'Đợt 13'),
            ('dot_14', 'Đợt 14'),
            ('dot_15', 'Đợt 15'),
            ('giao_nha', 'Giao nhà'),
            ('quy_bao_tri', 'Quỹ bảo trì'),
            ('thong_bao_so_hong', 'Thông báo sổ hồng'),
        ],
        string='Kỳ thanh toán',
        required=True,
    )
    type_name = fields.Char(
        string='Tên kỳ thanh toán',
        translate=True,
        help='Tên hiển thị của kỳ thanh toán, lấy từ mẫu lịch thanh toán.',
    )
    date = fields.Date(
        string='Ngày thanh toán',
        help='The date for this payment milestone'
    )
    name = fields.Char(
        string='Số tiền thanh toán',
        required=True,
        help='The name or description of this payment milestone'
    )
    amount = fields.Monetary(
        string='Tiền nhà',
        currency_field='currency_id',
        help='The amount to be paid at this milestone'
    )
    vat_amount = fields.Monetary(
        string='VAT',
        currency_field='currency_id',
        help='The VAT amount for this payment milestone'
    )
    total_amount = fields.Monetary(
        string='Tổng tiền (bao gồm VAT)',
        currency_field='currency_id',
        help='The total amount including VAT for this payment milestone',
        compute='_compute_total_amount',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    discount_amount = fields.Monetary(
        string='Chiết khấu trừ vào đợt',
        currency_field='currency_id',
        help='Phần tiền chiết khấu (chỉ tính trên giá nhà chưa thuế SDĐ) đã được '
             'trừ khỏi cột "Tiền nhà" của đợt này. Chỉ để tra soát, cột Tiền nhà '
             'hiển thị số đã trừ rồi.',
    )
    bank_amount = fields.Monetary(
        string='Tiền ngân hàng hỗ trợ',
        currency_field='currency_id',
    )
    bank_note = fields.Char(
        string='Ghi chú ngân hàng',
    )
    bank_group = fields.Char(
        string='Nhóm ngân hàng',
        help='Dùng để gộp rowspan cột "Hỗ trợ ngân hàng" trên bảng lịch thanh toán.',
    )
    is_merge_title = fields.Boolean(
        string='Gộp tiêu đề',
        default=False,
    )

    # --- Chia ô "Hỗ trợ ngân hàng" thành nhiều khối ---
    # Sinh ra từ payment.schedule.template.line.bank_split_ratio, xem
    # PaymentScheduleTemplate._apply_bank_splits.
    bank_split_json = fields.Text(
        string='Các khối ô ngân hàng',
        help='JSON các khối của ô "Hỗ trợ ngân hàng": '
             '[{"amount": 0.0, "label": "..."}, ...]. '
             'Rỗng = ô hiển thị bình thường theo bank_amount.',
    )
    bank_split_size = fields.Integer(
        string='Số hàng ô gộp phủ',
        default=0,
        help='rowspan của ô "Hỗ trợ ngân hàng" khi đợt này có chia khối.',
    )
    bank_split_covered = fields.Boolean(
        string='Ô NH bị phủ',
        default=False,
        help='Hàng này nằm dưới ô gộp của một hàng phía trên nên không render '
             'ô "Hỗ trợ ngân hàng" riêng.',
    )

    def get_bank_split_blocks(self):
        """Danh sách khối của ô "Hỗ trợ ngân hàng", dùng trực tiếp trong QWeb.

        Trả về [] nếu đợt này không chia ô (hoặc dữ liệu hỏng) để template chỉ
        cần một phép kiểm tra duy nhất.
        """
        self.ensure_one()
        if not self.bank_split_json:
            return []
        try:
            blocks = json.loads(self.bank_split_json)
        except (ValueError, TypeError):
            return []
        return blocks if isinstance(blocks, list) else []

    @api.depends('amount', 'vat_amount')
    @api.onchange('amount', 'vat_amount')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = (record.amount or 0) + (record.vat_amount or 0)