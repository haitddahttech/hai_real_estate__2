# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SitePlan(models.Model):
    _name = 'site.plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Site Plan / Master Plan'
    _order = 'name'

    name = fields.Char(
        string='Tên dự án',
        required=True,
        help='Tên bản đồ dự án hoặc phân khu'
    )
    
    image = fields.Binary(
        string='Ảnh bản đồ',
        required=True,
        attachment=True,
        help='Tải lên ảnh quy hoạch hoặc sơ đồ mặt bằng (giữ nguyên chất lượng gốc)'
    )
    
    image_filename = fields.Char(
        string='Tên file ảnh',
        help='Tên gốc của file ảnh đã tải lên'
    )
    
    cover_image = fields.Image(
        string='Ảnh đại diện',
        max_width=1920,
        max_height=1080,
        help='Ảnh đại diện cho dự án, hiển thị trên portal'
    )
    
    description = fields.Text(
        string='Mô tả',
        help='Thông tin thêm về bản đồ này'
    )
    
    polygon_ids = fields.One2many(
        comodel_name='site.plan.polygon',
        inverse_name='site_plan_id',
        string='Danh sách lô đất',
        help='Các lô đất đã vẽ trên bản đồ này'
    )
    
    polygon_count = fields.Integer(
        string='Số lượng lô',
        compute='_compute_polygon_count',
        store=True
    )
    
    active = fields.Boolean(
        string='Đang hoạt động',
        default=True
    )
    deposit_date = fields.Date(
        string='Ngày đặt cọc',
        help='Ngày thực hiện đặt cọc',
        default=fields.Date.today
    )
    
    image_path = fields.Char(string='Đường dẫn ảnh local')
    
    catalog = fields.Binary(
        string='Catalogue dự án',
        attachment=True,
        help='Tải lên file Catalogue của dự án (PDF hoặc hình ảnh)'
    )
    
    catalog_filename = fields.Char(
        string='Tên file Catalogue',
        help='Tên gốc của file Catalogue đã tải lên'
    )

    project_legal_1 = fields.Binary(
        string='Pháp lý dự án 1',
        attachment=True,
        help='File pháp lý dự án 1 (PDF)'
    )
    project_legal_1_filename = fields.Char(string='Tên file Pháp lý 1')

    project_legal_2 = fields.Binary(
        string='Pháp lý dự án 2',
        attachment=True,
        help='File pháp lý dự án 2 (PDF)'
    )
    project_legal_2_filename = fields.Char(string='Tên file Pháp lý 2')

    project_legal_3 = fields.Binary(
        string='Pháp lý dự án 3',
        attachment=True,
        help='File pháp lý dự án 3 (PDF)'
    )
    project_legal_3_filename = fields.Char(string='Tên file Pháp lý 3')

    folder_ids = fields.One2many(
        comodel_name='site.plan.folder',
        inverse_name='site_plan_id',
        string='Thư mục ảnh'
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.image:
                record._save_image_to_disk()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'image' in vals:
            for record in self:
                if record.image:
                    record._save_image_to_disk()
        return res

    def _save_image_to_disk(self):
        """Save image from binary field to module static folder"""
        import base64
        import os
        from odoo.modules.module import get_module_path

        self.ensure_one()
        if not self.image:
            return

        # Define path: static/site_maps/site_plan_<id>.png
        filename = f"site_plan_{self.id}.png"
        
        # Get absolute path to module directory
        module_path = get_module_path('real_estate_site_plan')
        if not module_path:
            return

        # Ensure static/site_maps exists
        site_maps_dir = os.path.join(module_path, 'static', 'site_maps')
        if not os.path.exists(site_maps_dir):
            try:
                os.makedirs(site_maps_dir)
            except OSError:
                # If we cannot create directory (permission?), abort
                return

        file_path = os.path.join(site_maps_dir, filename)

        try:
            with open(file_path, 'wb') as f:
                f.write(base64.b64decode(self.image))
            
            # Update path field relative to module
            rel_path = f"/real_estate_site_plan/static/site_maps/{filename}"
            # Avoid recursion loop in write
            self.env.cr.execute("UPDATE site_plan SET image_path=%s WHERE id=%s", (rel_path, self.id))
            self.invalidate_recordset(['image_path'])
        except Exception as e:
            # Log error but don't stop flow
            print(f"Failed to save site plan image to disk: {e}")

    @api.depends('polygon_ids')
    def _compute_polygon_count(self):
        for record in self:
            record.polygon_count = len(record.polygon_ids)
    
    def action_view_polygons(self):
        """Open the list of polygons for this site plan"""
        self.ensure_one()
        return {
            'name': 'Polygons',
            'type': 'ir.actions.act_window',
            'res_model': 'site.plan.polygon',
            'view_mode': 'list,form',
            'domain': [('site_plan_id', '=', self.id)],
            'context': {'default_site_plan_id': self.id},
        }
    
    def action_view_portal_map(self):
        """Open portal map view for this site plan"""
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        portal_url = f"{base_url}/my/site-plan/{self.id}"
        
        return {
            'type': 'ir.actions.act_url',
            'url': portal_url,
            'target': 'new',
        }


class SitePlanFolder(models.Model):
    _name = 'site.plan.folder'
    _description = 'Thư mục ảnh phối cảnh'
    _order = 'sequence, id'

    name = fields.Char(string='Tên thư mục', required=True)
    sequence = fields.Integer(string='Thứ tự', default=10)
    site_plan_id = fields.Many2one('site.plan', string='Dự án', required=True, ondelete='cascade')
    image_ids = fields.One2many('site.plan.image', 'folder_id', string='Danh sách ảnh')
    
    image_count = fields.Integer(string='Số lượng ảnh', compute='_compute_image_count')
    
    @api.depends('image_ids')
    def _compute_image_count(self):
        for folder in self:
            folder.image_count = len(folder.image_ids)


class SitePlanImage(models.Model):
    _name = 'site.plan.image'
    _description = 'Ảnh phối cảnh'
    _order = 'sequence, id'

    name = fields.Char(string='Tên ảnh')
    sequence = fields.Integer(string='Thứ tự', default=10)
    folder_id = fields.Many2one('site.plan.folder', string='Thư mục', required=True, ondelete='cascade')
    image = fields.Image(string='Ảnh', required=True, max_width=1920, max_height=1080)
    description = fields.Text(string='Mô tả')


class SitePlanImageUpload(models.TransientModel):
    _name = 'site.plan.image.upload'
    _description = 'Wizard tải lên nhiều ảnh'

    folder_id = fields.Many2one('site.plan.folder', string='Thư mục', required=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Chọn ảnh')

    def action_upload(self):
        self.ensure_one()
        if not self.attachment_ids:
            return
        
        # Create image records from attachments
        values_list = []
        for attachment in self.attachment_ids:
            values_list.append({
                'folder_id': self.folder_id.id,
                'name': attachment.name,
                'image': attachment.datas,
                'sequence': 10
            })
            
        if values_list:
            self.env['site.plan.image'].create(values_list)
            
        return {'type': 'ir.actions.act_window_close'}
