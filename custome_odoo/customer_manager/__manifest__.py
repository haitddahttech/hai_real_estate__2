# -*- coding: utf-8 -*-
{
    "name": "Customer Manager",
    "category": "Custome",
    "version": "1.0",
    'license': 'LGPL-3',
    "author": "Haitdd",
    "depends": [
        'base',
        'contacts',
        'stock',
        'product',
        'portal',
        'web_view_enterprise',
    ],
    "data": [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
        'views/res_users_views.xml',
        'views/product_views.xml',
        'views/save_button_views.xml',
        'views/portal_customer_views.xml',
        'wizard/change_partner_user_wizard_views.xml',
        # 'views/res_config_settings_views.xml',
        # 'views/res_company_views.xml',
        # 'views/res_bank_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'customer_manager/static/src/css/portal_customer.css',
            'customer_manager/static/src/js/portal_appointment.js',
        ],
    },
}
