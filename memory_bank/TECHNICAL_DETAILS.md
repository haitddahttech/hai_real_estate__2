# Technical Implementation Details

## Module: real_estate_site_plan

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Odoo Backend (Python)                    │
├─────────────────────────────────────────────────────────────┤
│  Models:                                                     │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  site.plan   │──│ site.plan.polygon│──│product.product│ │
│  │              │  │                  │  │              │  │
│  │ - name       │  │ - name           │  │ - is_sold    │  │
│  │ - image      │  │ - coordinates    │  │ - categ_id   │  │
│  │ - polygon_ids│  │ - product_id     │  └──────────────┘  │
│  └──────────────┘  │ - color          │                     │
│                    │ - polygon_type   │  ┌──────────────┐  │
│                    └──────────────────┘  │product.category│ │
│                                          │              │  │
│                                          │ - color      │  │
│                                          └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Odoo Frontend (OWL/JS)                      │
├─────────────────────────────────────────────────────────────┤
│  SitePlanCanvasWidget (OWL Component)                       │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ State:                                                │  │
│  │ - mode (select/polygon/rectangle/edit)                │  │
│  │ - currentPolygon (points being drawn)                 │  │
│  │ - polygons (loaded from DB)                           │  │
│  │ - scale, offset (zoom/pan)                            │  │
│  │                                                        │  │
│  │ Methods:                                              │  │
│  │ - onMouseDown/Move/Up (drawing logic)                 │  │
│  │ - onWheel (zoom)                                      │  │
│  │ - onKeyDown (shortcuts)                               │  │
│  │ - draw() (canvas rendering)                           │  │
│  │ - savePolygon() (ORM create)                          │  │
│  │ - loadPolygons() (ORM searchRead)                     │  │
│  └───────────────────────────────────────────────────────┘  │
│                              │                               │
│                              ▼                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │         HTML5 Canvas (Drawing Surface)                │  │
│  │  - Image rendering                                    │  │
│  │  - Polygon paths                                      │  │
│  │  - Points (circles)                                   │  │
│  │  - Labels (text)                                      │  │
│  │  - Transform (scale + translate)                      │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### 1. Create Polygon Flow
```
User draws polygon → Double-click/Enter/Save button
    ↓
savePolygonDialog() → Show product selection dialog
    ↓
User selects product
    ↓
savePolygon(name, productId, type)
    ↓
ORM.create('site.plan.polygon', {
    name: productName,
    product_id: productId,
    coordinates: JSON.stringify(points),
    color: auto-filled from category,
    polygon_type: 'polygon' or 'rectangle'
})
    ↓
Backend: site_plan_polygon.create()
    - Validate product exists
    - Auto-fill name from product
    - Auto-fill color from product.categ_id.color
    - Validate coordinates (min 3 points, valid JSON)
    - Check unique name per site plan
    ↓
Database: INSERT into site_plan_polygon
    ↓
Frontend: loadPolygons() → Refresh canvas
```

### 2. Load Polygons Flow
```
Component mounted / Polygon saved
    ↓
loadPolygons()
    ↓
ORM.searchRead('site.plan.polygon', [
    ['site_plan_id', '=', recordId]
], ['name', 'coordinates', 'color', 'product_id'])
    ↓
Parse JSON coordinates
    ↓
Store in state.polygons
    ↓
draw() → Render on canvas
```

### 3. Zoom/Pan Flow
```
User scrolls mouse wheel
    ↓
onWheel(e)
    ↓
Calculate: worldPosX/Y (point under mouse in world coords)
    ↓
Update: scale (oldScale * zoomFactor)
    ↓
Update: offset (to keep worldPos under mouse)
    ↓
draw() with new transform
    ↓
ctx.scale(scale, scale)
ctx.translate(offset.x, offset.y)
    ↓
Render image + polygons
    ↓
Inverse scale for points/lines (size / scale)
```

---

## Key Algorithms

### 1. Point-in-Polygon Detection
```javascript
isPointInPolygon(point, polygon) {
    // Ray casting algorithm
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        const xi = polygon[i].x, yi = polygon[i].y;
        const xj = polygon[j].x, yj = polygon[j].y;
        const intersect = ((yi > point.y) !== (yj > point.y)) &&
            (point.x < (xj - xi) * (point.y - yi) / (yj - yi) + xi);
        if (intersect) inside = !inside;
    }
    return inside;
}
```

### 2. Zoom at Mouse Position
```javascript
// Get world coordinates before zoom
const worldPosX = mouseX / oldScale - offset.x;
const worldPosY = mouseY / oldScale - offset.y;

// Update scale
scale = newScale;

// Adjust offset so worldPos stays under mouse
offset.x = mouseX / newScale - worldPosX;
offset.y = mouseY / newScale - worldPosY;
```

