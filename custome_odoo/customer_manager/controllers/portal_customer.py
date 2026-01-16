# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError
from odoo.tools import groupby as groupbyelem
from operator import itemgetter


class PortalCustomerManager(CustomerPortal):
    
    def _prepare_home_portal_values(self, counters):
        """Thêm số lượng customers vào portal home"""
        values = super()._prepare_home_portal_values(counters)
        if 'customer_count' in counters:
            # Portal user chỉ thấy customers được assign cho họ
            customer_count = request.env['res.partner'].search_count([
                ('type', '!=', 'private'),
                ('is_company', '=', False),
            ])
            values['customer_count'] = customer_count
        return values
    
    @http.route(['/my/customers', '/my/customers/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_customers(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, search=None, search_in='name', **kw):
        """
        Hiển thị danh sách khách hàng cho portal user
        """
        values = self._prepare_portal_layout_values()
        Partner = request.env['res.partner']
        
        # Cấu hình domain mặc định
        domain = [
            ('type', '!=', 'private'),
            ('is_company', '=', False),
        ]
        
        # Tìm kiếm
        searchbar_inputs = {
            'name': {'input': 'name', 'label': _('Tên')},
            'phone': {'input': 'phone', 'label': _('Số điện thoại')},
            'email': {'input': 'email', 'label': _('Email')},
            'ref': {'input': 'ref', 'label': _('Mã tham chiếu')},
        }
        
        if search and search_in:
            search_domain = []
            if search_in == 'name':
                search_domain = [('name', 'ilike', search)]
            elif search_in == 'phone':
                search_domain = [('phone', 'ilike', search)]
            elif search_in == 'email':
                search_domain = [('email', 'ilike', search)]
            elif search_in == 'ref':
                search_domain = [('ref', 'ilike', search)]
            domain += search_domain
        
        # Sắp xếp
        searchbar_sortings = {
            'date': {'label': _('Ngày tạo mới nhất'), 'order': 'create_date desc'},
            'name': {'label': _('Tên'), 'order': 'name'},
            'ref': {'label': _('Mã tham chiếu'), 'order': 'ref'},
        }
        
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        
        # Lọc
        searchbar_filters = {
            'all': {'label': _('Tất cả'), 'domain': []},
            'has_phone': {'label': _('Có số điện thoại'), 'domain': [('phone', '!=', False)]},
            'has_email': {'label': _('Có email'), 'domain': [('email', '!=', False)]},
        }
        
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']
        
        # Đếm tổng số
        customer_count = Partner.search_count(domain)
        
        # Phân trang
        pager = portal_pager(
            url="/my/customers",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby, 'filterby': filterby, 'search_in': search_in, 'search': search},
            total=customer_count,
            page=page,
            step=self._items_per_page
        )
        
        # Lấy danh sách customers
        customers = Partner.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        
        values.update({
            'date': date_begin,
            'customers': customers,
            'page_name': 'customer',
            'default_url': '/my/customers',
            'pager': pager,
            'searchbar_sortings': searchbar_sortings,
            'searchbar_filters': searchbar_filters,
            'searchbar_inputs': searchbar_inputs,
            'sortby': sortby,
            'filterby': filterby,
            'search_in': search_in,
            'search': search,
        })
        
        return request.render("customer_manager.portal_my_customers", values)
    
    @http.route(['/my/customer/<int:customer_id>'], type='http', auth="user", website=True)
    def portal_customer_detail(self, customer_id, access_token=None, **kw):
        """
        Hiển thị chi tiết một khách hàng
        """
        try:
            customer_sudo = self._document_check_access('res.partner', customer_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        
        values = {
            'customer': customer_sudo,
            'page_name': 'customer',
        }
        
        return request.render("customer_manager.portal_customer_detail", values)
    
    @http.route(['/my/customer/<int:customer_id>/update'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def portal_customer_update(self, customer_id, **post):
        """
        Cập nhật thông tin khách hàng (tất cả fields)
        """
        try:
            customer_sudo = self._document_check_access('res.partner', customer_id)
        except (AccessError, MissingError):
            return request.redirect('/my')
        
        # Lấy dữ liệu từ form
        vals = {}
        
        # Basic info
        if post.get('name'):
            vals['name'] = post.get('name')
        if 'phone' in post:
            vals['phone'] = post.get('phone') or False
        if 'email' in post:
            vals['email'] = post.get('email') or False
        
        # Address
        if 'street' in post:
            vals['street'] = post.get('street') or False
        if 'city' in post:
            vals['city'] = post.get('city') or False
        
        # Appointment
        if 'appointment_date' in post:
            vals['appointment_date'] = post.get('appointment_date') or False
        if 'appointment_address' in post:
            vals['appointment_address'] = post.get('appointment_address') or False
        if 'appointment_note' in post:
            vals['appointment_note'] = post.get('appointment_note') or False
        
        # Comment
        if 'comment' in post:
            vals['comment'] = post.get('comment') or False
        
        # Try to update
        try:
            if vals:
                customer_sudo.write(vals)
            return request.redirect(f'/my/customer/{customer_id}?updated=1')
        except Exception as e:
            return request.redirect(f'/my/customer/{customer_id}?error={str(e)}')
    
    @http.route(['/my/customer/<int:customer_id>/request_edit'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def portal_customer_request_edit(self, customer_id, **post):
        """
        Portal user yêu cầu quyền chỉnh sửa
        """
        try:
            customer_sudo = self._document_check_access('res.partner', customer_id)
        except (AccessError, MissingError):
            return request.redirect('/my')
        
        # Update edit_state to request_edit
        try:
            customer_sudo.write({'edit_state': 'request_edit'})
            return request.redirect(f'/my/customer/{customer_id}?requested=1')
        except Exception as e:
            return request.redirect(f'/my/customer/{customer_id}?error={str(e)}')
