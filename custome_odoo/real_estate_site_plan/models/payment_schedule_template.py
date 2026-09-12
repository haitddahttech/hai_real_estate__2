# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

import json
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class PaymentScheduleTemplate(models.Model):
    _name = 'payment.schedule.template'
    _description = 'Mẫu lịch thanh toán'
    _order = 'sequence, name'

    name = fields.Char(
        string='Tên lịch thanh toán',
        required=True,
        translate=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    product_category_ids = fields.Many2many(
        comodel_name='product.category',
        relation='payment_schedule_template_categ_rel',
        column1='template_id',
        column2='category_id',
        string='Danh mục sản phẩm áp dụng',
        help='Mẫu lịch này sẽ áp cho các sản phẩm thuộc các danh mục được chọn. '
             'Để trống nghĩa là KHÔNG áp cho danh mục nào.',
    )
    line_ids = fields.One2many(
        comodel_name='payment.schedule.template.line',
        inverse_name='template_id',
        string='Đợt thanh toán',
        copy=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        readonly=True,
    )
    total_percentage = fields.Float(
        string='Tổng % cấu hình',
        compute='_compute_totals',
        help='Tổng % của các dòng cấu hình theo % giá trị BĐS. Lý tưởng bằng 100%.',
    )
    line_count = fields.Integer(
        string='Số đợt',
        compute='_compute_totals',
    )

    @api.depends('line_ids.amount_type', 'line_ids.percentage')
    def _compute_totals(self):
        for tpl in self:
            tpl.line_count = len(tpl.line_ids)
            tpl.total_percentage = sum(
                l.percentage for l in tpl.line_ids if l.amount_type == 'percentage'
            )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('product_category_ids')
    def _check_category_uniqueness(self):
        """Mỗi product.category chỉ được nằm trong 1 lịch thanh toán duy nhất."""
        for tpl in self:
            if not tpl.product_category_ids:
                continue
            others = self.search([
                ('id', '!=', tpl.id),
                ('product_category_ids', 'in', tpl.product_category_ids.ids),
            ])
            for other in others:
                conflicts = tpl.product_category_ids & other.product_category_ids
                if conflicts:
                    raise ValidationError(_(
                        "Danh mục \"%(cat)s\" đã được dùng trong lịch thanh toán \"%(tpl)s\". "
                        "Mỗi danh mục chỉ được nằm trong 1 lịch thanh toán."
                    ) % {
                        'cat': conflicts[0].display_name,
                        'tpl': other.display_name,
                    })

    # ------------------------------------------------------------------
    # Action button: regenerate timelines for all products in categories
    # ------------------------------------------------------------------
    def action_regenerate_timelines(self):
        """Cập nhật lịch thanh toán mới cho tất cả product.template thuộc
        các product.category đã chọn của template này."""
        self.ensure_one()
        if not self.product_category_ids:
            raise UserError(_(
                "Template chưa chọn danh mục sản phẩm nào. "
                "Vui lòng chọn danh mục trước khi cập nhật."
            ))
        if not self.line_ids:
            raise UserError(_("Template chưa có dòng đợt thanh toán nào."))

        products = self.env['product.template'].search([
            ('categ_id', 'child_of', self.product_category_ids.ids),
        ])
        if not products:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Không có sản phẩm"),
                    'message': _("Không tìm thấy sản phẩm nào trong danh mục đã chọn."),
                    'type': 'warning',
                    'sticky': False,
                },
            }

        for product in products:
            self._generate_timelines_for_product(product)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Cập nhật thành công"),
                'message': _("Đã cập nhật lịch thanh toán cho %s sản phẩm.") % len(products),
                'type': 'success',
                'sticky': False,
            },
        }

    # Vị trí trừ tiền CK trên lịch — chốt với nghiệp vụ:
    #   ky_hop_dong (A) -> trừ thẳng vào đợt Ký hợp đồng
    #   spread      (B) -> chia đều từ đợt kế tiếp (Đợt 4) đến đợt Bàn giao nhà
    #   giao_nha    (C) -> trừ thẳng vào đợt Bàn giao nhà
    ROUND_DISCOUNT_SPLIT = -3  # chia đều làm tròn bội 1.000, dư dồn vào đợt cuối

    def _apply_schedule_discounts(self, vals_list, disc_ctx, currency):
        """Trừ tiền chiết khấu vào các đợt của `vals_list` (sửa tại chỗ).

        Với CK loại "% tính lại tổng giá": số tiền trừ chỉ là phần GIÁ NHÀ CHƯA
        THUẾ SDĐ bị cắt — VAT và quỹ bảo trì đã được dựng lại theo giá mới ngay
        khi sinh từng đợt nên không trừ lại ở đây (trừ nữa là trùng).
        Với các loại CK còn lại: trừ thẳng nguyên số tiền của CK đó.

        Nhờ vậy tổng lịch luôn khớp đúng final_price của sản phẩm.
        """
        by_stage = {k: v for k, v in (disc_ctx.get('by_stage') or {}).items() if v}
        if not by_stage:
            return

        self._cut_discount_by_stage(vals_list, by_stage, currency)

        # Tiền CK dồn vào một mốc có thể lớn hơn chính đợt đó (CK to, đợt nhỏ).
        # Không tự động san sang đợt khác vì mốc là do nghiệp vụ chốt — chỉ ghi
        # log để người cấu hình biết mà đổi mốc áp dụng.
        for vals in vals_list:
            if vals['amount'] < 0:
                _logger.warning(
                    "Lich thanh toan: dot '%s' bi am (%s) sau khi tru chiet khau %s "
                    "- can xem lai Moc ap dung cua chuong trinh chiet khau.",
                    vals.get('type_name') or vals.get('type'),
                    vals['amount'], vals.get('discount_amount'),
                )

    def _cut_discount_by_stage(self, vals_list, by_stage, currency):
        """Trừ từng khoản trong `by_stage` vào đúng đợt tương ứng."""
        codes = [vals['type'] for vals in vals_list]

        def index_of(code):
            return codes.index(code) if code in codes else -1

        def cut(pos, amount):
            if pos < 0 or not amount:
                return
            vals = vals_list[pos]
            vals['amount'] = currency.round(vals['amount'] - amount)
            vals['discount_amount'] = currency.round(vals.get('discount_amount', 0.0) + amount)

        ky_idx = index_of('ky_hop_dong')
        # Đợt Bàn giao nhà: ưu tiên cờ "Là đợt bàn giao nhà" trên mẫu lịch, chỉ
        # khi không mẫu nào tick mới dò theo mã 'giao_nha' như trước.
        handover_positions = [
            i for i, vals in enumerate(vals_list) if vals.get('is_handover')
        ]
        giao_idx = handover_positions[0] if handover_positions else index_of('giao_nha')
        # Mốc không tồn tại trên template thì dồn vào đợt Bàn giao nhà, cuối cùng
        # mới đến đợt cuối bảng — cốt để tổng lịch không bị hụt tiền CK.
        fallback_idx = giao_idx if giao_idx >= 0 else len(vals_list) - 1

        for stage, amount in by_stage.items():
            if stage == 'spread':
                continue
            # Mốc C của chương trình CK trỏ tới đợt Bàn giao nhà -> dùng chính
            # đợt đã đánh dấu ở trên, không dò lại theo mã.
            pos = giao_idx if stage == 'giao_nha' else index_of(stage)
            cut(pos if pos >= 0 else fallback_idx, amount)

        spread_total = by_stage.get('spread') or 0.0
        if not spread_total:
            return

        # Dải "từ đợt kế tiếp Ký HĐ đến hết đợt Bàn giao nhà". Các đợt bị gộp do
        # quá hạn đã biến mất khỏi vals_list nên phần chia đều tự động rải trên
        # đúng số đợt còn hiển thị.
        start = ky_idx + 1 if ky_idx >= 0 else 0
        end = giao_idx if giao_idx >= 0 else len(vals_list) - 1
        targets = [
            i for i in range(start, end + 1)
            if 0 <= i < len(vals_list)
            and vals_list[i]['type'] not in ('quy_bao_tri', 'thong_bao_so_hong')
        ]
        if not targets:
            cut(fallback_idx, spread_total)
            return

        share = round(spread_total / len(targets), self.ROUND_DISCOUNT_SPLIT)
        for i in targets[:-1]:
            cut(i, share)
        # Đợt cuối của dải gánh phần dư để tổng trừ đúng bằng tiền CK
        cut(targets[-1], spread_total - share * (len(targets) - 1))

    def _apply_bank_splits(self, vals_list, split_specs, bank_price_base,
                           vat_base, maint_base, currency):
        """Áp cấu hình "chia ô Hỗ trợ ngân hàng" lên các dòng lịch vừa sinh.

        Mỗi khối ứng với ĐÚNG MỘT hàng của bảng lịch, đếm từ chính hàng mang
        cấu hình trở xuống: "35:10" -> 2 khối -> ô gộp phủ 2 hàng (rowspan=2).
        Tiền của khối thứ i:

            giá nhà gồm TSDĐ × %i  +  VAT × %VAT_i
            ( + quỹ bảo trì, nếu hàng tương ứng chính là đợt Quỹ bảo trì )

        Số tiền này GHI ĐÈ bank_amount của từng hàng bị phủ — nhờ vậy tổng cột
        ngân hàng vẫn cộng đúng dù trên bảng chúng hiển thị gộp thành một ô.
        """
        for idx, line in split_specs:
            blocks = line._get_bank_split()
            if not blocks:
                continue

            # Cuối bảng có thể không còn đủ hàng để phủ (đợt sau đã bị gộp vì
            # quá hạn) — thu hẹp lại theo số hàng thực có, không tràn rowspan.
            size = min(len(blocks), len(vals_list) - idx)
            if size <= 0:
                continue

            payload = []
            for offset in range(size):
                share, vat_share, label = blocks[offset]
                row = vals_list[idx + offset]
                amount = currency.round(
                    bank_price_base * share / 100.0
                    + vat_base * vat_share / 100.0
                )
                # Quỹ bảo trì do khách nộp thẳng, cộng vào đúng khối của nó.
                if row.get('type') == 'quy_bao_tri':
                    amount += maint_base
                row['bank_amount'] = amount
                row['bank_split_covered'] = offset > 0
                # Ô gộp của khối là nguồn duy nhất cho cả dải này: gỡ cờ nhóm
                # bank_group để hai cơ chế rowspan không chồng lên nhau (nếu
                # không, hàng bị phủ mà lại mở nhóm sẽ để lại lỗ trống ô).
                row['bank_group'] = ''
                row['is_merge_title'] = False
                payload.append({'amount': amount, 'label': label})

            head = vals_list[idx]
            head['bank_split_json'] = json.dumps(payload)
            head['bank_split_size'] = size

    def _build_timeline_vals(self, product, discounts=None):
        """Dựng danh sách vals của các đợt thanh toán — KHÔNG chạm cơ sở dữ liệu.

        Đây là toàn bộ phần TÍNH của lịch thanh toán, tách khỏi phần GHI để
        dùng được cho hai mục đích khác nhau:
        - `_generate_timelines_for_product()` lấy kết quả rồi lưu vào DB (lịch
          GỐC của sản phẩm, hiển thị ở màn backend).
        - `product.template.get_display_timelines()` dựng bản ghi ẢO trong bộ
          nhớ để portal và mẫu in hiển thị lịch ĐÃ ÁP chiết khấu người xem đang
          tích, mà không ghi gì xuống DB — chiết khấu là mô phỏng lúc xem, không
          phải trạng thái vĩnh viễn của sản phẩm.

        `discounts` là recordset product.discount.config dùng để tính; để None
        thì lấy chiết khấu đã lưu trên sản phẩm.

        Áp dụng logic gộp (is_mergeable) tương tự compute_payment_timeline cũ,
        nhưng đọc cấu hình từ template.

        Special-case theo `code` để giữ tương thích nghiệp vụ cũ:
        - dat_coc + fixed_amount=0    -> dùng product.deposit
        - trong_3_ngay (%)            -> trừ tiền product.deposit (5% trừ cọc)
        - ky_hop_dong (%)             -> trừ paid_amount tích lũy (bù cho đủ %)
        - quy_bao_tri + fixed=0       -> dùng product.maintenance_fee
        - quy_bao_tri                 -> bank cộng thêm maintenance_fee
        """
        self.ensure_one()
        currency = self.env.company.currency_id
        company = self.env.company

        # Giá & tiền CK dùng cho lịch. Lịch được dựng trên GIÁ GỐC (chưa CK),
        # tiền CK chỉ bị trừ tại đúng các mốc đã chốt (xem _apply_schedule_discounts).
        # Riêng VAT và quỹ bảo trì thì không trừ theo mốc mà lấy thẳng số đã
        # tính lại theo giá sau CK.
        disc_ctx = product._get_schedule_discount_context(discounts)
        vat_base = disc_ctx['vat']
        maint_base = disc_ctx['maint']
        # Cột "Hỗ trợ ngân hàng" bám theo giá thực khách phải trả, nếu không tổng
        # cột ngân hàng sẽ lệch với tổng tiền nhà sau CK.
        bank_price_base = (
            disc_ctx['schedule_price'] if disc_ctx['total_cut']
            else product.price_include_land_tax
        )

        deposit_date = product.deposit_date or fields.Date.today()
        if product.site_plan_polygon_ids:
            fixed_anchor = (
                product.site_plan_polygon_ids[0].site_plan_id.deposit_date
                or deposit_date
            )
        else:
            fixed_anchor = deposit_date

        # Marker = NGÀY HIỆN TẠI (không phải ngày ký HĐ giả tạo như logic cũ).
        # Một đợt bị gộp khi line_date < today, hoặc khoảng cách < nearby_day.
        today_marker = fields.Date.today()
        nearby_day = company.nearby_day or 0

        early_codes = ('dat_coc', 'trong_3_ngay', 'ky_hop_dong')

        # Tô nền dòng / ô ngân hàng nay CHẠY HOÀN TOÀN theo cấu hình
        # (highlight_row / highlight_bank_cell) — không còn nền mặc định theo mã
        # đợt. legacy_hl chỉ còn dùng cho MỐC BÀN GIAO: lịch cũ chưa tick cờ nào
        # thì vẫn suy đợt 'giao_nha' làm mốc bàn giao để không lệch tiền chiết khấu.
        legacy_hl = not any(
            l.highlight_row or l.highlight_bank_cell for l in self.line_ids
        )

        paid_amount = 0.0
        acc_amount = acc_vat = acc_bank = 0.0
        # Cờ của các đợt bị gộp: dồn sang đợt kế tiếp cùng với tiền, nếu không
        # một đợt Bàn giao nhà quá hạn bị gộp sẽ làm lịch mất mốc bàn giao.
        acc_handover = acc_hl_row = acc_hl_bank = False
        acc_share = 0.0  # % tích lũy cho mô tả "X% +VAT tương ứng"
        # Hàng đợi NHÃN HIỂN THỊ của các đợt mergeable đã đi qua.
        # Khi 1 đợt bị gộp, nhãn của nó KHÔNG mất đi mà được đẩy xuống cho
        # dòng kế tiếp, nên số đợt còn lại luôn liên tục từ đầu nhóm:
        # 3-4-5-6, gộp 3 vào 4  ->  hiển thị 3-4-5 (không phải 4-5-6).
        # Hàng đợi này CHỈ ảnh hưởng type_name; cột `type` luôn giữ mã thật.
        pending_labels = []
        pending_group = None
        vals_list = []
        # (index trong vals_list, line) cua nhung dot co cau hinh chia o ngan hang.
        # Phai ghi lai index THAT vi cac dot qua han bi gop se bien mat khoi
        # vals_list, khong the suy ra tu thu tu line_ids.
        split_specs = []

        for line in self.line_ids.sorted('sequence'):
            line_share = (line.percentage or 0.0) if line.amount_type == 'percentage' else 0.0

            # ---- LABEL QUEUE: chỉ dịch nhãn trong cùng 1 nhóm mergeable ----
            line_group = line.group_merge if line.is_mergeable else None
            if not line.is_mergeable or line_group != pending_group:
                pending_labels = []
                pending_group = line_group

            # ---- DATE ----
            if line.date_type == 'fixed':
                line_date = line.fixed_date
            elif line.date_type == 'no_date':
                line_date = False
            else:
                base = deposit_date if line.code in early_codes else fixed_anchor
                line_date = base + relativedelta(
                    months=line.offset_months or 0,
                    days=line.offset_days or 0,
                )

            # ---- AMOUNT (giá nhà) ----
            if line.amount_type == 'fixed':
                amount = line.fixed_amount or 0.0
                if not amount and line.code == 'dat_coc':
                    amount = product.deposit or 0.0
                elif not amount and line.code == 'quy_bao_tri':
                    amount = maint_base
            else:
                amount = currency.round(
                    product.price_include_land_tax * (line.percentage or 0.0) / 100.0
                )
                if line.code == 'trong_3_ngay':
                    amount = amount - (product.deposit or 0.0)
                elif line.code == 'ky_hop_dong':
                    amount = amount - paid_amount

            paid_amount += amount

            # ---- VAT ----
            vat_amount = currency.round(
                vat_base * (line.vat_share or 0.0) / 100.0
            ) if line.vat_share else 0.0

            # ---- BANK ----
            bank_amount = currency.round(
                bank_price_base * (line.bank_share or 0.0) / 100.0
                + vat_base * (line.bank_vat_share or 0.0) / 100.0
            )
            if line.code == 'quy_bao_tri':
                bank_amount += maint_base

            # ---- CỜ HIỂN THỊ / MỐC BÀN GIAO ----
            line_handover = line.is_handover or (legacy_hl and line.code == 'giao_nha')
            # Tô nền HOÀN TOÀN theo cấu hình: không còn nền mặc định theo mã đợt.
            line_hl_row = line.highlight_row
            line_hl_bank = line.highlight_bank_cell

            # ---- MERGE (gộp dữ liệu theo ngày) ----
            if line.is_mergeable and line.is_merge_by_date and line_date:
                days_gap = (line_date - today_marker).days
                if line_date < today_marker or (nearby_day > 0 and days_gap < nearby_day):
                    acc_amount += amount
                    acc_vat += vat_amount
                    acc_bank += bank_amount
                    acc_share += line_share
                    acc_handover = acc_handover or line_handover
                    acc_hl_row = acc_hl_row or line_hl_row
                    acc_hl_bank = acc_hl_bank or line_hl_bank
                    # Giữ nhãn đợt bị gộp để dòng kế tiếp dùng lại
                    pending_labels.append((line.code or '', line.name or ''))
                    continue  # khong tao record cho dot nay, gop vao dot ke

            # ---- NAME (mô tả "Số tiền thanh toán") ----
            # Cột này hiển thị HOW MUCH ("5%", "Đủ 20% +VAT"...), KHÔNG phải tên đợt.
            if line.amount_type == 'fixed':
                name_str = line.name  # Fixed amount: dùng tên đợt làm mô tả
            elif line.code == 'ky_hop_dong':
                name_str = "Đủ %g%% +VAT" % (line.percentage or 0)
            elif line.code == 'giao_nha':
                name_str = "%g%% +VAT còn lại" % (line.percentage or 0)
            elif line.code == 'quy_bao_tri':
                name_str = "%g%%" % (line.percentage or 0.5)
            elif line.is_mergeable:
                # Đợt mergeable: hiển thị cumulative % (gồm tích lũy nếu vừa drain merge).
                # Chỉ gắn đuôi "+VAT tương ứng" khi đợt này thực sự có VAT.
                suffix = " +VAT tương ứng" if vat_amount else ""
                name_str = "%g%%%s" % (acc_share + line_share, suffix)
            else:
                name_str = "%g%%" % (line.percentage or 0)

            # ---- LABEL hiển thị: dùng nhãn sớm nhất còn treo trong nhóm ----
            # CHỈ cái nhãn mới bị dịch, để số đợt còn lại liên tục từ đầu nhóm
            # (3-4-5-6, gộp 3 vào 4 -> hiển thị 3-4-5). Cột `type` KHÔNG được
            # dịch theo: nó là KHOÁ MÁY, dùng để tìm đợt Ký HĐ / Bàn giao nhà
            # khi trừ tiền chiết khấu (_cut_discount_by_stage), để loại đợt
            # Quỹ bảo trì khỏi dải chia đều, và để tô nền dòng trên bảng lịch.
            # Dịch cả `type` thì một lịch có đợt bị gộp sẽ không còn dòng nào
            # mang type 'ky_hop_dong', khiến CK mốc A rơi nhầm sang đợt Bàn
            # giao nhà theo nhánh dự phòng.
            if pending_labels:
                _shifted_code, row_name = pending_labels.pop(0)
                pending_labels.append((line.code or '', line.name or ''))
            else:
                row_name = line.name or ''

            # ---- CREATE record (cộng dồn tích lũy nếu có) ----
            vals_list.append({
                'product_tmpl_id': product.id,
                # Bản ghi ẢO (.new) không được áp giá trị mặc định của trường,
                # nên phải ghi tiền tệ ra đây — thiếu nó thì Monetary bỏ qua
                # bước làm tròn và số trên portal lệch với số lưu trong DB.
                'currency_id': currency.id,
                # Mã THẬT của đợt này (khoá máy), không phải nhãn đã dịch.
                'type': line.code or '',
                'type_name': row_name,
                'date': line_date,
                'name': name_str,
                'amount': amount + acc_amount,
                'vat_amount': vat_amount + acc_vat,
                'bank_amount': bank_amount + acc_bank,
                'discount_amount': 0.0,
                'bank_note': line.note or '',
                'bank_group': line.group_merge or '' if line.is_mergeable else '',
                'is_merge_title': line.is_merge_title if line.is_mergeable else False,
                'is_handover': line_handover or acc_handover,
                'highlight_row': line_hl_row or acc_hl_row,
                'highlight_bank_cell': line_hl_bank or acc_hl_bank,
            })
            if (line.bank_split_ratio or '').strip():
                split_specs.append((len(vals_list) - 1, line))
            acc_amount = acc_vat = acc_bank = 0.0
            acc_handover = acc_hl_row = acc_hl_bank = False
            acc_share = 0.0

        # Nếu vẫn còn tích lũy (toàn bộ trailing lines đều mergeable + quá hạn)
        # thì dồn vào dòng cuối cùng đã tạo
        if vals_list and (acc_amount or acc_vat or acc_bank
                          or acc_handover or acc_hl_row or acc_hl_bank):
            last_vals = vals_list[-1]
            last_vals['amount'] += acc_amount
            last_vals['vat_amount'] += acc_vat
            last_vals['bank_amount'] += acc_bank
            last_vals['is_handover'] = last_vals['is_handover'] or acc_handover
            last_vals['highlight_row'] = last_vals['highlight_row'] or acc_hl_row
            last_vals['highlight_bank_cell'] = (
                last_vals['highlight_bank_cell'] or acc_hl_bank
            )

        # Chia ô "Hỗ trợ ngân hàng" thành nhiều khối theo cấu hình trên đợt
        self._apply_bank_splits(
            vals_list, split_specs, bank_price_base, vat_base, maint_base, currency,
        )

        # Trừ tiền chiết khấu vào đúng các mốc đã chốt
        self._apply_schedule_discounts(vals_list, disc_ctx, currency)

        return vals_list

    def _generate_timelines_for_product(self, product):
        """Ghi lịch thanh toán GỐC của sản phẩm xuống DB (xoá rồi tạo lại).

        Lịch lưu trong DB luôn là lịch theo chiết khấu ĐÃ LƯU trên sản phẩm —
        thường là không có chiết khấu nào. Chiết khấu người xem tích trên portal
        KHÔNG đi qua đây: chúng chỉ được dựng trong bộ nhớ lúc hiển thị (xem
        product.template.get_display_timelines).
        """
        vals_list = self._build_timeline_vals(product)
        product.payment_timeline_ids.unlink()
        product.write({'payment_timeline_ids': [(0, 0, vals) for vals in vals_list]})


