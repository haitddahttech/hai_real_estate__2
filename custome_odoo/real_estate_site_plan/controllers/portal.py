# -*- coding: utf-8 -*-

import json
import logging
import subprocess
import tempfile
import os
from odoo import http, _
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
            # Prepare polygon data for JS
            polygon_data = []
            
            # --- OPTIMIZATION START ---
            
            # 1. Collect all product IDs to batch fetch attachments
            product_ids = [p.product_template_id.id for p in polygons if p.product_template_id]
            product_ids = list(set(product_ids)) # Remove duplicates
            
            # 2. Batch fetch attachments
            attachments_by_product = {}
            if product_ids:
                all_attachments = request.env['ir.attachment'].sudo().search([
                    ('res_model', '=', 'product.template'),
                    ('res_id', 'in', product_ids),
                    ('mimetype', 'ilike', 'image')
                ])
                for att in all_attachments:
                    if att.res_id not in attachments_by_product:
                        attachments_by_product[att.res_id] = []
                    attachments_by_product[att.res_id].append({
                        'id': att.id,
                        'name': att.name,
                        'url': f'/web/image/{att.id}'
                    })
            
            # 3. Cache selection fields to avoid repeated introspection
            # property_type is still a Selection; direction was migrated to Many2one (real.estate.direction).
            ProductTemplate = request.env['product.template']
            pt_fields = ProductTemplate.fields_get(['property_type'])
            property_type_selection = dict(pt_fields.get('property_type', {}).get('selection', []))
            
            # --- OPTIMIZATION END ---

            for polygon in polygons:
                product = polygon.product_template_id
                
                if not product:
                    continue  # Skip polygons without products
                
                # Safely get labels (Selection for property_type, Many2one for direction)
                property_type_label = property_type_selection.get(product.property_type, '')
                direction_label = product.direction_id.name or ''
                
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
                        'is_inhouse_cart': bool(product.is_inhouse_cart),
                        'is_agency_cart': bool(product.is_agency_cart),
                        'is_decoration': bool(product.is_decoration),
                        'decoration_note': product.decoration_note or '',
                        'buyer_name': product.buyer_id.name if product.buyer_id else '',
                        'currency_symbol': product.currency_id.symbol if product.currency_id else '$',
                        'attachments': attachments_by_product.get(product.id, []) # Use pre-fetched data
                    }

                    polygon_data.append({
                        'id': polygon.id,
                        'name': polygon.name,
                        'coordinates': polygon.coordinates,
                        'color': polygon.color,
                        'price_label_x': polygon.price_label_x,
                        'price_label_y': polygon.price_label_y,
                        'product': product_data
                    })
                except Exception as e:
                    _logger.error(f"Error preparing polygon data for polygon {polygon.id}: {e}")
                    continue
        
            def safe_translate(term):
                """Helper to ensure translation works even if Odoo's DB lookup fails for some terms"""
                translated = _(term)
                if translated == term and request.env.lang == 'zh_TW':
                    fallbacks = {
                        'CHI TIẾT': '細節',
                        'Chưa có ảnh': '暫無圖片',
                        'CÒN TRỐNG': '待售',
                        'ĐÃ BÁN': '已售',
                        'Diện tích đất': '土地面積',
                        'Đơn giá/m²': '單價/m²',
                        'DT xây dựng': '建築面積',
                        'Giá bán': '售價',
                        'Hình ảnh': '圖片',
                        'Hướng': '方向',
                        'Loại hình': '類型',
                        'Mã căn': '房號',
                        'TIỆN ÍCH DỰ ÁN': '項目設施',
                        'Xem thêm': '查看更多'
                    }
                    return fallbacks.get(term, term)
                return translated

            js_translations = {
                'CHI TIẾT': safe_translate('CHI TIẾT'),
                'Chưa có ảnh': safe_translate('Chưa có ảnh'),
                'CÒN TRỐNG': safe_translate('CÒN TRỐNG'),
                'ĐÃ BÁN': safe_translate('ĐÃ BÁN'),
                'Diện tích đất': safe_translate('Diện tích đất'),
                'Đơn giá/m²': safe_translate('Đơn giá/m²'),
                'DT xây dựng': safe_translate('DT xây dựng'),
                'Giá bán': safe_translate('Giá bán'),
                'Hình ảnh': safe_translate('Hình ảnh'),
                'Hướng': safe_translate('Hướng'),
                'Loại hình': safe_translate('Loại hình'),
                'Mã căn': safe_translate('Mã căn'),
                'TIỆN ÍCH DỰ ÁN': safe_translate('TIỆN ÍCH DỰ ÁN'),
                'Xem thêm': safe_translate('Xem thêm')
            }
            values = {
                'site_plan': site_plan,
                'polygon_data_json': json.dumps(polygon_data),
                'js_translations_json': json.dumps(js_translations),
                'price_display_number': site_plan.price_display_number or 0,
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
            # Always update to clear old selections if none selected
            try:
                d_ids = []
                if kw.get('discount_ids'):
                    d_ids = [int(x) for x in kw['discount_ids'].split(',') if x]
                
                # Update product discounts (clears if d_ids is empty)
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
            # Always update to clear old selections if none selected
            try:
                d_ids = []
                if kw.get('discount_ids'):
                    d_ids = [int(x) for x in kw['discount_ids'].split(',') if x]
                
                # Update product discounts (clears if d_ids is empty)
                product.sudo().write({
                    'selected_discount_ids': [(6, 0, d_ids)]
                })
            except Exception as e:
                _logger.error(f"Error applying discounts for Image: {e}")

            # Check access rights
            product.sudo().check_access('read')
            
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

    @http.route(['/change_lang/<string:lang>'], type='http', auth='user', website=True)
    def change_language(self, lang, **kw):
        """Switch the current user's language and redirect back"""
        allowed_langs = ['vi_VN', 'zh_TW']
        if lang in allowed_langs:
            # Update the user's language preference in the database
            request.env.user.sudo().write({'lang': lang})
            # Also set the frontend cookie for immediate effect
            redirect_url = request.httprequest.referrer or '/'
            response = request.redirect(redirect_url)
            response.set_cookie('frontend_lang', lang, max_age=365*24*60*60, httponly=False, samesite='Lax')
            return response
        return request.redirect(request.httprequest.referrer or '/')
