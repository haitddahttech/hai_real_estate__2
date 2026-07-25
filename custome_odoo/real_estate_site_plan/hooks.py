# -*- coding: utf-8 -*-
"""System-level setup that must travel WITH the module.

Khi module được cài/ update trên bất kỳ server nào (kể cả server chính),
`post_init_hook` sẽ tự copy các font thương hiệu Hồng Hạc City vào thư mục
font của hệ thống rồi refresh fontconfig cache. Nhờ đó các report xuất PDF/ảnh
(wkhtmltopdf / wkhtmltoimage — vốn đọc font từ HỆ THỐNG, không đọc @font-face của
web) render đúng font Fahkwang / VÉN.

Thiết kế idempotent + không bao giờ làm hỏng quá trình install/update:
- Thử lần lượt nhiều thư mục font (user-level trước, system-level sau) và dừng
  ở nơi đầu tiên ghi được → không cần quyền root.
- Chỉ copy khi file thiếu hoặc khác kích thước.
- Mọi lỗi đều nuốt + log, không raise.
"""

import glob
import logging
import os
import shutil
import subprocess

from odoo.modules.module import get_module_path

_logger = logging.getLogger(__name__)

MODULE_NAME = 'real_estate_site_plan'
# Thư mục con để gom font của brand, tránh đụng font khác của hệ thống.
FONT_SUBDIR = 'honghac_brand'


def _candidate_font_dirs():
    """Danh sách thư mục đích theo thứ tự ưu tiên (user-level → system-level)."""
    dirs = []
    home = os.path.expanduser('~')
    if home and home != '~':
        dirs.append(os.path.join(home, '.local', 'share', 'fonts', FONT_SUBDIR))
        dirs.append(os.path.join(home, '.fonts', FONT_SUBDIR))
    # System-level (thường cần quyền ghi cao hơn — chỉ dùng nếu user-level fail).
    dirs.append(os.path.join('/usr/local/share/fonts', FONT_SUBDIR))
    dirs.append(os.path.join('/usr/share/fonts/truetype', FONT_SUBDIR))
    return dirs


def _source_font_files():
    module_path = get_module_path(MODULE_NAME)
    if not module_path:
        _logger.warning('[HongHac fonts] Không tìm thấy đường dẫn module, bỏ qua cài font.')
        return []
    src_dir = os.path.join(module_path, 'static', 'src', 'fonts')
    files = sorted(glob.glob(os.path.join(src_dir, '*.ttf')))
    files += sorted(glob.glob(os.path.join(src_dir, '*.otf')))
    if not files:
        _logger.warning('[HongHac fonts] Không có file font nào trong %s', src_dir)
    return files


def install_brand_fonts():
    """Copy font brand vào hệ thống + refresh cache. Trả về thư mục đã cài (hoặc None)."""
    font_files = _source_font_files()
    if not font_files:
        return None

    installed_dir = None
    for target in _candidate_font_dirs():
        try:
            os.makedirs(target, exist_ok=True)
            copied = 0
            for src in font_files:
                dest = os.path.join(target, os.path.basename(src))
                if (not os.path.exists(dest)
                        or os.path.getsize(dest) != os.path.getsize(src)):
                    shutil.copy2(src, dest)
                    copied += 1
            installed_dir = target
            _logger.info('[HongHac fonts] Đã đồng bộ %d/%d font vào %s',
                         copied, len(font_files), target)
            break
        except (OSError, PermissionError) as err:
            _logger.info('[HongHac fonts] Không ghi được %s (%s) — thử thư mục kế tiếp.',
                         target, err)
            continue

    if not installed_dir:
        _logger.warning(
            '[HongHac fonts] Không cài được font vào bất kỳ thư mục hệ thống nào. '
            'Report PDF/ảnh có thể thiếu font brand. Hãy copy thủ công các file trong '
            'static/src/fonts/ vào ~/.local/share/fonts hoặc /usr/share/fonts rồi chạy '
            '`fc-cache -f`.')
        return None

    # Refresh fontconfig cache để wkhtmltopdf/wkhtmltoimage nhận font ngay.
    try:
        subprocess.run(
            ['fc-cache', '-f', installed_dir],
            check=False, timeout=120,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        _logger.info('[HongHac fonts] Đã refresh fontconfig cache tại %s', installed_dir)
    except FileNotFoundError:
        _logger.warning('[HongHac fonts] Không tìm thấy lệnh `fc-cache` (fontconfig chưa cài). '
                        'Font đã copy nhưng cache chưa refresh.')
    except subprocess.SubprocessError as err:
        _logger.warning('[HongHac fonts] fc-cache lỗi (%s). Font đã copy nhưng cache chưa refresh.', err)

    return installed_dir


def post_init_hook(env):
    """Chạy sau khi install module lần đầu."""
    install_brand_fonts()
