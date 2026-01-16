# -*- coding: utf-8 -*-
from odoo import models, api


class ProductCategory(models.Model):
    _inherit = 'product.category'

    def action_save_record(self):
        """
        Save the current record.
        This method is called when user clicks the Save button.
        """
        self.ensure_one()
        # Simply return True to trigger the save
        # Odoo will automatically save any changes made to the form
        return True
