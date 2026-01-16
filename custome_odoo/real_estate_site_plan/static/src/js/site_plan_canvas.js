import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";

export class SitePlanCanvasWidget extends Component {
    static template = "real_estate_site_plan.SitePlanCanvasWidget";
    static props = {
        record: Object,
        readonly: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");

        this.canvasRef = useRef("canvas");
        this.state = useState({
            mode: 'select', // 'select', 'polygon', 'rectangle', 'edit'
            currentPolygon: [],
            polygons: [],
            selectedPolygon: null,
            selectedPoint: null,
            color: '#3498db',
            image: null,
            imageLoaded: false,
            scale: 1,
            offset: { x: 0, y: 0 },
            isDragging: false,
            dragStart: null,
            isPanning: false,
            panStart: null,
            draggedPointIndex: null,
            isMiddleMouseDown: false,
            isDraggingPolygon: false,
            polygonDragStart: null,
            polygonDragOffset: null,
        });

        onMounted(() => {
            this.initCanvas();
            this.loadPolygons();
        });

        onWillUnmount(() => {
            if (this.canvas) {
                this.canvas.removeEventListener('mousedown', this.handleMouseDown);
                this.canvas.removeEventListener('mousemove', this.handleMouseMove);
                this.canvas.removeEventListener('mouseup', this.handleMouseUp);
                this.canvas.removeEventListener('dblclick', this.handleDoubleClick);
                this.canvas.removeEventListener('wheel', this.handleWheel);
                document.removeEventListener('keydown', this.handleKeyDown);
            }
        });
    }

    async initCanvas() {
        this.canvas = this.canvasRef.el;
        if (!this.canvas) return;

        this.ctx = this.canvas.getContext('2d');

        // Set canvas size to match container
        this.resizeCanvas();

        // Add resize listener
        window.addEventListener('resize', () => this.resizeCanvas());

        // Load image if exists
        await this.loadImage();

        // Add event listeners
        this.handleMouseDown = this.onMouseDown.bind(this);
        this.handleMouseMove = this.onMouseMove.bind(this);
        this.handleMouseUp = this.onMouseUp.bind(this);
        this.handleDoubleClick = this.onDoubleClick.bind(this);
        this.handleWheel = this.onWheel.bind(this);
        this.handleKeyDown = this.onKeyDown.bind(this);

        this.canvas.addEventListener('mousedown', this.handleMouseDown);
        this.canvas.addEventListener('mousemove', this.handleMouseMove);
        this.canvas.addEventListener('mouseup', this.handleMouseUp);
        this.canvas.addEventListener('dblclick', this.handleDoubleClick);
        this.canvas.addEventListener('wheel', this.handleWheel, { passive: false });
        this.canvas.addEventListener('contextmenu', (e) => e.preventDefault()); // Prevent right-click menu
        document.addEventListener('keydown', this.handleKeyDown);

        this.draw();
    }

    resizeCanvas() {
        if (!this.canvas) return;

        const container = this.canvas.parentElement;
        const rect = container.getBoundingClientRect();

        // High-resolution multiplier for crisp rendering
        // 3x means canvas will be 3 times larger than display
        const RESOLUTION_SCALE = 3;

        // Maintain 3:2 aspect ratio (1200:800)
        const displayWidth = rect.width;
        const displayHeight = Math.round(rect.width * (800 / 1200));

        // Set canvas internal resolution (3x for crisp rendering)
        this.canvas.width = displayWidth * RESOLUTION_SCALE;
        this.canvas.height = displayHeight * RESOLUTION_SCALE;

        // Set display size (CSS pixels)
        this.canvas.style.width = displayWidth + 'px';
        this.canvas.style.height = displayHeight + 'px';

        // Store scale factor for use in draw()
        this.resolutionScale = RESOLUTION_SCALE;

        // Enable high-quality image smoothing for smooth rendering
        // With 3x resolution, smoothing makes images look better
        this.ctx.imageSmoothingEnabled = true;
        this.ctx.imageSmoothingQuality = 'high'; // 'low', 'medium', or 'high'

        // Redraw if image loaded
        if (this.state.imageLoaded) {
            this.draw();
        }
    }

