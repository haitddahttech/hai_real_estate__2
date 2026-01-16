# Real Estate Site Plan Module

## Overview
This module allows you to manage real estate properties by drawing polygons on site plan images. Each polygon represents a unique property/product.

## Features

### 🎨 **Drawing Tools**
- **Polygon Tool**: Click points to create custom shapes, double-click to finish
- **Rectangle Tool**: Click and drag to create rectangular shapes
- **Edit Mode**: Drag polygon points to adjust shapes
- **Delete Tool**: Remove unwanted polygons
- **Color Picker**: Customize polygon colors for better visualization

### 🏗️ **Site Plan Management**
- Upload master plan/site plan images
- Draw multiple polygons on a single site plan
- Each polygon automatically creates a unique product
- Visual representation of all properties

### 📦 **Product Integration**
- Automatic product creation when saving polygons
- Polygon name becomes product name (must be unique)
- Products are linked to their polygons
- Easy navigation between site plans and products

## Installation

1. Copy this module to your Odoo addons directory
2. Update the apps list in Odoo
3. Install "Real Estate Site Plan" module

## Usage

### Creating a Site Plan

1. Go to **Real Estate > Site Plans**
2. Click **Create**
3. Enter a name for your site plan (e.g., "Vinhomes Grand Park - Phase 1")
4. Upload your site plan image in the **Site Plan Image** tab
5. Go to the **Draw Polygons** tab

### Drawing Polygons

1. **Select a drawing tool:**
   - **Polygon**: For irregular shapes (villas, custom lots)
   - **Rectangle**: For regular rectangular plots

2. **Choose a color** from the color picker

3. **Draw your polygon:**
   - **Polygon mode**: Click each corner point, double-click to finish
   - **Rectangle mode**: Click and drag, release to finish

4. **Enter polygon name** when prompted (this will be the product name)

5. The polygon is automatically saved and a product is created

### Editing Polygons

1. Click the **Edit** button in the toolbar
2. Select a polygon by clicking on it
3. Drag the corner points to adjust the shape
4. The polygon is automatically updated

### Deleting Polygons

1. Click the **Select** button
2. Click on the polygon you want to delete
3. Click the **Delete** button
4. Confirm the deletion

## Technical Details

### Models

- **site.plan**: Stores site plan information and images
- **site.plan.polygon**: Stores polygon coordinates and links to products
- **product.product**: Extended to link with polygons

### Data Structure

Polygon coordinates are stored as JSON:
```json
[
  {"x": 100, "y": 150},
  {"x": 200, "y": 150},
  {"x": 200, "y": 250},
  {"x": 100, "y": 250}
]
```

### Constraints

- Polygon names must be unique within a site plan
- Each polygon must have at least 3 points
- Each polygon must be linked to a product

## Tips & Best Practices

1. **Image Quality**: Use high-resolution site plan images for better accuracy
2. **Naming Convention**: Use consistent naming (e.g., A01, A02, B01, B02)
3. **Colors**: Use different colors for different property types or statuses
4. **Zoom**: Use browser zoom (Ctrl +/-) for precise drawing on large images

## Future Enhancements

- [ ] Zoom and pan controls within the canvas
- [ ] Polygon copy/paste functionality
- [ ] Bulk import polygons from CSV
- [ ] Export site plan with polygons as PDF
- [ ] Property status visualization (available/sold/reserved)
- [ ] Area calculation for polygons
- [ ] Integration with sales module

## Support

For issues or questions, please contact your system administrator.

## License

LGPL-3

## Author

Your Company

## Version

19.0.1.0.0
