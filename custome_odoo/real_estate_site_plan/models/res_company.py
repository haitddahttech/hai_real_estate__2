# -*- coding: utf-8 -*-

from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Bank account information
    bank_account_ids = fields.One2many(
        'res.company.bank',
        'company_id',
        string='Tài khoản ngân hàng'
    )
    
    # Customer greeting message for PDF/Image footer
    customer_greeting = fields.Text(
        string='Câu chúc khách hàng',
        help='Dòng chữ sẽ hiển thị ở cuối PDF và ảnh tải xuống',
        default='Cảm ơn Quý khách đã quan tâm đến dự án của chúng tôi!'
    )

    nearby_day = fields.Float(
        string='Số ngày gộp đợt',
        default=0,
        help='Nếu khoảng cách giữa ngày Ký HĐ và đợt thanh toán gần nhất nhỏ hơn số ngày này, '
             'hệ thống sẽ tự động gộp đợt đó vào đợt tiếp theo. Mặc định 0 = không gộp.'
    )