class PaymentScheduleTemplateLine(models.Model):
    _name = 'payment.schedule.template.line'
    _description = 'Đợt trong mẫu lịch thanh toán'
    _order = 'template_id, sequence, id'

    template_id = fields.Many2one(
        comodel_name='payment.schedule.template',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(
        string='Tên kỳ thanh toán',
        required=True,
        translate=True,
        help='Ví dụ: Đặt cọc, Đợt 4, Giao nhà...',
    )
    code = fields.Char(
        string='Mã',
        help='Mã định danh kỹ thuật (vd: dat_coc, dot_4). Tuỳ chọn — dùng cho tích hợp.',
    )

    # --- Ngày thanh toán ---
    date_type = fields.Selection(
        selection=[
            ('offset', 'Số tháng/ngày kể từ ngày đặt cọc'),
            ('fixed', 'Ngày cố định'),
            ('no_date', 'Không xác định'),
        ],
        string='Loại ngày',
        default='offset',
        required=True,
    )
    offset_months = fields.Integer(string='Số tháng', default=0)
    offset_days = fields.Integer(string='Số ngày', default=0)
    fixed_date = fields.Date(string='Ngày cố định')

    # --- Số tiền ---
    amount_type = fields.Selection(
        selection=[
            ('percentage', '% giá trị BĐS'),
            ('fixed', 'Số tiền cố định'),
        ],
        string='Loại số tiền',
        default='percentage',
        required=True,
    )
    percentage = fields.Float(
        string='% giá trị',
        digits=(7, 4),
        help='Nhập 5 nghĩa là 5%. Chỉ dùng khi "Loại số tiền" = %.',
    )
    fixed_amount = fields.Monetary(
        string='Số tiền',
        currency_field='currency_id',
        help='Số tiền cố định. Chỉ dùng khi "Loại số tiền" = cố định.',
    )
    vat_share = fields.Float(
        string='% VAT',
        digits=(7, 4),
        help='Phần trăm VAT khách trả cho đợt này. '
             'Vd Giao nhà có thể là 50% mặc dù giá nhà chỉ 45%.',
    )
    bank_share = fields.Float(
        string='% NH (giá nhà)',
        digits=(7, 4),
        help='Phần trăm giá nhà được ngân hàng hỗ trợ ở đợt này. '
             'Cộng vào "Tiền ngân hàng hỗ trợ" trên dòng lịch.',
    )
    bank_vat_share = fields.Float(
        string='% NH (VAT)',
        digits=(7, 4),
        help='Phần trăm VAT được ngân hàng hỗ trợ ở đợt này.',
    )

    # --- Chia ô "Hỗ trợ ngân hàng" thành nhiều khối ---
    # Thay cho case đặc biệt merge_qbt (gộp cứng hàng Quỹ bảo trì với hàng ngay
    # trước nó): khai báo thẳng trên đợt muốn gộp, mỗi khối ứng với đúng một
    # hàng của bảng lịch tính từ hàng mang cấu hình trở xuống.
    bank_split_ratio = fields.Char(
        string='Tỷ lệ chia ô NH',
        help='Chia ô "Hỗ trợ ngân hàng" của đợt này thành nhiều khối, ngăn nhau '
             'bằng dấu ":". Mỗi số là % giá nhà bao gồm TSDĐ của khối đó.\n'
             'Vd "35:10" -> 2 khối -> ô gộp phủ 2 hàng (rowspan=2).\n'
             'Để trống = không chia, ô hiển thị như cũ theo "% NH (giá nhà)".',
    )
    bank_split_vat_ratio = fields.Char(
        string='Tỷ lệ chia ô NH (VAT)',
        help='% VAT của từng khối, phải cùng số phần với "Tỷ lệ chia ô NH". '
             'Vd "40:10".\n'
             'Để trống thì mỗi khối dùng luôn % giá nhà của chính nó.',
    )
    bank_split_label = fields.Char(
        string='Label chia ô NH',
        translate=True,
        help='Chú thích hiển thị dưới số tiền của từng khối, ngăn nhau bằng ":". '
             'Vd "NGÂN HÀNG 35%:KH 10%".',
    )
    currency_id = fields.Many2one(
        related='template_id.currency_id',
        readonly=True,
    )

    # --- Flags hành vi ---
    is_mergeable = fields.Boolean(
        string='Cho phép gộp đợt',
        default=True,
        help='Khi đến lúc sinh lịch, nếu đợt này đã quá hạn hoặc gần ngày ký HĐ '
             '(theo cấu hình "nearby_day" của công ty) thì gộp tiền vào đợt kế tiếp.',
    )
    group_merge = fields.Selection(
        selection=[
            ('1', 'Nhóm 1'),
            ('2', 'Nhóm 2'),
            ('3', 'Nhóm 3'),
            ('4', 'Nhóm 4'),
            ('5', 'Nhóm 5'),
        ],
        string='Nhóm gộp NH',
        help='Các đợt cùng nhóm sẽ được gộp cột "Hỗ trợ ngân hàng" trên bảng lịch thanh toán. '
             'Chỉ áp dụng khi "Cho phép gộp đợt" được bật.',
    )
    is_merge_by_date = fields.Boolean(
        string='Gộp theo ngày TT',
        default=True,
        help='Khi bật, nếu ngày thanh toán đã quá hạn hoặc gần ngày ký HĐ '
             '(theo cấu hình "nearby_day") thì gộp tiền vào đợt kế tiếp.\n'
             'Tắt để giữ nguyên từng dòng (chỉ gộp cột ngân hàng nếu cùng nhóm).',
    )
    is_merge_title = fields.Boolean(
        string='Gộp tiêu đề',
        default=False,
        help='Mặc định chỉ gộp 2 cột con của "Hỗ trợ ngân hàng". '
             'Bật để gộp toàn bộ dòng thành 1 hàng.',
    )
    note = fields.Char(
        string='Ghi chú',
        translate=True,
        help='Vd: "KH 20%", "NGÂN HÀNG 35%"...',
    )

    # --- Đợt bàn giao nhà + tô nền trên bảng lịch thanh toán ---
    is_handover = fields.Boolean(
        string='Là đợt bàn giao nhà',
        default=False,
        help='Đánh dấu đợt Bàn giao nhà của lịch này. Dùng làm mốc trừ chiết khấu '
             '(mốc C "CK tại thời điểm Bàn Giao Nhà" và điểm cuối của dải chia đều) '
             'thay cho việc dò theo mã "giao_nha".',
    )
    highlight_row = fields.Boolean(
        string='Tô nền cả dòng',
        default=False,
        help='Tô nền vàng nhạt toàn bộ dòng của đợt này trên bảng lịch thanh toán '
             '(portal và bản in PDF).',
    )
    highlight_bank_cell = fields.Boolean(
        string='Tô nền ô Hỗ trợ ngân hàng',
        default=False,
        help='Tô nền vàng đậm ô cuối dòng — cột "Hỗ trợ ngân hàng" — của đợt này '
             'trên bảng lịch thanh toán.',
    )

    # ------------------------------------------------------------------
    # Chia ô "Hỗ trợ ngân hàng"
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_split_numbers(raw):
        """'35:10' -> [35.0, 10.0]. Chuỗi rỗng -> []. Sai định dạng -> ValueError."""
        if not raw or not raw.strip():
            return []
        numbers = []
        for chunk in raw.split(':'):
            chunk = chunk.strip().replace(',', '.')
            if not chunk:
                raise ValueError(raw)
            numbers.append(float(chunk))
        return numbers

    def _get_bank_split(self):
        """Các khối của ô "Hỗ trợ ngân hàng" cho đợt này.

        Trả về [(pct_gia_nha, pct_vat, label), ...], hoặc [] nếu đợt này không
        cấu hình chia ô. Cấu hình sai định dạng cũng trả [] — ràng buộc
        _check_bank_split đã chặn từ lúc lưu, ở đây chỉ cần không làm hỏng
        việc sinh lịch.
        """
        self.ensure_one()
        try:
            shares = self._parse_split_numbers(self.bank_split_ratio)
        except ValueError:
            return []
        if not shares:
            return []

        try:
            vat_shares = self._parse_split_numbers(self.bank_split_vat_ratio)
        except ValueError:
            vat_shares = []
        if not vat_shares:
            # Để trống ô VAT: mỗi khối dùng luôn % giá nhà của chính nó.
            vat_shares = list(shares)

        labels = (self.bank_split_label or '').split(':')
        return [
            (
                share,
                vat_shares[i] if i < len(vat_shares) else share,
                labels[i].strip() if i < len(labels) else '',
            )
            for i, share in enumerate(shares)
        ]

    @api.constrains('bank_split_ratio', 'bank_split_vat_ratio', 'bank_split_label')
    def _check_bank_split(self):
        for line in self:
            if not (line.bank_split_ratio or '').strip():
                continue
            try:
                shares = self._parse_split_numbers(line.bank_split_ratio)
            except ValueError:
                raise ValidationError(_(
                    'Đợt "%(name)s": "Tỷ lệ chia ô NH" phải là các số ngăn nhau bằng '
                    'dấu ":", ví dụ "35:10". Giá trị hiện tại: "%(val)s".'
                ) % {'name': line.name, 'val': line.bank_split_ratio})

            try:
                vat_shares = self._parse_split_numbers(line.bank_split_vat_ratio)
            except ValueError:
                raise ValidationError(_(
                    'Đợt "%(name)s": "Tỷ lệ chia ô NH (VAT)" phải là các số ngăn nhau '
                    'bằng dấu ":", ví dụ "40:10". Giá trị hiện tại: "%(val)s".'
                ) % {'name': line.name, 'val': line.bank_split_vat_ratio})

            if vat_shares and len(vat_shares) != len(shares):
                raise ValidationError(_(
                    'Đợt "%(name)s": "Tỷ lệ chia ô NH (VAT)" có %(got)s phần nhưng '
                    '"Tỷ lệ chia ô NH" có %(want)s phần — hai ô phải cùng số phần '
                    '(hoặc để trống ô VAT).'
                ) % {'name': line.name, 'got': len(vat_shares), 'want': len(shares)})

            if line.bank_split_label:
                labels = line.bank_split_label.split(':')
                if len(labels) != len(shares):
                    raise ValidationError(_(
                        'Đợt "%(name)s": "Label chia ô NH" có %(got)s phần nhưng '
                        '"Tỷ lệ chia ô NH" có %(want)s phần — hai ô phải cùng số phần.'
                    ) % {'name': line.name, 'got': len(labels), 'want': len(shares)})

    @api.onchange('date_type')
    def _onchange_date_type(self):
        if self.date_type != 'offset':
            self.offset_months = 0
            self.offset_days = 0
        if self.date_type != 'fixed':
            self.fixed_date = False

    @api.onchange('amount_type')
    def _onchange_amount_type(self):
        if self.amount_type != 'percentage':
            self.percentage = 0.0
        if self.amount_type != 'fixed':
            self.fixed_amount = 0.0
