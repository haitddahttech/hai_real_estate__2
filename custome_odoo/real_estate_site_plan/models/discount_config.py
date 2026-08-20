# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ProductDiscountConfig(models.Model):
    _name = 'product.discount.config'
    _description = 'Cấu hình giảm giá'
    _order = 'sequence, name'

    # Làm tròn bám theo đúng file Excel nguồn (sheet "CK GD2 SH"):
    # giá nhà ROUND(...,-4), quỹ bảo trì ROUND(...,-3).
    ROUND_SALE = -4    # giá nhà: bội 10.000
    ROUND_MAINT = -3   # quỹ bảo trì: bội 1.000

    name = fields.Char(string='Tên chương trình', translate=True, required=True)
    sequence = fields.Integer(string='Thứ tự', default=10, help="Thứ tự hiển thị, số nhỏ hơn sẽ hiển thị trước")
    qty = fields.Float(string='% giảm trên giá bán', default=0,
        help="Chỉ dùng cho loại 'Công thức % tính lại tổng giá'. "
             "Nhập 1 nghĩa là 1% giảm trên giá bán chưa TSDĐ, kéo theo VAT và Quỹ bảo trì tính lại.")
    discount_type = fields.Selection([
        ('percent',        'Phần trăm (%)'),
        ('amount',         'Số tiền cố định'),
        ('formula',        'Công thức theo sản phẩm'),
        ('percent_recalc', 'Công thức % tính lại tổng giá'),
    ], string='Loại giảm giá', required=True, default='percent')
    discount_value = fields.Float(string='Giá trị giảm', default=0,
        help="Phần trăm/số tiền/hệ số nhân tuỳ theo loại giảm giá. "
             "Không dùng cho loại 'Công thức % tính lại tổng giá' (dùng % giảm trên giá bán).")
    formula_type = fields.Selection([
        ('management_fee', 'Phí quản lý × Diện tích × Hệ số'),
        ('maintenance_fee', 'Phí bảo trì × Diện tích × Hệ số'),
        ('custom', 'Tùy chỉnh')
    ], string='Loại công thức', default='management_fee',
        help="Chọn công thức tính chiết khấu theo sản phẩm")
    active = fields.Boolean(string='Đang hoạt động', default=True)
    apply_stage = fields.Selection([
        ('ky_hop_dong', 'A — Trừ thẳng vào đợt Ký HĐMB'),
        ('spread',      'B — Chia đều từ đợt 4 đến Bàn giao nhà'),
        ('giao_nha',    'C — Trừ thẳng vào đợt Bàn giao nhà'),
    ], string='Mốc áp dụng', default='ky_hop_dong', required=True,
        help="Bắt buộc — vị trí trừ tiền chiết khấu trên LỊCH THANH TOÁN, mặc "
             "định là loại A. Với CK '% tính lại tổng giá' thì số tiền trừ vào "
             "đợt là phần giá nhà chưa TSDĐ bị cắt; với các loại còn lại là "
             "nguyên số tiền của chiết khấu. Thứ tự nhân chuỗi (CK sau tính "
             "trên giá đã trừ CK trước) vẫn lấy theo trường Thứ tự, không phụ "
             "thuộc mốc áp dụng.")
    product_categ_ids = fields.Many2many('product.category', string='Áp dụng cho Danh mục',
        help="Để trống nếu áp dụng cho tất cả danh mục")

    def check_eligibility(self, product):
        """Kiểm tra xem sản phẩm có được phép áp dụng giảm giá này không"""
        self.ensure_one()
        # Nếu đã chọn danh mục cụ thể thì phải thuộc danh mục đó
        if self.product_categ_ids and product.categ_id not in self.product_categ_ids:
            return False
        return True

    def compute_discount_for_product(self, product):
        """Tính giá trị chiết khấu cho một sản phẩm cụ thể."""
        self.ensure_one()
        if self.discount_type == 'percent':
            return product.list_price * self.discount_value / 100.0
        elif self.discount_type == 'amount':
            return self.discount_value
        elif self.discount_type == 'formula':
            if self.formula_type == 'management_fee':
                # Phí quản lý × Diện tích đất × Hệ số (số tháng)
                management_fee = product.management_fee or 0
                area = product.area or 0
                return management_fee * area * self.discount_value
            elif self.formula_type == 'maintenance_fee':
                # Phí bảo trì × Diện tích đất × Hệ số
                maintenance_fee = product.maintenance_fee or 0
                area = product.area or 0
                return maintenance_fee * area * self.discount_value
            else:
                # Custom - trả về giá trị mặc định
                return self.discount_value
        elif self.discount_type == 'percent_recalc':
            return self._compute_percent_recalc(product)
        return 0

    def _compute_percent_recalc(self, product):
        """Công thức % tính lại tổng giá:
            Giá bán sau   = round(price_exclude_land_tax × (100-qty)/100, -4)
            VAT sau       = 10% × Giá bán sau
            Quỹ BT sau    = round((Giá bán sau + land_tax) × 0.5%, -3)
            Tổng giá sau  = Giá bán sau + land_tax + VAT sau + Quỹ BT sau

        Trả về số tiền giảm = list_price (tổng gốc) − Tổng giá sau.
        """
        self.ensure_one()
        q = self.qty or 0.0
        if q <= 0 or q >= 100:
            return 0.0
        sale = product.price_exclude_land_tax or 0.0
        land = product.land_tax or 0.0
        list_price = product.list_price or 0.0
        new_sale  = round(sale * (100.0 - q) / 100.0, self.ROUND_SALE)
        new_vat   = 0.10 * new_sale
        new_maint = round((new_sale + land) * 0.005, self.ROUND_MAINT)
        new_total = new_sale + land + new_vat + new_maint
        return list_price - new_total

    def _chain_percent_recalc(self, product):
        """Áp các CK loại percent_recalc theo chuỗi đúng như sheet "CK GD2 SH":
        mỗi bước chỉ trừ vào giá nhà chưa TSDĐ rồi làm tròn bội 10.000; VAT 10%
        và quỹ bảo trì 0,5% dựng lại từ giá nhà của bước đó. Tiền sử dụng đất
        không bao giờ bị trừ.

        Trả về (tổng tiền giảm, {discount_id: tiền giảm biên của riêng đợt đó}).
        Phần biên phụ thuộc thứ tự: CK đứng sau tính trên giá đã giảm của CK
        đứng trước, nên tổng thì cố định còn từng dòng thì đổi theo sequence.
        """
        land = product.land_tax or 0.0
        list_price = product.list_price or 0.0

        def total_at(sale):
            maint = round((sale + land) * 0.005, self.ROUND_MAINT)
            return sale + land + 0.10 * sale + maint

        recs = self.filtered(
            lambda d: d.discount_type == 'percent_recalc' and 0 < (d.qty or 0) < 100
        ).sorted('sequence')
        if not recs:
            return 0.0, {}

        sale = product.price_exclude_land_tax or 0.0
        # Mốc đầu là tổng THẬT của sản phẩm (list_price) chứ không phải tổng
        # dựng lại từ giá gốc, để tổng các phần biên luôn khớp đúng
        # list_price - tổng cuối, không sinh sai số lẻ.
        prev_total = list_price
        marginal = {}
        for discount in recs:
            sale = round(sale * (100.0 - discount.qty) / 100.0, self.ROUND_SALE)
            cur_total = total_at(sale)
            marginal[discount.id] = prev_total - cur_total
            prev_total = cur_total
        return list_price - prev_total, marginal

    # Ký hiệu và mô tả ngắn của từng mốc — dùng chung cho portal, mẫu in và
    # màn cấu hình để ba nơi không mô tả lệch nhau.
    STAGE_CODE = {
        'ky_hop_dong': 'A',
        'spread': 'B',
        'giao_nha': 'C',
    }
    STAGE_HINT = {
        'ky_hop_dong': 'Trừ thẳng vào đợt Ký hợp đồng',
        'spread': 'Chia đều từ đợt 4 đến đợt Bàn giao nhà',
        'giao_nha': 'Trừ thẳng vào đợt Bàn giao nhà',
    }
    # Thứ tự hiển thị các nhóm: A -> B -> C, đúng trình tự tiền CK bị trừ trên lịch
    STAGE_ORDER = ('ky_hop_dong', 'spread', 'giao_nha')

    def group_by_stage(self):
        """Gom chiết khấu thành các nhóm A/B/C để portal và mẫu in kẻ dòng
        phân loại.

        Trả về list dict theo thứ tự A -> B -> C, bỏ qua nhóm rỗng:
            {'stage', 'code', 'hint', 'label', 'discounts'}

        Chiết khấu mang mốc lạ (dữ liệu cũ chưa chạy migration) được dồn vào
        một nhóm cuối không tên thay vì bị loại — mất dòng trên bảng giá thì
        khách không đối chiếu được số tiền.
        """
        ordered = self.sorted('sequence')
        groups = []
        for stage in self.STAGE_ORDER:
            discounts = ordered.filtered(lambda d: d.apply_stage == stage)
            if not discounts:
                continue
            code = self.STAGE_CODE.get(stage, '')
            hint = self.STAGE_HINT.get(stage, '')
            groups.append({
                'stage': stage,
                'code': code,
                'hint': hint,
                'label': ('Chiết khấu %s' % code) if code else 'Chiết khấu',
                'discounts': discounts,
            })
        others = ordered.filtered(lambda d: d.apply_stage not in self.STAGE_ORDER)
        if others:
            groups.append({
                'stage': False,
                'code': '',
                'hint': '',
                'label': 'Chiết khấu khác',
                'discounts': others,
            })
        return groups

    # Mốc mặc định của mọi chiết khấu là loại A (trừ thẳng vào đợt Ký HĐMB).
    # Trường apply_stage là bắt buộc, hằng số này chỉ còn là lưới an toàn cho
    # bản ghi cũ hoặc dữ liệu ghi thẳng bằng SQL.
    DEFAULT_APPLY_STAGE = 'ky_hop_dong'

    def get_schedule_discount_context(self, product):
        """Giá sau chiết khấu + tiền CK phân bổ theo mốc, dùng để dựng LỊCH THANH TOÁN.

        Quy tắc đã chốt với nghiệp vụ:
        - CK chỉ trừ vào GIÁ NHÀ CHƯA THUẾ SDĐ; tiền sử dụng đất không bao giờ bị trừ.
        - CK nhân chuỗi theo Thứ tự: CK B tính trên giá đã trừ CK A, CK C trên giá
          đã trừ CK B. Mỗi bước làm tròn giá nhà tới bội 10.000.
        - SỐ TIỀN CK TRỪ VÀO ĐỢT = đúng phần giá nhà bị cắt của CK đó (không gồm
          VAT, không gồm quỹ bảo trì).
        - VAT và quỹ bảo trì KHÔNG bị trừ vào đợt nào mà được TÍNH LẠI từ giá mới
          rồi đưa thẳng lên lịch: VAT = 10% × giá nhà mới,
          Quỹ bảo trì = làm tròn((giá nhà mới + TSDĐ) × 0,5%, bội 1.000).
        - MỌI loại CK đang chọn đều bị trừ vào lịch tại mốc của nó. Khác nhau ở
          chỗ chỉ percent_recalc mới kéo theo VAT và quỹ bảo trì tính lại; các
          loại percent/amount/formula chỉ trừ thẳng số tiền của nó, không đụng
          tới giá nhà nên không làm đổi VAT hay quỹ bảo trì.

        Trả về dict:
            sale            giá nhà chưa TSDĐ sau các CK % tính lại
            land            tiền sử dụng đất (không đổi)
            price_incl      sale + land
            other_cut       tổng CK loại trừ thẳng (không làm đổi giá nhà)
            schedule_price  price_incl − other_cut — tổng cột "Tiền nhà" của lịch
                            (chưa gồm dòng quỹ bảo trì)
            vat             tổng VAT sau CK
            maint           quỹ bảo trì sau CK
            by_stage        {mốc: tổng tiền CK trừ vào mốc đó}
            total_cut       tổng tiền CK trừ trên lịch (= tổng by_stage)
        """
        land = product.land_tax or 0.0
        sale = product.price_exclude_land_tax or 0.0

        recs = self.filtered(
            lambda d: d.discount_type == 'percent_recalc' and 0 < (d.qty or 0) < 100
        ).sorted('sequence')

        by_stage = {}
        for discount in recs:
            new_sale = round(sale * (100.0 - discount.qty) / 100.0, self.ROUND_SALE)
            stage = discount.apply_stage or self.DEFAULT_APPLY_STAGE
            by_stage[stage] = by_stage.get(stage, 0.0) + (sale - new_sale)
            sale = new_sale

        if recs:
            vat = 0.10 * sale
            maint = round((sale + land) * 0.005, self.ROUND_MAINT)
        else:
            # Không có CK % tính lại -> giữ nguyên số liệu nhập tay của sản phẩm,
            # không tự dựng lại VAT/quỹ bảo trì (tránh đổi lịch của hàng cũ).
            vat = product.vat_tax or 0.0
            maint = product.maintenance_fee or 0.0

        # CK loại trừ thẳng: cộng nguyên số tiền vào mốc của nó. Không tính lại
        # VAT/quỹ bảo trì vì các CK này không định nghĩa lại giá nhà.
        other_cut = 0.0
        for discount in self:
            if discount.discount_type == 'percent_recalc':
                continue
            amount = discount.compute_discount_for_product(product) or 0.0
            if not amount:
                continue
            stage = discount.apply_stage or self.DEFAULT_APPLY_STAGE
            by_stage[stage] = by_stage.get(stage, 0.0) + amount
            other_cut += amount

        return {
            'sale': sale,
            'land': land,
            'price_incl': sale + land,
            'other_cut': other_cut,
            'schedule_price': sale + land - other_cut,
            'vat': vat,
            'maint': maint,
            'by_stage': by_stage,
            'total_cut': sum(by_stage.values()),
        }

    def compute_discounts_for_product(self, product):
        """Điểm vào cho cả nhóm chiết khấu đang chọn: loại percent_recalc nhân
        chuỗi theo sequence, các loại khác (percent/amount/formula) cộng thẳng
        vì không phụ thuộc thứ tự.

        Trả về (tổng tiền giảm, {discount_id: tiền giảm}).
        """
        total, per_discount = self._chain_percent_recalc(product)
        for discount in self:
            if discount.discount_type == 'percent_recalc':
                continue
            amount = discount.compute_discount_for_product(product)
            per_discount[discount.id] = amount
            total += amount
        return total, per_discount
