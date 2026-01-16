# -*- coding: utf-8 -*-

import json
import logging
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

_logger = logging.getLogger(__name__)


class SitePlanPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        """Add site plans count to portal home"""
        values = super()._prepare_home_portal_values(counters)
        if 'site_plan_count' in counters:
            site_plan_count = request.env['site.plan'].search_count([('active', '=', True)])
            values['site_plan_count'] = site_plan_count
        return values

    @http.route(['/real-estate', '/real-estate/'], type='http', auth='public', website=True)
    def portal_landing_page(self, **kw):
        """Landing page for real estate site plans"""
        return request.render('real_estate_site_plan.portal_landing_page')

    @http.route(['/my/site-plans', '/my/site-plans/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_site_plans(self, page=1, sortby=None, **kw):
        """List all site plans"""
        SitePlan = request.env['site.plan']
        
        # Count
        site_plan_count = SitePlan.search_count([('active', '=', True)])
        
        # Pager
        pager = portal_pager(
            url='/my/site-plans',
            total=site_plan_count,
            page=page,
            step=self._items_per_page
        )
        
        # Search
        site_plans = SitePlan.search([('active', '=', True)], limit=self._items_per_page, offset=pager['offset'])
        
        values = {
            'site_plans': site_plans,
            'page_name': 'site_plan',
            'pager': pager,
            'default_url': '/my/site-plans',
        }
        return request.render('real_estate_site_plan.portal_my_site_plans', values)

    @http.route(['/my/site-plan/<int:site_plan_id>'], type='http', auth='user', website=True)
    def portal_site_plan_detail(self, site_plan_id, **kw):
        """View site plan map with polygons"""
        site_plan = request.env['site.plan'].browse(site_plan_id)
        
        # Check access
        if not site_plan.exists() or not site_plan.active:
            return request.redirect('/my')
        
        # Get polygons with product info
        polygons = request.env['site.plan.polygon'].search([
            ('site_plan_id', '=', site_plan_id),
            ('active', '=', True)
        ])
        
        # Prepare polygon data for JS
        polygon_data = []
        for polygon in polygons:
            product = polygon.product_template_id
            
            if not product:
                continue  # Skip polygons without products
            
            # Safely get selection field labels
            property_type_label = ''
            direction_label = ''
            
            try:
                if hasattr(product, 'property_type') and product.property_type:
                    property_type_label = dict(product._fields['property_type'].selection).get(product.property_type, '')
            except Exception as e:
                _logger.warning(f"Error getting property_type for product {product.id}: {e}")
            
            try:
                if hasattr(product, 'direction') and product.direction:
                    direction_label = dict(product._fields['direction'].selection).get(product.direction, '')
            except Exception as e:
                _logger.warning(f"Error getting direction for product {product.id}: {e}")
            
            try:
                polygon_data.append({
                    'id': polygon.id,
                    'name': polygon.name,
                    'coordinates': polygon.coordinates,
                    'color': polygon.color,
                    'product': {
                        'id': product.id,
                        'name': product.name,
                        'category': product.categ_id.display_name if product.categ_id else '',
                        'property_type': property_type_label,
                        'direction': direction_label,
                        'price': float(product.list_price) if product.list_price else 0.0,
                        'area': float(product.area) if product.area else 0.0,
                        'deposit': float(product.deposit) if product.deposit else 0.0,
                        'price_per_m2': float(product.price_per_m2) if product.price_per_m2 else 0.0,
                        'vat_tax': float(product.vat_tax) if hasattr(product, 'vat_tax') and product.vat_tax else 0.0,
                        'is_sold': bool(product.is_sold),
                        'currency_symbol': product.currency_id.symbol if product.currency_id else '$',
                    }
                })
            except Exception as e:
                _logger.error(f"Error preparing polygon data for polygon {polygon.id}: {e}")
                continue
        
        values = {
            'site_plan': site_plan,
            'polygon_data_json': json.dumps(polygon_data),
            'page_name': 'site_plan_detail',
        }
        return request.render('real_estate_site_plan.portal_site_plan_detail', values)

    @http.route(['/my/property/<int:product_id>'], type='http', auth='user', website=True)
    def portal_property_detail(self, product_id, **kw):
        """View property detail"""
        product = request.env['product.template'].browse(product_id)
        
        # Check access
        if not product.exists():
            return request.redirect('/my')
        
        values = {
            'product': product,
            'page_name': 'property_detail',
        }
        return request.render('real_estate_site_plan.portal_property_detail', values)

    @http.route(['/my/property/<int:product_id>/download-pdf'], type='http', auth='user', website=True)
    def portal_property_detail_pdf(self, product_id, **kw):
        """Download property detail as PDF"""
        product = request.env['product.template'].browse(product_id)
        
        # Check access
        if not product.exists():
            return request.redirect('/my')
        
        # Get the report
        report = request.env['ir.actions.report'].sudo().search([
            ('report_name', '=', 'real_estate_site_plan.report_property_detail_document')
        ], limit=1)
        
        if not report:
            return request.redirect('/my')
        
        # Render the PDF
        pdf_content, _ = report._render_qweb_pdf(report_ref='real_estate_site_plan.report_property_detail_document', res_ids=product_id)
        
        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf_content)),
            ('Content-Disposition', f'attachment; filename="Property_{product.name}.pdf"')
        ]
        
        return request.make_response(pdf_content, headers=pdfhttpheaders)
