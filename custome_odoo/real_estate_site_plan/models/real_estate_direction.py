# -*- coding: utf-8 -*-

from odoo import models, fields


class RealEstateDirection(models.Model):
    _name = 'real.estate.direction'
    _description = 'Hướng bất động sản'
    _order = 'sequence, name'

    name = fields.Char(
        string='Tên hướng',
        required=True,
        translate=True,
        help='Tên hiển thị của hướng (ví dụ: Bắc, Đông Nam...)',
    )
    code = fields.Char(
        string='Mã hướng',
        required=True,
        help='Mã định danh kỹ thuật, dùng cho migrate và tích hợp.',
    )
    sequence = fields.Integer(
        string='Thứ tự',
        default=10,
        help='Thứ tự hiển thị trong dropdown và danh sách.',
    )
    active = fields.Boolean(
        string='Đang dùng',
        default=True,
    )

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Mã hướng đã tồn tại — vui lòng đặt mã khác.'),
    ]
