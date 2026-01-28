# -*- coding: utf-8 -*-

from odoo import models, fields


class ResCompanyBank(models.Model):
    _name = 'res.company.bank'
    _description = 'Company Bank Account'

    company_id = fields.Many2one(
        'res.company',
        string='Công ty',
        required=True,
        ondelete='cascade',
        default=lambda self: self.env.company
    )
    
    bank_name = fields.Char(
        string='Ngân hàng',
        required=True,
        help='Tên ngân hàng'
    )
    
    bank_account_holder_name = fields.Char(
        string='Tên chủ tài khoản',
        required=True,
        help='Tên chủ tài khoản ngân hàng'
    )
    
    bank_account_number = fields.Char(
        string='Số tài khoản',
        required=True,
        help='Số tài khoản ngân hàng'
    )
    
    swift_code = fields.Char(
        string='SWIFT Code',
        help='Mã SWIFT của ngân hàng'
    )
    
    payment_qr_code = fields.Binary(
        string='QR Chuyển khoản',
        help='Hình ảnh mã QR để khách hàng quét chuyển khoản'
    )
    
    sequence = fields.Integer(
        string='Thứ tự',
        default=10
    )
    
    active = fields.Boolean(
        string='Đang hoạt động',
        default=True
    )
