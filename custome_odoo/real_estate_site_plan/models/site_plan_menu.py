# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SitePlan(models.Model):
    _inherit = 'site.plan'

    website_menu_id = fields.Many2one(
        'website.menu',
        string='Website Menu',
        help='Website menu item for this site plan',
        ondelete='cascade'
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Create website menu when site plan is created"""
        records = super().create(vals_list)
        for record in records:
            record._create_website_menu()
        return records

    def write(self, vals):
        """Update website menu when site plan name changes"""
        res = super().write(vals)
        if 'name' in vals or 'active' in vals:
            for record in self:
                if record.website_menu_id:
                    record.website_menu_id.write({
                        'name': record.name,
                        'is_visible': record.active,
                    })
                elif record.active:
                    record._create_website_menu()
        return res

    def unlink(self):
        """Delete website menu when site plan is deleted"""
        menus = self.mapped('website_menu_id')
        res = super().unlink()
        menus.unlink()
        return res

    def _create_website_menu(self):
        """Create website menu item for this site plan"""
        self.ensure_one()
        if not self.website_menu_id and self.active:
            # Find or create parent menu
            parent_menu = self.env.ref('real_estate_site_plan.menu_site_plans_parent', raise_if_not_found=False)
            
            # Create menu
            menu = self.env['website.menu'].create({
                'name': self.name,
                'url': f'/my/site-plan/{self.id}',
                'parent_id': parent_menu.id if parent_menu else False,
                'sequence': self.id,
                'is_visible': True,
            })
            self.website_menu_id = menu