    async loadImage() {
        const recordId = this.props.record.resId;
        if (!recordId) return;

        try {
            // First, try to get the attachment URL for better quality
            const attachments = await this.orm.searchRead(
                'ir.attachment',
                [
                    ['res_model', '=', 'site.plan'],
                    ['res_id', '=', recordId],
                    ['res_field', '=', 'image']
                ],
                ['id', 'checksum']
            );

            if (attachments && attachments.length > 0) {
                // Load image from attachment URL (preserves original quality)
                const attachmentId = attachments[0].id;
                const img = new Image();
                img.onload = () => {
                    this.state.image = img;
                    this.state.imageLoaded = true;
                    this.draw();
                };
                // Use web/image route to get original image without resizing
                img.src = `/web/content/${attachmentId}?unique=${attachments[0].checksum}`;
            } else {
                // Fallback to base64 if no attachment found
                const record = await this.orm.read('site.plan', [recordId], ['image']);
                if (record && record[0] && record[0].image) {
                    const img = new Image();
                    img.onload = () => {
                        this.state.image = img;
                        this.state.imageLoaded = true;
                        this.draw();
                    };
                    img.src = `data:image/png;base64,${record[0].image}`;
                }
            }
        } catch (error) {
            console.error('Error loading image:', error);
        }
    }

    async loadPolygons() {
        const recordId = this.props.record.resId;
        if (!recordId) return;

        try {
            const polygons = await this.orm.searchRead(
                'site.plan.polygon',
                [['site_plan_id', '=', recordId]],
                ['name', 'coordinates', 'color', 'polygon_type', 'product_template_id']
            );

            this.state.polygons = polygons.map(p => ({
                id: p.id,
                name: p.name,
                points: JSON.parse(p.coordinates),
                color: p.color || '#3498db',
                type: p.polygon_type,
                productId: p.product_template_id[0],
                productName: p.product_template_id[1],
            }));

            this.draw();
        } catch (error) {
            console.error('Error loading polygons:', error);
        }
    }

    getMousePos(e) {
        const rect = this.canvas.getBoundingClientRect();

        // Get display dimensions (CSS pixels, not canvas pixels)
        const displayWidth = parseFloat(this.canvas.style.width) || rect.width;
        const displayHeight = parseFloat(this.canvas.style.height) || rect.height;

        // Calculate scale from display size to reference size (1200x800)
        const scaleX = 1200 / displayWidth;
        const scaleY = 800 / displayHeight;

        // Convert screen coordinates to reference coordinates (1200x800 space)
        const canvasX = (e.clientX - rect.left) * scaleX;
        const canvasY = (e.clientY - rect.top) * scaleY;

        // Apply zoom and pan transforms (inverse)
        const x = canvasX / this.state.scale - this.state.offset.x;
        const y = canvasY / this.state.scale - this.state.offset.y;

        return { x, y };
    }

    onMouseDown(e) {
        const pos = this.getMousePos(e);

        // Middle mouse button - track for zoom
        if (e.button === 1) {
            e.preventDefault();
            this.state.isMiddleMouseDown = true;
            return;
        }

        // Right click - start panning
        if (e.button === 2) {
            e.preventDefault();
            this.state.isPanning = true;
            this.state.panStart = { x: e.clientX, y: e.clientY };
            this.canvas.style.cursor = 'grabbing';
            return;
        }

        // Left click
        if (e.button === 0) {
            // Check if clicking on existing point to drag
            if (this.state.mode === 'polygon' && this.state.currentPolygon.length > 0) {
                const pointIndex = this.findNearestPoint(pos, this.state.currentPolygon);
                if (pointIndex !== -1) {
                    this.state.draggedPointIndex = pointIndex;
                    this.canvas.style.cursor = 'move';
                    return;
                }
            }

            // Normal polygon drawing
            if (this.state.mode === 'polygon') {
                this.state.currentPolygon.push(pos);
                this.draw();
            } else if (this.state.mode === 'rectangle') {
                this.state.isDragging = true;
                this.state.dragStart = pos;
            } else if (this.state.mode === 'edit') {
                this.selectPoint(pos);
            } else if (this.state.mode === 'select') {
                // Check if clicking on a polygon to drag
                const polygonIndex = this.findPolygonAtPosition(pos);
                if (polygonIndex !== -1) {
                    this.state.selectedPolygon = polygonIndex;
                    this.state.isDraggingPolygon = true;
                    this.state.polygonDragStart = pos;
                    this.canvas.style.cursor = 'move';
                    this.draw();
                } else {
                    this.state.selectedPolygon = null;
                    this.draw();
                }
            }
        }
    }

