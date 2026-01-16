# Real Estate Management System - Project Context

## Project Overview
**Project Name:** Real Estate Management System  
**Framework:** Odoo 19.0  
**Location:** `/home/haitdd@aht.local/Documents/job_hai/real_estate/`  
**Database:** PostgreSQL  
**Language:** Python, JavaScript (OWL), XML  

---

## Project Structure

```
real_estate/
├── odoo-19.0/                    # Odoo core installation
├── custome_odoo/                 # Custom modules directory
│   ├── real_estate_site_plan/    # Main site plan module
│   └── customer_manager/         # Customer management module
├── odoo.conf                     # Odoo configuration
└── memory_bank/                  # Project documentation (this folder)
```

---

## Custom Modules

### 1. real_estate_site_plan
**Purpose:** Site plan drawing and property management  
**Version:** 19.0.1.0.0  
**Status:** ✅ Active Development  

**Key Features:**
- Upload site plan images (master plans/blueprints)
- Draw polygons on canvas to represent properties
- Link polygons to products (properties)
- Automatic product creation from polygons
- Interactive canvas with zoom, pan, drawing tools
- Color coding based on product categories
- Sold status indication (gray color)

**Dependencies:**
- `product` (Odoo base)
- `web` (Odoo framework)

**Models:**
- `site.plan` - Site plan master record
- `site.plan.polygon` - Individual property polygons
- `product.product` (inherited) - Property products
- `product.category` (inherited) - Category with color

**Frontend:**
- OWL-based canvas widget
- HTML5 Canvas API
- Interactive drawing tools (polygon, rectangle, edit, select)
- Zoom/pan controls
- Real-time polygon rendering

### 2. customer_manager
**Purpose:** Customer and contact management  
**Status:** ✅ Installed  
**Dependencies:**
- `base`, `contacts`, `stock`, `product`, `portal`
- `web_view_enterprise`

---

## Configuration

### Odoo Config (`odoo.conf`)
```ini
[options]
admin_passwd = admin!123
db_host = localhost
db_name = db_test_map
db_port = 5432
db_user = odoo
xmlrpc_port = 8019
http_port = 8019
db_password = 745254
data_dir = /tmp/odoo-data
addons_path = /home/haitdd@aht.local/Documents/job_hai/real_estate/odoo-19.0/addons, /home/haitdd@aht.local/Documents/job_hai/real_estate/custome_odoo
```

### Database
- **Name:** `db_test_map`
- **Port:** 5432
- **User:** odoo

### Server
- **HTTP Port:** 8019
- **Access:** http://localhost:8019

---

## Key Technologies

### Backend
- **Python 3.10+**
- **Odoo ORM**
- **PostgreSQL**

### Frontend
- **OWL (Odoo Web Library)** - Component framework
- **HTML5 Canvas API** - Drawing polygons
- **JavaScript ES6+**
- **XML** - View definitions

### Tools
- **Git** - Version control
- **VS Code / PyCharm** - Development

---

## Development Workflow

1. **Start Odoo:**
   ```bash
   cd /home/haitdd@aht.local/Documents/job_hai/real_estate
   python3 odoo-19.0/odoo-bin -c odoo.conf -d db_test_map
   ```

2. **Update Module:**
   ```bash
   python3 odoo-19.0/odoo-bin -c odoo.conf -d db_test_map -u real_estate_site_plan
   ```

3. **Access:**
   - URL: http://localhost:8019
   - Menu: Real Estate → Site Plans

---

## Important Notes

- **No MD documentation files** unless explicitly requested
- **Code-first approach** - Focus on implementation
- **Odoo 19 specific** - Use latest OWL syntax
- **Custom addons path** configured in odoo.conf
- **Module updates** require restart or `-u` flag

---

**Last Updated:** 2026-01-13 09:10:00 +07:00  
**Maintained By:** Senior Odoo Developer
