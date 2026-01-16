# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ChangePartnerUserWizard(models.TransientModel):
    _name = 'change.partner.user.wizard'
    _description = 'Change Partner User Wizard'

    new_user_id = fields.Many2one(
        'res.users',
        string='New Salesperson',
        required=True,
        help='Select the new salesperson to assign to selected contacts'
    )
    partner_ids = fields.Many2many(
        'res.partner',
        string='Selected Contacts',
        help='Contacts that will be reassigned'
    )
    partner_count = fields.Integer(
        string='Number of Contacts',
        compute='_compute_partner_count'
    )

    @api.depends('partner_ids')
    def _compute_partner_count(self):
        for wizard in self:
            wizard.partner_count = len(wizard.partner_ids)

    @api.model
    def default_get(self, fields_list):
        """Get selected partners from context"""
        res = super(ChangePartnerUserWizard, self).default_get(fields_list)
        
        # Get selected partner IDs from context
        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            res['partner_ids'] = [(6, 0, active_ids)]
        
        return res

    def action_change_user(self):
        """Change user_id for all selected partners"""
        self.ensure_one()
        
        if not self.partner_ids:
            raise UserError(_('No contacts selected. Please select at least one contact.'))
        
        if not self.new_user_id:
            raise UserError(_('Please select a salesperson.'))
        
        # Update user_id for all selected partners
        self.partner_ids.write({
            'user_id': self.new_user_id.id
        })
        
        # Show success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%s contact(s) have been assigned to %s') % (
                    len(self.partner_ids),
                    self.new_user_id.name
                ),
                'type': 'success',
                'sticky': False,
            }
        }
