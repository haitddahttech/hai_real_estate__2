# -*- coding: utf-8 -*-

from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Bank account information
    bank_account_holder_name = fields.Char(
        string='Tên chủ tài khoản',
        help='Tên chủ tài khoản ngân hàng của công ty'
    )
    
    bank_name = fields.Char(
        string='Ngân hàng',
        help='Tên ngân hàng'
    )
    
    bank_account_number = fields.Char(
        string='Số tài khoản',
        help='Số tài khoản ngân hàng của công ty'
    )
