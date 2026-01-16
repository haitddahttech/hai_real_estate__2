# Quick Reference - Commands & Shortcuts

## Odoo Commands

### Start Odoo
```bash
cd /home/haitdd@aht.local/Documents/job_hai/real_estate
python3 odoo-19.0/odoo-bin -c odoo.conf -d db_test_map
```

### Update Module
```bash
python3 odoo-19.0/odoo-bin -c odoo.conf -d db_test_map -u real_estate_site_plan
```

### Install Module
```bash
python3 odoo-19.0/odoo-bin -c odoo.conf -d db_test_map -i real_estate_site_plan
```

### Shell Mode (Testing)
```bash
python3 odoo-19.0/odoo-bin shell -c odoo.conf -d db_test_map
```

### Debug Mode
```bash
python3 odoo-19.0/odoo-bin -c odoo.conf -d db_test_map --log-level=debug
```

---

## Canvas Widget Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **Enter** | Save current polygon |
| **Backspace** | Remove last point |
| **Delete** | Remove last point |
| **Ctrl+Z** | Undo last point |
| **Escape** | Cancel current drawing |

---

## Mouse Controls

| Action | Function |
|--------|----------|
| **Left Click** | Add point (polygon mode) |
| **Left Click + Drag** | Draw rectangle (rectangle mode) |
| **Left Click on Point + Drag** | Move point |
| **Right Click + Drag** | Pan canvas |
| **Scroll Wheel** | Zoom in/out |
| **Double Click** | ~~Save polygon~~ (disabled) |

---

## Toolbar Buttons

### Drawing Tools
- **Select** - Select polygons
- **Polygon** - Draw free-form polygon
- **Rectangle** - Draw rectangle
- **Edit** - Edit polygon points

### Actions
- **Save Polygon** - Save current drawing
- **Delete** - Delete selected polygon
- **Clear** - Clear current drawing

### Zoom Controls
- **Zoom In** - Zoom in (center)
- **Zoom Out** - Zoom out (center)
- **Reset** - Reset to 100% zoom

### Color
- **Color Picker** - Choose polygon color (overridden by category)

---

## Module File Structure

```
real_estate_site_plan/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── site_plan.py
│   ├── site_plan_polygon.py
│   ├── product_product.py
│   └── product_category.py
├── views/
│   ├── site_plan_views.xml
│   └── product_product_views.xml
├── security/
│   └── ir.model.access.csv
├── static/
│   ├── src/
│   │   ├── js/
│   │   │   └── site_plan_canvas.js
│   │   └── xml/
│   │       └── site_plan_canvas.xml
│   └── description/
│       └── icon.svg
└── README.md
```

---

## Common Tasks

### Add New Field to Model
1. Edit `models/model_name.py`
2. Add field definition
3. Update module: `-u real_estate_site_plan`

### Add New View
1. Edit `views/view_name.xml`
2. Add view record
3. Update module

### Modify Canvas Widget
1. Edit `static/src/js/site_plan_canvas.js`
2. Clear browser cache (Ctrl+Shift+R)
3. Refresh page

### Debug JavaScript
1. Open browser console (F12)
2. Check for errors
3. Use `console.log()` in widget code

### Check Odoo Logs
```bash
# In terminal where Odoo is running
# Logs appear in real-time
```

---

## Database Queries (Shell Mode)

```python
# Get all site plans
env['site.plan'].search([])

# Get polygons for site plan ID 1
env['site.plan.polygon'].search([('site_plan_id', '=', 1)])

# Get product by ID
env['product.product'].browse(1)

# Update polygon color
polygon = env['site.plan.polygon'].browse(1)
polygon.write({'color': '#ff0000'})

# Create new polygon
env['site.plan.polygon'].create({
    'name': 'Test',
    'site_plan_id': 1,
    'product_id': 1,
    'coordinates': '[{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100}]',
    'color': '#00ff00'
})
```

---

## Troubleshooting

### Module Not Showing
1. Check `addons_path` in odoo.conf
2. Restart Odoo
3. Apps → Update Apps List

### Canvas Not Loading
1. Check browser console (F12)
2. Clear cache (Ctrl+Shift+R)
3. Check widget registration (view_widgets)

### Polygon Not Saving
1. Check product is selected
2. Check at least 3 points
3. Check browser console for errors
4. Check Odoo logs

### Zoom Not Working
1. Check scroll wheel works
2. Try zoom buttons
3. Check browser console

### Colors Not Showing
1. Check product has category
2. Check category has color field
3. Update module if field added recently

---

## Git Commands (If Using Version Control)

```bash
# Status
git status

# Add changes
git add .

# Commit
git commit -m "Description"

# Push
git push origin main

# Pull
git pull origin main
```

---

## Useful Odoo URLs

- **Main:** http://localhost:8019
- **Apps:** http://localhost:8019/web#action=base.open_module_tree
- **Settings:** http://localhost:8019/web#action=base.action_res_config_settings
- **Database Manager:** http://localhost:8019/web/database/manager

---

## Color Codes (Reference)

```python
# Default colors
'#3498db'  # Blue (default)
'#555555'  # Dark gray (sold)
'#e74c3c'  # Red (selected)
'#2ecc71'  # Green
'#f39c12'  # Orange
'#9b59b6'  # Purple
'#1abc9c'  # Turquoise
```

---

**Quick Access:** Save this file for fast reference!  
**Last Updated:** 2026-01-13 09:10:00 +07:00
