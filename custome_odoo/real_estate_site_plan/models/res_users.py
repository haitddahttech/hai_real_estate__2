# -*- coding: utf-8 -*-

from odoo import models, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def _get_default_action_id(self):
        """Override default action to redirect to backend root menu instead of portal"""
        # Return False to use the default Odoo backend home (root menu)
        # This prevents automatic redirect to portal for portal users
        return False
