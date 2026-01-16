# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SitePlan(models.Model):
    _name = 'site.plan'
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
