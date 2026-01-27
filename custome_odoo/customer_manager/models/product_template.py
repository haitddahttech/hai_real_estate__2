import requests
from odoo import models, fields, api, _

class ProductTemplate(models.Model):
    _inherit = "product.template"

    # sale_state = fields.Selection(
    #     selection=[
    #         ('available', 'Available'),
    #         ],)

    is_sold = fields.Boolean(
        string='Đã bán',
        compute='_compute_is_sold',
        store=True,
        tracking=True,
        copy=False,
        help='Indicates if this product/property has been sold'
    )
    
    buyer_id = fields.Many2one(
        comodel_name='res.partner',
        string='Buyer',
        copy=False,
        tracking=True,
    )
    customer_follower_ids = fields.Many2many(
        comodel_name='res.partner',
        string='Followers',
        compute='_compute_customer_follower_ids',
        relation='product_template_customer_follower_rel',
        column1='product_template_id',
        column2='res_partner_id',
    )
    count_customer_followers = fields.Integer(
        string='Number of Customer Followers',
        compute='_compute_count_customer_followers',
        copy=False,
    )

    def _compute_count_customer_followers(self):
        for rec in self:
            rec.count_customer_followers = len(rec.customer_follower_ids)

    def action_view_customer_followers(self):
        self.ensure_one()
        return {
            'name': _('Customer Followers'),
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'res_model': 'res.partner',
            'domain': [('id', 'in', self.customer_follower_ids.ids)],
            'context': dict(self.env.context),
        }

    def _compute_customer_follower_ids(self):
        for rec in self:
            if rec.id:
                query = """
                    SELECT res_partner_id 
                    FROM product_template_customer_follower_rel
                        
                    WHERE product_template_id = %s
                """ % (rec.id)
                self.env.cr.execute(query)
                partner_ids = [row[0] for row in self.env.cr.fetchall()]
                rec.customer_follower_ids = [(6, 0, partner_ids)]
            else:
                rec.customer_follower_ids = False


    @api.depends('buyer_id')
    def _compute_is_sold(self):
        for rec in self:
            rec.is_sold = bool(rec.buyer_id)

    @api.depends('type')
    def compute_is_storable(self):
        self.sudo().write({'is_storable': False})

    def action_save_record(self):
        """
        Save the current record.
        This method is called when user clicks the Save button.
        """
        self.ensure_one()
        # Simply return True to trigger the save
        # Odoo will automatically save any changes made to the form
        return True