    onMouseMove(e) {
        // Handle panning
        if (this.state.isPanning && this.state.panStart) {
            const dx = (e.clientX - this.state.panStart.x) / this.state.scale;
            const dy = (e.clientY - this.state.panStart.y) / this.state.scale;

            this.state.offset.x += dx;
            this.state.offset.y += dy;

            this.state.panStart = { x: e.clientX, y: e.clientY };
            this.draw();
            return;
        }

        // Handle polygon dragging
        if (this.state.isDraggingPolygon && this.state.polygonDragStart) {
            const pos = this.getMousePos(e);
            const dx = pos.x - this.state.polygonDragStart.x;
            const dy = pos.y - this.state.polygonDragStart.y;

            // Move all points of the polygon
            const polygon = this.state.polygons[this.state.selectedPolygon];
            polygon.points = polygon.points.map(point => ({
                x: point.x + dx,
                y: point.y + dy
            }));

            this.state.polygonDragStart = pos;
            this.draw();
            return;
        }

        // Handle point dragging
        if (this.state.draggedPointIndex !== null) {
            const pos = this.getMousePos(e);
            this.state.currentPolygon[this.state.draggedPointIndex] = pos;
            this.draw();
            return;
        }

        // Rectangle drawing
        if (this.state.mode === 'rectangle' && this.state.isDragging) {
            const pos = this.getMousePos(e);
            this.state.currentPolygon = [
                this.state.dragStart,
                { x: pos.x, y: this.state.dragStart.y },
                pos,
                { x: this.state.dragStart.x, y: pos.y },
            ];
            this.draw();
        } else if (this.state.mode === 'edit' && this.state.selectedPoint !== null) {
            const pos = this.getMousePos(e);
            const polygon = this.state.polygons[this.state.selectedPolygon];
            polygon.points[this.state.selectedPoint] = pos;
            this.draw();
        }
    }

    onMouseUp(e) {
        // End middle mouse button
        if (e.button === 1) {
            this.state.isMiddleMouseDown = false;
            return;
        }

        // End panning
        if (this.state.isPanning) {
            this.state.isPanning = false;
            this.state.panStart = null;
            this.canvas.style.cursor = 'crosshair';
            return;
        }

        // End polygon dragging
        if (this.state.isDraggingPolygon) {
            this.state.isDraggingPolygon = false;
            this.state.polygonDragStart = null;
            this.canvas.style.cursor = 'crosshair';

            // Save updated polygon position
            if (this.state.selectedPolygon !== null) {
                this.savePolygonPosition(this.state.selectedPolygon);
            }
            return;
        }

        // End point dragging
        if (this.state.draggedPointIndex !== null) {
            this.state.draggedPointIndex = null;
            this.canvas.style.cursor = 'crosshair';
            return;
        }

        // Rectangle drawing
        if (this.state.mode === 'rectangle' && this.state.isDragging) {
            this.state.isDragging = false;
            if (this.state.currentPolygon.length === 4) {
                this.savePolygonDialog('rectangle');
            }
        } else if (this.state.mode === 'edit' && this.state.selectedPoint !== null) {
            this.updatePolygon();
            this.state.selectedPoint = null;
        }
    }

    findNearestPoint(pos, points) {
        const threshold = 15 / this.state.scale; // Increased threshold for easier point selection
        for (let i = 0; i < points.length; i++) {
            const p = points[i];
            const dist = Math.sqrt((pos.x - p.x) ** 2 + (pos.y - p.y) ** 2);
            if (dist < threshold) {
                return i;
            }
        }
        return -1;
    }

    onDoubleClick(e) {
        e.preventDefault(); // Prevent adding point on double-click
        // Double-click no longer saves - use Save button or Enter key instead
    }

    onWheel(e) {
        e.preventDefault();

        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // Calculate zoom factor
        const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9; // Scroll up = zoom in, scroll down = zoom out
        const oldScale = this.state.scale;
        const newScale = Math.max(0.1, Math.min(10, oldScale * zoomFactor));

        // If scale didn't change (hit limits), don't update
        if (oldScale === newScale) {
            return;
        }

        // Get the mouse position in world coordinates before zoom
        const worldPosX = mouseX / oldScale - this.state.offset.x;
        const worldPosY = mouseY / oldScale - this.state.offset.y;

        // Update scale
        this.state.scale = newScale;

        // Calculate new offset so that worldPos stays under the mouse cursor
        this.state.offset.x = mouseX / newScale - worldPosX;
        this.state.offset.y = mouseY / newScale - worldPosY;

        this.draw();
    }