### 3. Inverse Scaling for Visual Consistency
```javascript
// Points stay 4px regardless of zoom
const pointRadius = 4 / this.state.scale;

// Lines stay 2-3px regardless of zoom
const lineWidth = (isSelected ? 3 : 2) / this.state.scale;

// Font stays 14px regardless of zoom
const fontSize = 14 / this.state.scale;
```

---

## Database Schema

### site_plan
```sql
CREATE TABLE site_plan (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    image BYTEA,  -- Binary image data
    description TEXT,
    active BOOLEAN DEFAULT TRUE,
    create_date TIMESTAMP,
    write_date TIMESTAMP,
    create_uid INTEGER REFERENCES res_users(id),
    write_uid INTEGER REFERENCES res_users(id)
);
```

### site_plan_polygon
```sql
CREATE TABLE site_plan_polygon (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    site_plan_id INTEGER REFERENCES site_plan(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES product_product(id) ON DELETE RESTRICT,
    coordinates TEXT NOT NULL,  -- JSON: [{"x": 0, "y": 0}, ...]
    color VARCHAR DEFAULT '#3498db',
    polygon_type VARCHAR DEFAULT 'polygon',  -- 'polygon' or 'rectangle'
    active BOOLEAN DEFAULT TRUE,
    create_date TIMESTAMP,
    write_date TIMESTAMP,
    
    CONSTRAINT unique_name_per_site_plan 
        UNIQUE(name, site_plan_id)
);
```

### product_product (extended)
```sql
ALTER TABLE product_product ADD COLUMN site_plan_polygon_id INTEGER 
    REFERENCES site_plan_polygon(id) ON DELETE SET NULL;
ALTER TABLE product_product ADD COLUMN is_sold BOOLEAN DEFAULT FALSE;
```

### product_category (extended)
```sql
ALTER TABLE product_category ADD COLUMN color VARCHAR DEFAULT '#3498db';
```

---

## API Endpoints (ORM Calls)

### Frontend → Backend

1. **Load Polygons:**
```javascript
await this.orm.searchRead(
    'site.plan.polygon',
    [['site_plan_id', '=', recordId]],
    ['name', 'coordinates', 'color', 'polygon_type', 'product_id']
);
```

2. **Create Polygon:**
```javascript
await this.orm.create('site.plan.polygon', [{
    name: productName,
    site_plan_id: recordId,
    product_id: productId,
    coordinates: JSON.stringify(points),
    color: color,
    polygon_type: type
}]);
```

3. **Update Polygon:**
```javascript
await this.orm.write('site.plan.polygon', [polygonId], {
    coordinates: JSON.stringify(newPoints)
});
```

4. **Delete Polygon:**
```javascript
await this.orm.unlink('site.plan.polygon', [polygonId]);
```

5. **Load Image:**
```javascript
await this.orm.read('site.plan', [recordId], ['image']);
```

---

## Performance Considerations

### Optimizations Implemented:
1. **Canvas Rendering:**
   - Single draw() call per state change
   - No unnecessary redraws
   - Efficient path drawing

2. **State Management:**
   - OWL reactive state (useState)
   - Minimal state updates
   - Computed values cached

3. **Database:**
   - Indexed foreign keys
   - Unique constraints for fast lookups
   - JSON storage for coordinates (compact)

4. **Memory:**
   - Image loaded once, cached in state
   - Polygons loaded once, updated on change
   - No memory leaks (proper cleanup in onWillUnmount)

### Potential Bottlenecks:
- Large images (>5MB) may slow initial load
- Many polygons (>1000) may affect rendering
- Complex polygons (>100 points) may slow drawing

### Scaling Recommendations:
- Lazy load polygons (pagination)
- Image compression/thumbnails
- Canvas virtualization for large datasets
- Web Workers for heavy calculations

---

## Security

### Access Control:
- Model-level security via `ir.model.access.csv`
- All users can read/write site plans and polygons
- Product access controlled by product module

### Data Validation:
- Python constraints on models
- JSON validation for coordinates
- Unique name validation
- Product existence validation

### XSS Prevention:
- Odoo ORM handles SQL injection
- No direct HTML rendering from user input
- Canvas rendering (no DOM manipulation)

---

## Browser Compatibility

**Tested On:**
- Chrome 120+ ✅
- Firefox 120+ ✅
- Edge 120+ ✅

**Requirements:**
- HTML5 Canvas support
- ES6+ JavaScript
- Odoo 19 compatible browser

**Known Issues:**
- Safari may have different wheel event deltaY values
- Mobile browsers not optimized (touch events needed)

---

**Last Updated:** 2026-01-13 09:10:00 +07:00
