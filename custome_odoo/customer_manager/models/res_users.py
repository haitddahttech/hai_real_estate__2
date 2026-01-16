import requests
from odoo import models, fields, api, _

class ResUsers(models.Model):
    _inherit = "res.users"

    customer_ids = fields.One2many(
        comodel_name='res.partner',
        inverse_name='user_id',
        string='Customers',
    )
    saled_amount = fields.Monetary(
        string='Saled Amount',
        compute='_compute_saled_amount',
        store=True,
        currency_field='company_currency_id',
    )
    count_customers = fields.Float(
        string='Number of Customers',
        compute='_compute_count_customers',
        store=True,
    )

    @api.depends('customer_ids')
    def _compute_count_customers(self):
        for user in self:
            user.count_customers = len(user.customer_ids.filtered(lambda c: c != user.partner_id))

    @api.depends('customer_ids.transaction_amount')
    def _compute_saled_amount(self):
        for user in self:
            total_amount = sum(user.customer_ids.mapped('transaction_amount'))
            user.saled_amount = total_amount

    def action_save_record(self):
        """
        Save the current record.
        This method is called when user clicks the Save button.
        """
        self.ensure_one()
        # Simply return True to trigger the save
        # Odoo will automatically save any changes made to the form
        return True

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create to automatically ADD group_partner_manager to new users.
        Uses command (4, id) to APPEND, not replace existing groups.
        """
        users = super(ResUsers, self).create(vals_list)
        
        # Get the group_partner_manager group
        partner_manager_group = self.env.ref('base.group_partner_manager', raise_if_not_found=False)
        
        if partner_manager_group:
            for user in users:
                # Command (4, id): LINK/ADD group without removing existing groups
                if partner_manager_group not in user.groups_id:
                    user.groups_id = [(4, partner_manager_group.id)]
        
        return users

    @api.model
    def default_get(self, fields_list):
        """
        Set default groups by ADDING group_partner_manager to existing defaults.
        Does NOT replace other default groups.
        """
        res = super(ResUsers, self).default_get(fields_list)
        
        # Add group_partner_manager to default groups_id
        if 'groups_id' in fields_list:
            partner_manager_group = self.env.ref('base.group_partner_manager', raise_if_not_found=False)
            
            if partner_manager_group:
                # Get existing default groups (from parent classes)
                existing_groups = res.get('groups_id', [])
                
                # Extract group IDs from existing commands
                group_ids = [cmd[1] for cmd in existing_groups if cmd[0] in (4, 6)]
                
                # Only add if not already present
                if partner_manager_group.id not in group_ids:
                    if not existing_groups:
                        # No existing groups, just add ours
                        res['groups_id'] = [(4, partner_manager_group.id)]
                    else:
                        # APPEND to existing groups (not replace)
                        res['groups_id'] = existing_groups + [(4, partner_manager_group.id)]
        
        return res