    onKeyDown(e) {
        // Enter: finish and save polygon
        if (e.key === 'Enter' && this.state.mode === 'polygon') {
            if (this.state.currentPolygon.length >= 3) {
                e.preventDefault();
                this.savePolygonDialog('polygon');
            }
        }

        // Backspace or Delete: remove last point when drawing
        if ((e.key === 'Backspace' || e.key === 'Delete') && this.state.mode === 'polygon') {
            if (this.state.currentPolygon.length > 0) {
                e.preventDefault();
                this.state.currentPolygon.pop();
                this.draw();
            }
        }

        // Ctrl+Z: undo last point
        if (e.ctrlKey && e.key === 'z' && this.state.mode === 'polygon') {
            if (this.state.currentPolygon.length > 0) {
                e.preventDefault();
                this.state.currentPolygon.pop();
                this.draw();
            }
        }

        // Escape: cancel current drawing
        if (e.key === 'Escape') {
            this.state.currentPolygon = [];
            this.state.selectedPolygon = null;
            this.draw();
        }
    }

    selectPolygon(pos) {
        for (let i = this.state.polygons.length - 1; i >= 0; i--) {
            if (this.isPointInPolygon(pos, this.state.polygons[i].points)) {
                this.state.selectedPolygon = i;
                this.draw();
                return;
            }
        }
        this.state.selectedPolygon = null;
        this.draw();
    }

    findPolygonAtPosition(pos) {
        // Find polygon at position, return index or -1
        for (let i = this.state.polygons.length - 1; i >= 0; i--) {
            if (this.isPointInPolygon(pos, this.state.polygons[i].points)) {
                return i;
            }
        }
        return -1;
    }

    selectPoint(pos) {
        if (this.state.selectedPolygon === null) return;

        const polygon = this.state.polygons[this.state.selectedPolygon];
        for (let i = 0; i < polygon.points.length; i++) {
            const p = polygon.points[i];
            const dist = Math.sqrt((pos.x - p.x) ** 2 + (pos.y - p.y) ** 2);
            if (dist < 10) {
                this.state.selectedPoint = i;
                return;
            }
        }
    }

    isPointInPolygon(point, polygon) {
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

    draw() {
        if (!this.ctx) return;

        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Save context and apply transformations
        this.ctx.save();

        // Apply resolution scale first (canvas is 3x larger than display)
        const resScale = this.resolutionScale || 1;
        this.ctx.scale(resScale, resScale);

        // Get display dimensions (CSS pixels)
        const displayWidth = parseFloat(this.canvas.style.width) || (this.canvas.width / resScale);
        const displayHeight = parseFloat(this.canvas.style.height) || (this.canvas.height / resScale);

        // Scale coordinates from reference size (1200x800) to current display size
        const scaleX = displayWidth / 1200;
        const scaleY = displayHeight / 800;
        this.ctx.scale(scaleX, scaleY);

        // Apply user zoom and pan
        this.ctx.scale(this.state.scale, this.state.scale);
        this.ctx.translate(this.state.offset.x, this.state.offset.y);

        // Draw image at reference size (1200x800)
        if (this.state.imageLoaded && this.state.image) {
            this.ctx.drawImage(this.state.image, 0, 0, 1200, 800);
        }


        // Draw saved polygons (coordinates in 1200x800 space)
        this.state.polygons.forEach((polygon, index) => {
            this.drawPolygon(
                polygon.points,
                polygon.color,
                index === this.state.selectedPolygon,
                polygon.name
            );
        });

        // Draw current polygon being drawn
        if (this.state.currentPolygon.length > 0) {
            this.drawPolygon(this.state.currentPolygon, this.state.color, false, null, true);
        }

        // Restore context
        this.ctx.restore();
    }

    drawPolygon(points, color, isSelected, label, isDrawing = false) {
        if (points.length === 0) return;

        this.ctx.beginPath();
        this.ctx.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            this.ctx.lineTo(points[i].x, points[i].y);
        }

        // Close the path or draw closing line for preview
        if (!isDrawing) {
            this.ctx.closePath();
        } else if (points.length >= 2) {
            // Draw dashed line from last point to first point for preview
            this.ctx.save();
            this.ctx.setLineDash([5 / this.state.scale, 5 / this.state.scale]);
            this.ctx.strokeStyle = color;
            this.ctx.lineWidth = 1 / this.state.scale;
            this.ctx.beginPath();
            this.ctx.moveTo(points[points.length - 1].x, points[points.length - 1].y);
            this.ctx.lineTo(points[0].x, points[0].y);
            this.ctx.stroke();
            this.ctx.restore();

            // Continue with the main path
            this.ctx.beginPath();
            this.ctx.moveTo(points[0].x, points[0].y);
            for (let i = 1; i < points.length; i++) {
                this.ctx.lineTo(points[i].x, points[i].y);
            }
        }

        // Fill with less transparency
        this.ctx.fillStyle = color + '99'; // 60% opacity (less transparent)
        this.ctx.fill();

        // Stroke - adjust line width based on scale
        this.ctx.strokeStyle = isSelected ? '#e74c3c' : color;
        this.ctx.lineWidth = (isSelected ? 3 : 2) / this.state.scale;
        this.ctx.stroke();

        // Draw points - adjust radius based on scale
        const pointRadius = 4 / this.state.scale;
        points.forEach(p => {
            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, pointRadius, 0, 2 * Math.PI);
            this.ctx.fillStyle = isSelected ? '#e74c3c' : color;
            this.ctx.fill();
        });

