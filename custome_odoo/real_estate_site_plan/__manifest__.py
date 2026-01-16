# -*- coding: utf-8 -*-
{
    'name': 'Real Estate Site Plan',
    'version': '19.0.1.0.0',
    'category': 'Real Estate',
    'summary': 'Draw polygons on site plan images and link to products',
    'description': """
Real Estate Site Plan Manager
==============================
This module allows you to:
- Upload site plan/master plan images
- Draw polygons (free-form or rectangle) on the image
- Link each polygon to a unique product
- Customize polygon colors
- Manage real estate properties visually
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'product',
        'web',
        'portal',
        'website',
        'customer_manager',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/website_menu.xml',
        'views/site_plan_views.xml',
        'views/product_product_views.xml',
        'views/res_company_views.xml',
        'views/portal/portal_landing_page.xml',
        'views/portal/portal_templates.xml',
        'views/portal/portal_site_plan_detail.xml',
        'views/portal/portal_property_detail.xml',
        'views/discount_config_views.xml',
        'reports/property_detail_report.xml',
        'reports/property_detail_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # 'real_estate_site_plan/static/src/scss/custom_theme.scss',
            'real_estate_site_plan/static/src/js/site_plan_canvas.js',
            'real_estate_site_plan/static/src/xml/site_plan_canvas.xml',
        ],
        'web.assets_frontend': [
            'real_estate_site_plan/static/src/scss/custom_theme.scss',
            'real_estate_site_plan/static/src/js/portal_site_map.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
