import requests
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = "res.partner"

    appointment_date = fields.Datetime(
        string='Appointment Date',
        tracking=True,
        copy=False,
    )
    appointment_note = fields.Text(
        string='Nội dung cuộc hẹn',
        tracking=True,
        copy=False,
    )
    appointment_address = fields.Text(
        string='Địa điểm hẹn',
        tracking=True,
        copy=False,
    )
    edit_state = fields.Selection(
        selection=[
            ('draft', 'Available to Edit'),
            ('request_edit', 'Request to Edit'),
            ('manager_edit', 'Manager Edite'),
        ],
        string='Edit State',
        default='draft',
        tracking=True,
    )
    has_group_admin = fields.Boolean(
        string='Has Group Admin',
        compute='_compute_has_group_admin',
        store=False,
    )
    customer_sale_state = fields.Selection(
        selection=[
            ('not_contact_yet', 'Not contact yet'),
            ('can_not_contact', 'Cannot contact'),
            ('potential_customers', 'Potential Customers'),
            ('non_potential_customers', 'Non-potential Customers'),
            ('caring', 'Caring'),
            ('finalize', 'Finalize'),
            ('deposited', 'Deposited'),
            ('passed', 'Passed'),
            ('after_sale_service', 'After-sale Caring Service'),
        ],
        string='Customer Sale State',
        default='not_contact_yet',
        tracking=True,
    )
    x_bought_product_ids = fields.One2many(
        comodel_name='product.template',
        inverse_name='buyer_id',
        string='Bought Products',
    )
    count_bought_product = fields.Integer(
        string='Count Bought Products',
        compute='_compute_count_bought_product',
        store=True,
    )
    follower_product_ids = fields.Many2many(
        comodel_name='product.template',
        string='Followed Products',
        relation='product_template_customer_follower_rel',
        column1='res_partner_id',
        column2='product_template_id',
        copy=False,
    )
    pass_change = fields.Float(
        string='Pass Change (%)',
        help='The percentage change in the number of passed products compared to the followed products.',
        compute='_compute_pass_change',
        store=True,
    )
    count_follower_product = fields.Integer(
        string='Count Followed Products',
        compute='_compute_count_follower_product',
        store=True,
    )
    company_currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    transaction_amount = fields.Monetary(
        string='Transaction Amount',
        tracking=True,
        compute='_compute_transaction_amount',
        store=True,
        currency_field='company_currency_id'
    )
    assign_sale_date = fields.Date(
        string='Thời gian Sale nhận khách',
        help='Thời gian khách hàng được giao cho sale hiện tại phụ trách',
        compute='_compute_assign_sale_date',
        store=True,
    )

    @api.depends('user_id')
    @api.onchange('user_id')
    def _compute_assign_sale_date(self):
        for rec in self:
            if rec.user_id:
                rec.assign_sale_date = fields.Date.today()
            else:
                rec.assign_sale_date = False

    @api.depends('count_bought_product', 'count_follower_product')
    def _compute_pass_change(self):
        for rec in self:
            if rec.count_follower_product > 0:
                rec.pass_change = (rec.count_bought_product / rec.count_follower_product) * 100
            else:
                rec.pass_change = 0.0

    @api.depends('x_bought_product_ids')
    def _compute_count_bought_product(self):
        for partner in self:
            partner.count_bought_product = len(partner.x_bought_product_ids)

    @api.depends('follower_product_ids')
    def _compute_count_follower_product(self):
        for partner in self:
            partner.count_follower_product = len(partner.follower_product_ids)

    @api.depends('x_bought_product_ids')
    def _compute_transaction_amount(self):
        for partner in self:
            total_amount = sum(partner.x_bought_product_ids.mapped('list_price'))
            partner.transaction_amount = total_amount

    def action_not_contact_yet(self):
        for rec in self:
            rec.customer_sale_state = 'not_contact_yet'

    def action_cannot_contact(self):
        for rec in self:
            rec.customer_sale_state = 'can_not_contact'

    def action_potential_customers(self):
        for rec in self:
            rec.customer_sale_state = 'potential_customers'

    def action_non_potential_customers(self):
        for rec in self:
            rec.customer_sale_state = 'non_potential_customers'

    def action_caring(self):
        for rec in self:
            rec.customer_sale_state = 'caring'

    def action_finalize(self):
        for rec in self:
            rec.customer_sale_state = 'finalize'

    def action_deposited(self):
        for rec in self:
            rec.customer_sale_state = 'deposited'

    def action_passed(self):
        for rec in self:
            rec.customer_sale_state = 'passed'

    def action_after_sale_service(self):
        for rec in self:
            rec.customer_sale_state = 'after_sale_service'

    def _compute_has_group_admin(self):
        if self.env.user.has_group('base.group_system'):
            for partner in self:
                partner.has_group_admin = True
        else:
            for partner in self:
                partner.has_group_admin = False

    def action_disable_edit(self):
        for rec in self:
            rec.edit_state = 'manager_edit'

    def action_request_edit(self):
        self.sudo().write({'edit_state': 'request_edit'})

    def action_enable_edit(self):
        for rec in self:
            rec.edit_state = 'draft'

    def action_save_record(self):
        """
        Save the current record.
        This method is called when user clicks the Save button.
        """
        self.ensure_one()
        # Simply return True to trigger the save
        # Odoo will automatically save any changes made to the form
        return True

    def write(self, vals):
        """
        Override write to implement edit_state logic for portal users.
        Portal users can edit all fields when edit_state == 'draft'.
        When edit_state != 'draft', portal users cannot edit (must request edit first).
        """
        # Check if current user is a portal user
        if self.env.user.has_group('base.group_portal'):
            # Check edit_state for each record
            for record in self:
                # If edit_state is not 'draft', block the edit
                if record.edit_state != 'draft':
                    # Allow only 'edit_state' field to be updated (for request_edit action)
                    if set(vals.keys()) == {'edit_state'}:
                        # Allow changing edit_state (for request edit)
                        pass
                    else:
                        # Block other field updates
                        from odoo.exceptions import UserError
                        raise UserError(
                            _("Bạn không thể chỉnh sửa khách hàng này. "
                              "Trạng thái hiện tại: %s. "
                              "Vui lòng yêu cầu quyền chỉnh sửa.") % dict(record._fields['edit_state'].selection).get(record.edit_state)
                        )
        
        return super(ResPartner, self).write(vals)

    def action_change_salesperson_wizard(self):
        """
        Open wizard to change salesperson for selected partners.
        This method is called from list view action button.
        """
        return {
            'name': _('Change Salesperson'),
            'type': 'ir.actions.act_window',
            'res_model': 'change.partner.user.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_ids': [(6, 0, self.ids)],
            }
        }