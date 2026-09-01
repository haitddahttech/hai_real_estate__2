# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductCategory(models.Model):
    _inherit = 'product.category'
    _order = "sequence, id"

    real_estate_color = fields.Char(
        string='Màu sắc',
        default='#3498db',
        help='Mã màu Hex cho các sản phẩm trong danh mục này (ví dụ: #3498db)'
    )
    sequence = fields.Integer(required=True, default=10)

    booklet_attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        string='Booklet',
        compute='_compute_booklet_attachment_ids',
        inverse='_inverse_booklet_attachment_ids',
        help='Tài liệu booklet dùng chung cho MỌI sản phẩm thuộc danh mục này. '
             'Hiển thị ở tab "BOOKLET" trên trang chi tiết sản phẩm của portal.',
    )

    def get_booklet_attachments(self):
        """Booklet của danh mục = các tệp đính kèm của chính bản ghi danh mục này.

        res_field = False là bắt buộc: các trường Binary(attachment=True) của
        model cũng nằm trong ir.attachment nhưng có res_field, không phải booklet.

        Dùng sudo() vì khách trên portal không có quyền đọc ir.attachment của
        danh mục — họ chỉ được xem, không sửa.
        """
        self.ensure_one()
        # Danh mục mới chưa lưu thì chưa thể có tệp nào.
        categ_id = self._origin.id
        if not categ_id:
            return self.env['ir.attachment']
        return self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'product.category'),
            ('res_id', '=', categ_id),
            ('res_field', '=', False),
        ], order='id')

    def _compute_booklet_attachment_ids(self):
        for category in self:
            category.booklet_attachment_ids = category.get_booklet_attachments()

    def _inverse_booklet_attachment_ids(self):
        """Nguồn dữ liệu duy nhất là res_model/res_id của ir.attachment, không
        phải bảng quan hệ — nhờ vậy portal và ô nhập trên form luôn thấy cùng
        một danh sách."""
        for category in self:
            stored = category.get_booklet_attachments()
            kept = category.booklet_attachment_ids
            # Tệp vừa tải lên khi danh mục còn mới có res_id = 0: gắn lại cho đúng.
            to_link = kept - stored
            if to_link:
                to_link.sudo().write({
                    'res_model': 'product.category',
                    'res_id': category.id,
                    'res_field': False,
                })
            # Bấm X trên ô tệp = bỏ hẳn tài liệu đó khỏi booklet.
            to_drop = stored - kept
            if to_drop:
                to_drop.sudo().unlink()

    def _auto_init(self):
        """
        FIX: If the 'color' column in DB is Char (due to previous incorrect version), village
        rename it to avoid Odoo base trying to convert it to Integer and crashing.
        """
        self.env.cr.execute("""
            SELECT data_type FROM information_schema.columns 
            WHERE table_name = 'product_category' AND column_name = 'color'
        """)
        res = self.env.cr.fetchone()
        if res and res[0] in ('character varying', 'text'):
            self.env.cr.execute("ALTER TABLE product_category RENAME COLUMN color TO color_hex_backup")
            self.env.cr.commit()
            
        return super()._auto_init()
    
    
    def write(self, vals):
        """Update all products' color when category color changes"""
        res = super(ProductCategory, self).write(vals)
        
        if 'real_estate_color' in vals:
            # Update all products in this category
            for category in self:
                products = self.env['product.template'].search([
                    ('categ_id', '=', category.id)
                ])
                if products:
                    products.write({'real_estate_color': vals['real_estate_color']})
        
        return res