        // Draw label - adjust font size based on scale
        if (label && !isDrawing) {
            const centerX = points.reduce((sum, p) => sum + p.x, 0) / points.length;
            const centerY = points.reduce((sum, p) => sum + p.y, 0) / points.length;

            this.ctx.fillStyle = '#000';
            // Use fixed small font - canvas transform will scale it automatically
            this.ctx.font = 'bold 4px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'middle';
            this.ctx.fillText(label, centerX, centerY);
        }
    }

    async savePolygonDialog(type) {
        const recordId = this.props.record.resId;
        if (!recordId) {
            this.notification.add('Vui lòng lưu bản vẽ trước!', { type: 'warning' });
            return;
        }

        // Get list of products already assigned to any polygon
        const usedPolygons = await this.orm.searchRead(
            'site.plan.polygon',
            [],
            ['product_template_id']
        );
        // Filter out falsy values (false, null, undefined, 0)
        const usedProductIds = usedPolygons
            .map(p => p.product_template_id[0])
            .filter(id => id); // Remove falsy values

        // Open Odoo's product selection dialog with filter
        this.dialog.add(SelectCreateDialog, {
            title: "Chọn sản phẩm",
            resModel: "product.template",
            multiSelect: false,
            domain: [['id', 'not in', usedProductIds]],
            onSelected: async (resIds) => {
                if (resIds && resIds.length > 0) {
                    const productId = resIds[0];

                    // Get product name
                    const products = await this.orm.read('product.template', [productId], ['name']);
                    if (products && products.length > 0) {
                        const productName = products[0].name;
                        await this.savePolygon(productName, productId, type);
                    }
                }
            },
        });
    }

    async savePolygon(name, productId, type) {
        const recordId = this.props.record.resId;
        if (!recordId) {
            this.notification.add('Vui lòng lưu bản vẽ trước!', { type: 'warning' });
            return;
        }

        try {
            const coordinates = JSON.stringify(this.state.currentPolygon);

            await this.orm.create('site.plan.polygon', [{
                name: name,
                site_plan_id: recordId,
                product_template_id: productId,
                coordinates: coordinates,
                color: this.state.color,
                polygon_type: type,
            }]);

            this.notification.add(`Đã lưu "${name}" thành công!`, { type: 'success' });

            // Reset current polygon
            this.state.currentPolygon = [];

            // Reload polygons
            await this.loadPolygons();
        } catch (error) {
            this.notification.add(`Lỗi khi lưu: ${error.message}`, { type: 'danger' });
            console.error('Error saving polygon:', error);
        }
    }

    async updatePolygon() {
        if (this.state.selectedPolygon === null) return;

        const polygon = this.state.polygons[this.state.selectedPolygon];
        try {
            await this.orm.write('site.plan.polygon', [polygon.id], {
                coordinates: JSON.stringify(polygon.points),
            });
            // Silent update
        } catch (error) {
            this.notification.add(`Lỗi khi cập nhật: ${error.message}`, { type: 'danger' });
        }
    }

    async savePolygonPosition(polygonIndex) {
        const polygon = this.state.polygons[polygonIndex];
        try {
            await this.orm.write('site.plan.polygon', [polygon.id], {
                coordinates: JSON.stringify(polygon.points),
            });
            // Silent save - no notification
        } catch (error) {
            this.notification.add(`Lỗi khi di chuyển: ${error.message}`, { type: 'danger' });
            // Reload to revert changes
            await this.loadPolygons();
        }
    }

    async deleteSelectedPolygon() {
        if (this.state.selectedPolygon === null) {
            this.notification.add('Vui lòng chọn một hình trước!', { type: 'warning' });
            return;
        }

        const polygon = this.state.polygons[this.state.selectedPolygon];
        if (!confirm(`Xóa hình "${polygon.name}"?`)) return;

        try {
            await this.orm.unlink('site.plan.polygon', [polygon.id]);
            this.notification.add('Đã xóa thành công!', { type: 'success' });
            this.state.selectedPolygon = null;
            await this.loadPolygons();
        } catch (error) {
            this.notification.add(`Lỗi khi xóa: ${error.message}`, { type: 'danger' });
        }
    }

    async updatePolygonColor() {
        if (this.state.selectedPolygon === null) {
            this.notification.add('Vui lòng chọn một hình trước!', { type: 'warning' });
            return;
        }

        const polygon = this.state.polygons[this.state.selectedPolygon];

        try {
            // Update polygon color
            await this.orm.write('site.plan.polygon', [polygon.id], {
                color: this.state.color
            });

            this.notification.add(`Đã cập nhật màu cho "${polygon.name}"!`, { type: 'success' });
            await this.loadPolygons();
        } catch (error) {
            this.notification.add(`Lỗi khi cập nhật màu: ${error.message}`, { type: 'danger' });
        }
    }

    saveCurrentPolygon() {
        if (this.state.mode === 'polygon' && this.state.currentPolygon.length >= 3) {
            this.savePolygonDialog('polygon');
        } else if (this.state.mode === 'rectangle' && this.state.currentPolygon.length === 4) {
            this.savePolygonDialog('rectangle');
        } else {
            this.notification.add('Vui lòng vẽ ít nhất 3 điểm', { type: 'warning' });
        }
    }

    zoomIn() {
        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;

        const oldScale = this.state.scale;
        const newScale = Math.min(10, oldScale * 1.2);

        if (oldScale === newScale) return;

        const worldPosX = centerX / oldScale - this.state.offset.x;
        const worldPosY = centerY / oldScale - this.state.offset.y;

        this.state.scale = newScale;
        this.state.offset.x = centerX / newScale - worldPosX;
        this.state.offset.y = centerY / newScale - worldPosY;

        this.draw();
    }

    zoomOut() {
        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;

        const oldScale = this.state.scale;
        const newScale = Math.max(0.1, oldScale / 1.2);

        if (oldScale === newScale) return;

        const worldPosX = centerX / oldScale - this.state.offset.x;
        const worldPosY = centerY / oldScale - this.state.offset.y;

        this.state.scale = newScale;
        this.state.offset.x = centerX / newScale - worldPosX;
        this.state.offset.y = centerY / newScale - worldPosY;

        this.draw();
    }

    resetZoom() {
        this.state.scale = 1;
        this.state.offset = { x: 0, y: 0 };
        this.draw();
    }

    onZoomSliderChange(event) {
        const newScale = parseFloat(event.target.value);

        // Zoom towards center
        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;

        const oldScale = this.state.scale;

        // Calculate world position at center
        const worldPosX = centerX / oldScale - this.state.offset.x;
        const worldPosY = centerY / oldScale - this.state.offset.y;

        // Update scale
        this.state.scale = newScale;

        // Adjust offset to keep center point fixed
        this.state.offset.x = centerX / newScale - worldPosX;
        this.state.offset.y = centerY / newScale - worldPosY;

        this.draw();
    }

    setMode(mode) {
        this.state.mode = mode;
        this.state.currentPolygon = [];
        this.state.selectedPoint = null;
        this.draw();
    }

    getUsedColors() {
        // Get unique colors from existing polygons
        const colors = new Set();
        this.state.polygons.forEach(polygon => {
            if (polygon.color) {
                colors.add(polygon.color);
            }
        });
        return Array.from(colors).sort();
    }

    selectColor(color) {
        this.state.color = color;
        this.draw();
    }

    setColor(event) {
        this.state.color = event.target.value;
    }

    clearCanvas() {
        if (!confirm('Clear current drawing?')) return;
        this.state.currentPolygon = [];
        this.state.selectedPolygon = null;
        this.draw();
    }
}

registry.category("view_widgets").add("site_plan_canvas_widget", {
    component: SitePlanCanvasWidget,
});
