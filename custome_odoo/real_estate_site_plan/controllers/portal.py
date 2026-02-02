# -*- coding: utf-8 -*-

import json
import logging
import subprocess
import tempfile
import os
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

_logger = logging.getLogger(__name__)


class SitePlanPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        """Add site plans count and list to portal home"""
        values = super()._prepare_home_portal_values(counters)
        SitePlan = request.env['site.plan']
        if 'site_plan_count' in counters:
            values['site_plan_count'] = SitePlan.search_count([('active', '=', True)])
        
        # Always fetch site plans for direct menu display if needed
        site_plans = SitePlan.search([('active', '=', True)], order='id')
        values['site_plans_list'] = site_plans
        return values

    @http.route(['/', '/real-estate', '/real-estate/'], type='http', auth='user', website=True)
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
        try:
            site_plan = request.env['site.plan'].browse(site_plan_id)
            
            # Check existence and active status
            if not site_plan.exists() or not site_plan.active:
                _logger.warning(f"Site plan {site_plan_id} not found or inactive")
                return request.redirect('/my')
            
            # Check access rights
            try:
                site_plan.check_access_rights('read')
                site_plan.check_access_rule('read')
            except Exception as access_error:
                _logger.warning(f"Access denied for site plan {site_plan_id}: {access_error}")
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
                    product_data = {
                        'id': product.id,
                        'name': product.name,
                        'category': product.categ_id.display_name if product.categ_id else '',
                        'property_type': property_type_label,
                        'direction': direction_label,
                        'price': float(product.list_price) if product.list_price else 0.0,
                        'area': float(product.area) if product.area else 0.0,
                        'deposit': float(product.deposit) if product.deposit else 0.0,
                        'construction_area': float(product.construction_area) if hasattr(product, 'construction_area') and product.construction_area else 0.0,
                        'price_per_m2': float(product.price_per_m2) if product.price_per_m2 else 0.0,
                        'vat_tax': float(product.vat_tax) if hasattr(product, 'vat_tax') and product.vat_tax else 0.0,
                        'is_sold': bool(product.is_sold),
                        'is_decoration': bool(product.is_decoration),
                        'decoration_note': product.decoration_note or '',
                        'buyer_name': product.buyer_id.name if product.buyer_id else '',
                        'currency_symbol': product.currency_id.symbol if product.currency_id else '$',
                        'attachments': []
                    }

                    # Add attachments for decoration or anyway
                    attachments = request.env['ir.attachment'].sudo().search([
                        ('res_model', '=', 'product.template'),
                        ('res_id', '=', product.id),
                        ('mimetype', 'ilike', 'image')
                    ])
                    for attach in attachments:
                        product_data['attachments'].append({
                            'id': attach.id,
                            'name': attach.name,
                            'url': f'/web/image/{attach.id}'
                        })

                    polygon_data.append({
                        'id': polygon.id,
                        'name': polygon.name,
                        'coordinates': polygon.coordinates,
                        'color': polygon.color,
                        'product': product_data
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
        except Exception as e:
            _logger.error(f"Error in portal_site_plan_detail for site plan {site_plan_id}: {e}")
            return request.redirect('/my')

    @http.route(['/my/property/<int:product_id>'], type='http', auth='user', website=True)
    def portal_property_detail(self, product_id, **kw):
        """View property detail"""
        try:
            product = request.env['product.template'].browse(product_id)
            
            # Check existence
            if not product.exists():
                _logger.warning(f"Product {product_id} not found")
                return request.redirect('/my')
            
            # Check access rights
            try:
                product.check_access('read')
            except Exception as access_error:
                _logger.warning(f"Access denied for product {product_id}: {access_error}")
                return request.redirect('/my')
            
            values = {
                'product': product,
                'page_name': 'property_detail',
            }
            return request.render('real_estate_site_plan.portal_property_detail', values)
        except Exception as e:
            _logger.error(f"Error in portal_property_detail for product {product_id}: {e}")
            return request.redirect('/my')

    @http.route(['/my/property/<int:product_id>/download-pdf'], type='http', auth='user', website=True)
    def portal_property_detail_pdf(self, product_id, bank_id=None, **kw):
        """Download property detail as PDF"""
        try:
            product = request.env['product.template'].browse(product_id)
            
            # Check existence
            if not product.exists():
                _logger.warning(f"Product {product_id} not found for PDF download")
                return request.redirect('/my')
            
            # Handle discount_ids param to sync state before printing
            if 'discount_ids' in kw:
                try:
                    d_ids = []
                    if kw['discount_ids']:
                        d_ids = [int(x) for x in kw['discount_ids'].split(',')]
                    
                    # Update product discounts
                    product.sudo().write({
                        'selected_discount_ids': [(6, 0, d_ids)]
                    })
                except Exception as e:
                    _logger.error(f"Error applying discounts for PDF: {e}")
            
            # Check access rights
            try:
                product.check_access_rights('read')
                product.check_access_rule('read')
            except Exception as access_error:
                _logger.warning(f"Access denied for PDF of product {product_id}: {access_error}")
                return request.redirect('/my')
            
            # Get the report
            report = request.env['ir.actions.report'].sudo().search([
                ('report_name', '=', 'real_estate_site_plan.report_property_detail_document')
            ], limit=1)
            
            if not report:
                _logger.error("Property detail report not found")
                return request.redirect('/my')
            
            # Prepare context for rendering
            context = dict(request.env.context)
            if bank_id:
                context['selected_bank_id'] = int(bank_id)
            
            # Render the PDF
            pdf_content, _ = report.with_context(context)._render_qweb_pdf(
                report_ref='real_estate_site_plan.report_property_detail_document', 
                res_ids=product_id
            )
            
            pdfhttpheaders = [
                ('Content-Type', 'application/pdf'),
                ('Content-Length', len(pdf_content)),
                ('Content-Disposition', f'attachment; filename="Property_{product.name}.pdf"')
            ]
            
            return request.make_response(pdf_content, headers=pdfhttpheaders)
        except Exception as e:
            _logger.error(f"Error generating PDF for product {product_id}: {e}")
            return request.redirect('/my')

    @http.route(['/my/property/<int:product_id>/download-image'], type='http', auth='user', website=True)
    def portal_property_detail_image(self, product_id, bank_id=None, **kw):
        """Download property detail as Image (PNG)"""
        try:
            product = request.env['product.template'].browse(product_id)
            
            if not product.exists():
                return request.redirect('/my')
            
            # Handle discount_ids param to sync state before printing
            if 'discount_ids' in kw:
                try:
                    d_ids = []
                    if kw['discount_ids']:
                        d_ids = [int(x) for x in kw['discount_ids'].split(',')]
                    
                    # Update product discounts
                    product.sudo().write({
                        'selected_discount_ids': [(6, 0, d_ids)]
                    })
                except Exception as e:
                    _logger.error(f"Error applying discounts for Image: {e}")

            # Check access rights
            product.check_access('read')
            
            # Get the report record
            report = request.env['ir.actions.report'].sudo().search([
                ('report_name', '=', 'real_estate_site_plan.report_property_detail_document')
            ], limit=1)
            
            if not report:
                return request.redirect('/my')
            
            # Prepare context for rendering
            context = dict(request.env.context)
            if bank_id:
                context['selected_bank_id'] = int(bank_id)
            
            # Render HTML content first
            html_content = report.with_context(context)._render_qweb_html(
                report_ref='real_estate_site_plan.report_property_detail_document', 
                docids=[product_id]
            )[0]
            
            # Convert HTML to Image using wkhtmltoimage
            try:
                # We add --load-error-handling ignore to prevent ContentNotFoundError from aborting the process
                # This is common when some assets (like small icons or non-critical images) fail to load
                cmd = [
                    'wkhtmltoimage',
                    '--format', 'png',
                    '--quality', '100',
                    '--load-error-handling', 'ignore',
                    '--quiet',
                    '-', # read from stdin
                    '-'  # write to stdout
                ]
                
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                image_content, stderr = process.communicate(input=html_content)
                
                if process.returncode != 0 and not image_content:
                    _logger.error(f"wkhtmltoimage error: {stderr.decode('utf-8')}")
                    return request.redirect('/my')
                    
                imagehttpheaders = [
                    ('Content-Type', 'image/png'),
                    ('Content-Length', len(image_content)),
                    ('Content-Disposition', f'attachment; filename="Property_{product.name}.png"')
                ]
                
                return request.make_response(image_content, headers=imagehttpheaders)
                
            except Exception as e:
                _logger.error(f"Failed to call wkhtmltoimage: {e}")
                return request.redirect('/my')
                
        except Exception as e:
            _logger.error(f"Error generating Image for product {product_id}: {e}")
            return request.redirect('/my')

    @http.route(['/my/property/<int:product_id>/save_discounts'], type='jsonrpc', auth='user', methods=['POST'])
    def save_selected_discounts(self, product_id, discount_ids=None, **kw):
        """Save selected discounts to product"""
        try:
            product = request.env['product.template'].sudo().browse(product_id)
            if not product.exists():
                return {'success': False, 'error': 'Product not found'}
            
            # Update selected_discount_ids
            discount_ids = discount_ids or []
            product.write({
                'selected_discount_ids': [(6, 0, discount_ids)]  # Replace all with new selection
            })
            
            return {
                'success': True,
                'message': 'Discounts saved successfully',
                'selected_count': len(discount_ids)
            }
        except Exception as e:
            _logger.error(f"Error saving discounts: {str(e)}")
            return {'success': False, 'error': str(e)}
