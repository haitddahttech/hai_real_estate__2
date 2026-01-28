# -*- coding: utf-8 -*-

from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Bank account information
    # Bank account information
    bank_account_ids = fields.One2many(
        'res.company.bank',
        'company_id',
        string='Tài khoản ngân hàng'
    )
