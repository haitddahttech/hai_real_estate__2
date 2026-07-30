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
            cachedImage: null,
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
            isDraggingPriceLabel: false,
            priceLabelDragStart: null,
            priceDisplayNumber: 0,
            isRotatingPriceLabel: false,
            isResizingPriceLabel: false,
        });

        // Ngữ cảnh của thao tác xoay nhãn giá, chốt lại lúc mousedown:
        // { pivot, lastPointerAngle, rotation }. Giữ ngoài useState vì đây là dữ
        // liệu tạm của một cử chỉ chuột, không cần OWL theo dõi để re-render.
        this.priceLabelRotateGesture = null;
        // Đỉnh ô giá đang được kéo: { cornerIndex }.
        this.priceLabelResizeGesture = null;
        // Id của requestAnimationFrame đang chờ vẽ (gộp nhiều mousemove thành 1 lần vẽ)
        this.pendingDrawFrame = null;

        onMounted(() => {
            this.initCanvas();
            this.loadPolygons();
        });

        onWillUnmount(() => {
            if (this.pendingDrawFrame !== null) {
                cancelAnimationFrame(this.pendingDrawFrame);
                this.pendingDrawFrame = null;
            }
            if (this.canvas) {
                this.canvas.removeEventListener('mousedown', this.handleMouseDown);
                this.canvas.removeEventListener('mousemove', this.handleMouseMove);
                this.canvas.removeEventListener('mouseup', this.handleMouseUp);
                this.canvas.removeEventListener('dblclick', this.handleDoubleClick);
                this.canvas.removeEventListener('wheel', this.handleWheel);
                document.removeEventListener('mouseup', this.handleDocumentMouseUp);
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
        this.handleDocumentMouseUp = this.onDocumentMouseUp.bind(this);
        this.handleDoubleClick = this.onDoubleClick.bind(this);
        this.handleWheel = this.onWheel.bind(this);
        this.handleKeyDown = this.onKeyDown.bind(this);

        this.canvas.addEventListener('mousedown', this.handleMouseDown);
        this.canvas.addEventListener('mousemove', this.handleMouseMove);
        this.canvas.addEventListener('mouseup', this.handleMouseUp);
        this.canvas.addEventListener('dblclick', this.handleDoubleClick);
        this.canvas.addEventListener('wheel', this.handleWheel, { passive: false });
        this.canvas.addEventListener('contextmenu', (e) => e.preventDefault()); // Prevent right-click menu
        // Nhả chuột ngoài canvas vẫn phải kết thúc thao tác, nếu không cờ kéo/xoay
        // còn kẹt lại và hình sẽ "tự chạy" theo chuột ở lần di tiếp theo.
        document.addEventListener('mouseup', this.handleDocumentMouseUp);
        document.addEventListener('keydown', this.handleKeyDown);

        this.draw();
    }

    resizeCanvas() {
        if (!this.canvas) return;

        const container = this.canvas.parentElement;
        const rect = container.getBoundingClientRect();

        // High-resolution multiplier for crisp rendering
        // Reduced to 2 to match portal and improve performance
        const RESOLUTION_SCALE = 2;

        const displayWidth = rect.width;
        let displayHeight;

        // Use image aspect ratio if loaded, otherwise fallback to 3:2
        if (this.state.imageLoaded && this.state.image) {
            const imgAspect = this.state.image.width / this.state.image.height;
            displayHeight = Math.round(displayWidth / imgAspect);
        } else {
            // Maintain 3:2 aspect ratio (1200:800) default
            displayHeight = Math.round(displayWidth * (800 / 1200));
        }

        // Set canvas internal resolution
        this.canvas.width = displayWidth * RESOLUTION_SCALE;
        this.canvas.height = displayHeight * RESOLUTION_SCALE;

        // Set display size (CSS pixels)
        this.canvas.style.width = displayWidth + 'px';
        this.canvas.style.height = displayHeight + 'px';

        // Store scale factor for use in draw()
        this.resolutionScale = RESOLUTION_SCALE;

        // Enable high-quality image smoothing
        this.ctx.imageSmoothingEnabled = true;
        this.ctx.imageSmoothingQuality = 'high';

        // Redraw if image loaded
        if (this.state.imageLoaded) {
            this.draw();
        }
    }

    async loadImage() {
        const recordId = this.props.record.resId;
        if (!recordId) return;

        try {
            // Priority 1: Use the physical file saved to static disk (NO compression from Odoo)
            const record = await this.orm.read('site.plan', [recordId], ['image_path', 'image']);

            if (record && record[0] && record[0].image_path) {
                const img = new Image();
                img.onload = () => {
                    this.state.image = img;
                    this.state.imageLoaded = true;
                    this.createDownsampledImage();
                    this.resizeCanvas();
                };
                img.onerror = () => {
                    console.warn("Failed to load image from disk path:", record[0].image_path);
                    this.loadFallbackImage(recordId, record[0]);
                };
                // Adding timestamp to bypass browser cache if image was updated
                img.src = record[0].image_path + '?t=' + Date.now();
                return;
            }

            // Fallback methods if image_path doesn't exist
            await this.loadFallbackImage(recordId, record ? record[0] : null);

        } catch (error) {
            console.error('Error loading image:', error);
        }
    }

    async loadFallbackImage(recordId, recordData) {
        try {
            // Priority 2: Use ir.attachment to get original untouched binary
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
                const attachmentId = attachments[0].id;
                const img = new Image();
                img.onload = () => {
                    this.state.image = img;
                    this.state.imageLoaded = true;
                    this.createDownsampledImage();
                    this.resizeCanvas();
                };
                img.src = `/web/content/${attachmentId}?unique=${attachments[0].checksum}`;
                return;
            }

            // Priority 3: Fallback to base64
            if (recordData && recordData.image) {
                const img = new Image();
                img.onload = () => {
                    this.state.image = img;
                    this.state.imageLoaded = true;
                    this.createDownsampledImage();
                    this.resizeCanvas();
                };
                img.src = `data:image/png;base64,${recordData.image}`;
            }
        } catch (error) {
            console.error('Error loading fallback image:', error);
        }
    }

    createDownsampledImage() {
        if (!this.state.image) return;

        // Target width smaller than full image for performance (e.g., 2048px)
        const targetWidth = 2048;
        if (this.state.image.width <= targetWidth) {
            this.state.cachedImage = this.state.image;
            return;
        }

        const scale = targetWidth / this.state.image.width;
        const offCanvas = document.createElement('canvas');
        offCanvas.width = this.state.image.width * scale;
        offCanvas.height = this.state.image.height * scale;

        const offCtx = offCanvas.getContext('2d');
        offCtx.imageSmoothingEnabled = true;
        offCtx.imageSmoothingQuality = 'high';
        offCtx.drawImage(this.state.image, 0, 0, offCanvas.width, offCanvas.height);

        this.state.cachedImage = offCanvas;
    }

    async loadPolygons() {
        const recordId = this.props.record.resId;
        if (!recordId) return;

        try {
            const sitePlanData = await this.orm.read('site.plan', [recordId], ['price_display_number']);
            const polygons = await this.orm.searchRead(
                'site.plan.polygon',
                [['site_plan_id', '=', recordId]],
                ['name', 'coordinates', 'color', 'polygon_type', 'product_template_id', 'price_label_x', 'price_label_y', 'price_label_rotation', 'price_label_width', 'price_label_height', 'price_label_corners']
            );
            this.state.priceDisplayNumber = parseInt(sitePlanData?.[0]?.price_display_number || 0, 10);

            const productIds = polygons
                .map((polygon) => polygon.product_template_id && polygon.product_template_id[0])
                .filter(Boolean);
            let productsById = {};
            if (productIds.length) {
                const products = await this.orm.read('product.template', productIds, ['list_price']);
                productsById = Object.fromEntries(products.map((product) => [product.id, product]));
            }

            this.state.polygons = polygons.map(p => ({
                id: p.id,
                name: p.name,
                points: JSON.parse(p.coordinates),
                color: p.color || '#3498db',
                type: p.polygon_type,
                productId: p.product_template_id[0],
                productName: p.product_template_id[1],
                productPrice: productsById[p.product_template_id[0]]?.list_price,
                priceLabelX: p.price_label_x,
                priceLabelY: p.price_label_y,
                priceLabelRotation: p.price_label_rotation || 0,
                priceLabelWidth: p.price_label_width || 0,
                priceLabelHeight: p.price_label_height || 0,
                priceLabelCorners: this.parsePriceLabelCorners(p.price_label_corners),
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
                if (this.state.selectedPolygon !== null) {
                    const selectedPolygon = this.state.polygons[this.state.selectedPolygon];
                    if (this.isPointOnPriceLabelRotateHandle(pos, selectedPolygon)) {
                        // Chốt tâm xoay + góc con trỏ ngay lúc bấm. Nhờ vậy ô xoay
                        // đúng bằng lượng chuột đã quét, thay vì nhảy ngay đến góc
                        // tuyệt đối của con trỏ.
                        const quad = this.getPriceLabelQuad(selectedPolygon);
                        if (quad && this.ensurePriceLabelCorners(selectedPolygon)) {
                            const pivot = this.getPriceLabelCentroid(selectedPolygon.priceLabelCorners);
                            this.priceLabelRotateGesture = {
                                pivot,
                                lastPointerAngle: this.getPointerAngleDegrees(pivot, pos),
                            };
                            this.state.isRotatingPriceLabel = true;
                            this.canvas.style.cursor = 'grabbing';
                            return;
                        }
                    }

                    // Kéo 1 trong 4 đỉnh — mỗi đỉnh đi độc lập, ô không bắt buộc
                    // phải giữ hình chữ nhật. Phải xét trước khi xét "bấm trong ô"
                    // vì tay nắm đỉnh nằm chồng lên mép ô.
                    const cornerIndex = this.findPriceLabelCornerAtPosition(pos, selectedPolygon);
                    if (cornerIndex !== -1) {
                        this.startPriceLabelCornerDrag(selectedPolygon, cornerIndex);
                        return;
                    }
                }

                if (this.state.selectedPolygon !== null && this.isPointOnPriceLabelHandle(pos, this.state.polygons[this.state.selectedPolygon])) {
                    this.state.isDraggingPriceLabel = true;
                    this.state.priceLabelDragStart = pos;
                    this.canvas.style.cursor = 'move';
                    return;
                }

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
            this.requestDraw();
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
            if (Number.isFinite(polygon.priceLabelX) && Number.isFinite(polygon.priceLabelY)) {
                polygon.priceLabelX += dx;
                polygon.priceLabelY += dy;
            }
            this.translatePriceLabelCorners(polygon, dx, dy);

            this.state.polygonDragStart = pos;
            this.requestDraw();
            return;
        }

        if (this.state.isDraggingPriceLabel && this.state.selectedPolygon !== null) {
            const pos = this.getMousePos(e);
            const polygon = this.state.polygons[this.state.selectedPolygon];
            const dx = pos.x - this.state.priceLabelDragStart.x;
            const dy = pos.y - this.state.priceLabelDragStart.y;
            polygon.priceLabelX = (polygon.priceLabelX || 0) + dx;
            polygon.priceLabelY = (polygon.priceLabelY || 0) + dy;
            this.translatePriceLabelCorners(polygon, dx, dy);
            this.state.priceLabelDragStart = pos;
            this.requestDraw();
            return;
        }

        if (this.state.isRotatingPriceLabel && this.state.selectedPolygon !== null) {
            const gesture = this.priceLabelRotateGesture;
            if (!gesture) {
                return;
            }
            const pos = this.getMousePos(e);
            const polygon = this.state.polygons[this.state.selectedPolygon];
            const pointerAngle = this.getPointerAngleDegrees(gesture.pivot, pos);

            // Cộng dồn từng bước nhỏ (đã quy về [-180, 180]) để quay qua mốc
            // ±180° vẫn liên tục, không bị nhảy một vòng.
            const delta = this.normalizeDeltaAngle(pointerAngle - gesture.lastPointerAngle);
            gesture.lastPointerAngle = pointerAngle;

            this.rotatePriceLabelCorners(polygon, delta);
            // Vẫn cộng dồn vào priceLabelRotation để góc xoay không mất khi người
            // dùng trả ô về hình chữ nhật mặc định.
            polygon.priceLabelRotation = this.normalizeAngle((polygon.priceLabelRotation || 0) + delta);
            this.requestDraw();
            return;
        }

        if (this.state.isResizingPriceLabel && this.state.selectedPolygon !== null) {
            if (!this.priceLabelResizeGesture) {
                return;
            }
            this.applyPriceLabelCornerDrag(this.getMousePos(e));
            this.requestDraw();
            return;
        }

        // Handle point dragging
        if (this.state.draggedPointIndex !== null) {
            const pos = this.getMousePos(e);
            this.state.currentPolygon[this.state.draggedPointIndex] = pos;
            this.requestDraw();
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
            this.requestDraw();
        } else if (this.state.mode === 'edit' && this.state.selectedPoint !== null) {
            const pos = this.getMousePos(e);
            const polygon = this.state.polygons[this.state.selectedPolygon];
            polygon.points[this.state.selectedPoint] = pos;
            this.requestDraw();
        } else if (this.state.mode === 'select' && this.state.selectedPolygon !== null) {
            // Gợi ý con trỏ khi rê qua tay nắm của ô giá
            const pos = this.getMousePos(e);
            const polygon = this.state.polygons[this.state.selectedPolygon];
            let cursor = 'crosshair';
            const hoveredCorner = this.findPriceLabelCornerAtPosition(pos, polygon);
            if (this.isPointOnPriceLabelRotateHandle(pos, polygon)) {
                cursor = 'grab';
            } else if (hoveredCorner !== -1) {
                cursor = 'grab';
            } else if (this.isPointOnPriceLabelHandle(pos, polygon)) {
                cursor = 'move';
            }
            if (this.canvas.style.cursor !== cursor) {
                this.canvas.style.cursor = cursor;
            }
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

        if (this.state.isDraggingPriceLabel) {
            this.state.isDraggingPriceLabel = false;
            this.state.priceLabelDragStart = null;
            this.canvas.style.cursor = 'crosshair';

            if (this.state.selectedPolygon !== null) {
                this.savePriceLabelPosition(this.state.selectedPolygon);
            }
            return;
        }

        if (this.state.isRotatingPriceLabel) {
            this.state.isRotatingPriceLabel = false;
            this.priceLabelRotateGesture = null;
            this.canvas.style.cursor = 'crosshair';
            this.draw();

            if (this.state.selectedPolygon !== null) {
                this.savePriceLabelPosition(this.state.selectedPolygon);
            }
            return;
        }

        if (this.state.isResizingPriceLabel) {
            this.state.isResizingPriceLabel = false;
            this.priceLabelResizeGesture = null;
            this.canvas.style.cursor = 'crosshair';
            this.draw();

            if (this.state.selectedPolygon !== null) {
                this.savePriceLabelPosition(this.state.selectedPolygon);
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

    /**
     * Chốt hạ thao tác khi người dùng nhả chuột bên ngoài canvas.
     *
     * Chỉ xử lý khi đang có cử chỉ kéo/xoay dở dang, và bỏ qua sự kiện phát ra
     * từ chính canvas (onMouseUp đã chạy rồi, sự kiện nổi bọt lên document).
     */
    onDocumentMouseUp(e) {
        if (e.target === this.canvas) {
            return;
        }
        const busy = this.state.isPanning
            || this.state.isDraggingPolygon
            || this.state.isDraggingPriceLabel
            || this.state.isRotatingPriceLabel
            || this.state.isResizingPriceLabel
            || this.state.draggedPointIndex !== null;
        if (busy) {
            this.onMouseUp(e);
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

        // Nháy đúp vào ô giá: trả ô về kích thước tự động
        if (this.state.mode === 'select' && this.state.selectedPolygon !== null) {
            const pos = this.getMousePos(e);
            const polygon = this.state.polygons[this.state.selectedPolygon];
            const onCorner = this.findPriceLabelCornerAtPosition(pos, polygon) !== -1;
            if (onCorner || this.isPointOnPriceLabelHandle(pos, polygon)) {
                this.resetPriceLabelSize(this.state.selectedPolygon);
            }
        }
    }

    onWheel(e) {
        e.preventDefault();

        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // Calculate zoom factor
        const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9; // Scroll up = zoom in, scroll down = zoom out
        const oldScale = this.state.scale;
        const newScale = Math.max(0.1, Math.min(30, oldScale * zoomFactor));

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

    /**
     * Gộp các yêu cầu vẽ trong cùng một khung hình.
     *
     * Chuột có thể bắn ra hơn 100 sự kiện mousemove mỗi giây, trong khi mỗi lần
     * draw() phải vẽ lại toàn bộ ảnh nền ở chế độ khử răng cưa cao. Gọi draw()
     * trực tiếp trong mousemove khiến hàng đợi sự kiện bị dồn và thao tác kéo /
     * xoay giật cục. Ở đây chỉ vẽ tối đa 1 lần mỗi khung hình.
     */
    requestDraw() {
        if (this.pendingDrawFrame !== null) {
            return;
        }
        this.pendingDrawFrame = requestAnimationFrame(() => {
            this.pendingDrawFrame = null;
            this.draw();
        });
    }

    draw() {
        if (!this.ctx) return;

        // Vẽ ngay thì bỏ khung hình đang chờ, tránh vẽ thừa một lần nữa
        if (this.pendingDrawFrame !== null) {
            cancelAnimationFrame(this.pendingDrawFrame);
            this.pendingDrawFrame = null;
        }

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
        this.displayScaleX = displayWidth / 1200;
        this.displayScaleY = displayHeight / 800;

        // Scale coordinates from reference size (1200x800) to current display size
        const scaleX = this.displayScaleX;
        const scaleY = this.displayScaleY;
        this.ctx.scale(scaleX, scaleY);

        // Apply user zoom and pan
        this.ctx.scale(this.state.scale, this.state.scale);
        this.ctx.translate(this.state.offset.x, this.state.offset.y);

        // Draw image at highest possible quality by bypassing canvas CTM bugs at extreme scales
        // We do this by calculating the exact visible crop of the image and using the 9-argument drawImage
        if (this.state.imageLoaded && this.state.image) {
            let imgToDraw = this.state.image;
            // Use downsampled image if zoom is low
            if (this.state.scale <= 1.5 && this.state.cachedImage) {
                imgToDraw = this.state.cachedImage;
            }

            this.ctx.save();
            // Reset to identity (plus resolution scale for Retina)
            this.ctx.setTransform(resScale, 0, 0, resScale, 0, 0);

            // Always enable smoothing to prevent pixelated image when zooming in
            this.ctx.imageSmoothingEnabled = true;
            this.ctx.imageSmoothingQuality = 'high';

            // The image corresponds to the 1200x800 logical space.
            const sRatioX = imgToDraw.width / 1200;
            const sRatioY = imgToDraw.height / 800;

            // Visible world coordinates
            const worldLeft = -this.state.offset.x;
            const worldTop = -this.state.offset.y;
            const worldRight = (1200 / this.state.scale) - this.state.offset.x;
            const worldBottom = (800 / this.state.scale) - this.state.offset.y;

            // Clamp source world coordinates to [0..1200] and [0..800]
            const cropWorldLeft = Math.max(0, worldLeft);
            const cropWorldTop = Math.max(0, worldTop);
            const cropWorldRight = Math.min(1200, worldRight);
            const cropWorldBottom = Math.min(800, worldBottom);

            if (cropWorldRight > cropWorldLeft && cropWorldBottom > cropWorldTop) {
                // Calculate source pixel coordinates (from the img object)
                const sx = cropWorldLeft * sRatioX;
                const sy = cropWorldTop * sRatioY;
                const sWidth = (cropWorldRight - cropWorldLeft) * sRatioX;
                const sHeight = (cropWorldBottom - cropWorldTop) * sRatioY;

                // Calculate destination screen coordinates (CSS pixels)
                const worldVisibleW = worldRight - worldLeft;
                const worldVisibleH = worldBottom - worldTop;

                const dx = ((cropWorldLeft - worldLeft) / worldVisibleW) * displayWidth;
                const dy = ((cropWorldTop - worldTop) / worldVisibleH) * displayHeight;
                const dWidth = ((cropWorldRight - cropWorldLeft) / worldVisibleW) * displayWidth;
                const dHeight = ((cropWorldBottom - cropWorldTop) / worldVisibleH) * displayHeight;

                this.ctx.drawImage(imgToDraw,
                    sx, sy, sWidth, sHeight,
                    dx, dy, dWidth, dHeight
                );
            }

            this.ctx.restore();
        }


        // Draw saved polygons (coordinates in 1200x800 space)
        this.state.polygons.forEach((polygon, index) => {
            this.drawPolygon(
                polygon.points,
                polygon.color,
                index === this.state.selectedPolygon,
                polygon.name,
                false,
                polygon
            );
        });

        // Draw current polygon being drawn
        if (this.state.currentPolygon.length > 0) {
            this.drawPolygon(this.state.currentPolygon, this.state.color, false, null, true, null);
        }

        // Restore context
        this.ctx.restore();
    }

    drawPolygon(points, color, isSelected, label, isDrawing = false, polygon = null) {
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
        this.ctx.lineWidth = (isSelected ? 2 : 1) / this.state.scale;
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

        if (!isDrawing && polygon && isSelected && this.getPriceDisplayNumber() > 0) {
            this.drawPriceLabel(polygon, isSelected);
        }
    }

    getPriceDisplayNumber() {
        return parseInt(this.state.priceDisplayNumber || this.props.record.data.price_display_number || 0, 10);
    }

    getPriceLabelDisplayText(polygon) {
        const displayNumber = this.getPriceDisplayNumber();
        if (!displayNumber || displayNumber <= 0) {
            return '';
        }

        const price = polygon.productPrice;
        if (price === null || price === undefined || price === '') {
            return '';
        }

        const digitsOnly = String(price).replace(/\D/g, '');
        if (!digitsOnly || digitsOnly.length < displayNumber) {
            return '';
        }

        const formattedPrice = Number(price).toLocaleString('en-US', {
            maximumFractionDigits: 0,
            useGrouping: true,
        });

        let digitCount = 0;
        let label = '';
        for (const char of formattedPrice) {
            if (/\d/.test(char)) {
                digitCount += 1;
            }
            label += char;
            if (digitCount >= displayNumber) {
                break;
            }
        }
        return label.replace(/[^\d]+$/, '');
    }

    getDefaultPriceLabelPosition(points) {
        const minX = Math.min(...points.map(point => point.x));
        const minY = Math.min(...points.map(point => point.y));
        return { x: minX + 8, y: minY + 16 };
    }

    getPriceLabelPosition(polygon) {
        if (
            Number.isFinite(polygon.priceLabelX)
            && Number.isFinite(polygon.priceLabelY)
            && !(polygon.priceLabelX === 0 && polygon.priceLabelY === 0)
        ) {
            return { x: polygon.priceLabelX, y: polygon.priceLabelY };
        }
        return this.getDefaultPriceLabelPosition(polygon.points);
    }

    getPriceLabelBox(polygon) {
        const priceText = this.getPriceLabelDisplayText(polygon);
        if (!priceText || !this.ctx) {
            return null;
        }

        const position = this.getPriceLabelPosition(polygon);
        const fontSize = 4.5;
        const horizontalPadding = 1.75;
        const verticalPadding = 1.5;

        this.ctx.save();
        this.ctx.font = `bold ${fontSize}px Arial`;
        const textWidth = this.ctx.measureText(priceText).width;
        this.ctx.restore();

        // Kích thước "tự nhiên" — vừa khít chuỗi giá với cỡ chữ mặc định.
        const autoBoxWidth = textWidth + horizontalPadding * 2;
        const autoBoxHeight = fontSize + verticalPadding * 2;

        // Kích thước hình chữ nhật mặc định. Chỉ còn dùng khi polygon chưa có
        // priceLabelCorners — hễ người dùng đã kéo đỉnh thì 4 đỉnh mới là nguồn.
        const boxWidth = polygon.priceLabelWidth > 0 ? polygon.priceLabelWidth : autoBoxWidth;
        const boxHeight = polygon.priceLabelHeight > 0 ? polygon.priceLabelHeight : autoBoxHeight;

        const boxX = position.x - horizontalPadding;
        const boxY = position.y - boxHeight / 2;

        return {
            priceText,
            fontSize,
            horizontalPadding,
            verticalPadding,
            autoBoxWidth,
            autoBoxHeight,
            boxWidth,
            boxHeight,
            boxX,
            boxY,
            rotation: polygon.priceLabelRotation || 0,
            centerX: boxX + boxWidth / 2,
            centerY: position.y,
        };
    }

    /**
     * 4 đỉnh của ô giá suy ra từ hình chữ nhật + góc xoay.
     * Chỉ dùng khi polygon chưa có priceLabelCorners.
     * Thứ tự: 0 = trên-trái, 1 = trên-phải, 2 = dưới-phải, 3 = dưới-trái.
     */
    getPriceLabelRectCorners(labelBox) {
        const halfWidth = labelBox.boxWidth / 2;
        const halfHeight = labelBox.boxHeight / 2;
        const angle = (labelBox.rotation * Math.PI) / 180;
        const cos = Math.cos(angle);
        const sin = Math.sin(angle);

        return [
            { sx: -1, sy: -1 },
            { sx: 1, sy: -1 },
            { sx: 1, sy: 1 },
            { sx: -1, sy: 1 },
        ].map((corner) => {
            const localX = corner.sx * halfWidth;
            const localY = corner.sy * halfHeight;
            return {
                x: labelBox.centerX + localX * cos - localY * sin,
                y: labelBox.centerY + localX * sin + localY * cos,
            };
        });
    }

    /** Đọc 4 đỉnh từ chuỗi JSON của DB; dữ liệu hỏng thì coi như chưa có. */
    parsePriceLabelCorners(raw) {
        if (!raw) {
            return null;
        }
        try {
            const parsed = JSON.parse(raw);
            return this.isValidPriceLabelCorners(parsed)
                ? parsed.map(point => ({ x: point.x, y: point.y }))
                : null;
        } catch (error) {
            console.warn('Toạ độ 4 đỉnh ô giá không đọc được:', error);
            return null;
        }
    }

    serializePriceLabelCorners(corners) {
        return this.isValidPriceLabelCorners(corners)
            ? JSON.stringify(corners.map(point => ({ x: point.x, y: point.y })))
            : false;
    }

    /** Kiểm tra một giá trị có phải mảng 4 điểm hợp lệ hay không. */
    isValidPriceLabelCorners(corners) {
        return Array.isArray(corners)
            && corners.length === 4
            && corners.every(point => point && Number.isFinite(point.x) && Number.isFinite(point.y));
    }

    /**
     * Hình dạng thật sự của ô giá: 4 đỉnh tự do nếu người dùng đã kéo, ngược lại
     * là hình chữ nhật mặc định. Đây là hàm duy nhất mọi thao tác vẽ / bắt chuột
     * dùng đến, nên phần còn lại không cần biết ô đang ở dạng nào.
     */
    getPriceLabelQuad(polygon) {
        const labelBox = this.getPriceLabelBox(polygon);
        if (!labelBox) {
            return null;
        }
        const corners = this.isValidPriceLabelCorners(polygon.priceLabelCorners)
            ? polygon.priceLabelCorners.map(point => ({ x: point.x, y: point.y }))
            : this.getPriceLabelRectCorners(labelBox);
        return { labelBox, corners };
    }

    getPriceLabelCentroid(corners) {
        return {
            x: corners.reduce((sum, point) => sum + point.x, 0) / corners.length,
            y: corners.reduce((sum, point) => sum + point.y, 0) / corners.length,
        };
    }

    /**
     * Chuyển ô giá sang dạng 4 đỉnh tự do (nếu chưa) để mọi thao tác kéo thả
     * sau đó chỉ còn phải làm việc với toạ độ đỉnh.
     */
    ensurePriceLabelCorners(polygon) {
        if (this.isValidPriceLabelCorners(polygon.priceLabelCorners)) {
            return polygon.priceLabelCorners;
        }
        const quad = this.getPriceLabelQuad(polygon);
        if (!quad) {
            return null;
        }
        polygon.priceLabelCorners = quad.corners;
        // Kích thước hình chữ nhật đã được nuốt vào toạ độ đỉnh, giữ lại chỉ gây
        // hiểu nhầm về nguồn dữ liệu nào đang có hiệu lực.
        polygon.priceLabelWidth = 0;
        polygon.priceLabelHeight = 0;
        return polygon.priceLabelCorners;
    }

    /**
     * Hệ số quy đổi cho các chi tiết điều khiển (chấm ở đỉnh, tay nắm xoay,
     * nét viền chọn): canvas đã nhân sẵn state.scale khi zoom, nên chia lại để
     * chúng giữ nguyên kích thước trên màn hình thay vì to lên theo ảnh.
     * Cùng quy ước với pointRadius / lineWidth trong drawPolygon().
     */
    getHandleScale() {
        return 1 / (this.state.scale || 1);
    }

    getPriceLabelCornerHandleRadius() {
        // Nhỏ hơn tay nắm xoay để không nuốt mất vùng bấm của nó
        return 1.9 * this.getHandleScale();
    }

    drawPriceLabelCornerHandles(corners) {
        const handleScale = this.getHandleScale();
        const radius = this.getPriceLabelCornerHandleRadius();
        this.ctx.save();
        this.ctx.lineWidth = 0.4 * handleScale;
        corners.forEach((corner) => {
            this.ctx.beginPath();
            this.ctx.arc(corner.x, corner.y, radius, 0, Math.PI * 2);
            this.ctx.fillStyle = '#ffffff';
            this.ctx.fill();
            this.ctx.strokeStyle = '#0d6efd';
            this.ctx.stroke();
        });
        this.ctx.restore();
    }

    /** Trả về đỉnh đang bị trỏ vào (0..3), hoặc -1 nếu không trúng đỉnh nào. */
    findPriceLabelCornerAtPosition(pos, polygon) {
        if (!polygon || this.getPriceDisplayNumber() <= 0) {
            return -1;
        }
        const quad = this.getPriceLabelQuad(polygon);
        if (!quad) {
            return -1;
        }

        let bestIndex = -1;
        // Vùng bấm nới thêm 1.2 — cũng phải theo zoom để bấm trúng đúng cái chấm
        // đang thấy trên màn hình.
        let bestDistance = this.getPriceLabelCornerHandleRadius() + 1.2 * this.getHandleScale();

        quad.corners.forEach((corner, index) => {
            const distance = Math.hypot(pos.x - corner.x, pos.y - corner.y);
            if (distance <= bestDistance) {
                bestDistance = distance;
                bestIndex = index;
            }
        });
        return bestIndex;
    }

    /**
     * Hướng chữ trong ô: lấy trung bình 2 cạnh "ngang" (trên và dưới) nên vẫn
     * hợp lý khi ô đã bị kéo thành hình thang hay hình xiên.
     */
    getPriceLabelTextAngle(corners) {
        const dirX = (corners[1].x - corners[0].x) + (corners[2].x - corners[3].x);
        const dirY = (corners[1].y - corners[0].y) + (corners[2].y - corners[3].y);
        return Math.hypot(dirX, dirY) < 1e-6 ? 0 : Math.atan2(dirY, dirX);
    }

    drawPriceLabel(polygon, isSelected) {
        const quad = this.getPriceLabelQuad(polygon);
        if (!quad) {
            return;
        }

        const { labelBox, corners } = quad;

        // Nền là tứ giác 4 đỉnh tự do — đây là phần duy nhất đổi hình theo
        // thao tác kéo đỉnh.
        this.ctx.save();
        this.ctx.beginPath();
        this.ctx.moveTo(corners[0].x, corners[0].y);
        for (let i = 1; i < corners.length; i++) {
            this.ctx.lineTo(corners[i].x, corners[i].y);
        }
        this.ctx.closePath();
        this.ctx.fillStyle = '#dc3545';
        this.ctx.fill();

        if (isSelected) {
            this.ctx.strokeStyle = '#ffffff';
            this.ctx.lineWidth = 0.5 * this.getHandleScale();
            this.ctx.stroke();
        }
        this.ctx.restore();

        // Chữ giữ nguyên cỡ và tỉ lệ gốc dù ô bị kéo méo tới đâu: chỉ đặt vào
        // tâm ô và nghiêng theo hướng ô, tuyệt đối không co giãn.
        const center = this.getPriceLabelCentroid(corners);
        this.ctx.save();
        this.ctx.translate(center.x, center.y);
        this.ctx.rotate(this.getPriceLabelTextAngle(corners));
        this.ctx.font = `bold ${labelBox.fontSize}px Arial`;
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillStyle = '#ffffff';
        this.ctx.fillText(labelBox.priceText, 0, 0);
        this.ctx.restore();

        if (isSelected) {
            this.drawPriceLabelRotateHandle(corners);
            this.drawPriceLabelCornerHandles(corners);
        }
    }

    isPointOnPriceLabelHandle(pos, polygon) {
        if (!polygon || this.getPriceDisplayNumber() <= 0) {
            return false;
        }

        const quad = this.getPriceLabelQuad(polygon);
        return quad ? this.isPointInPolygon(pos, quad.corners) : false;
    }

    /**
     * Tay nắm xoay nằm ngoài cạnh trên, trên đường nối từ tâm ô ra trung điểm
     * cạnh đó — cách đặt này vẫn hợp lý với tứ giác méo bất kỳ.
     */
    getPriceLabelRotateHandle(corners) {
        const handleScale = this.getHandleScale();
        const radius = 2.8 * handleScale;
        const gap = 2.5 * handleScale;
        const centroid = this.getPriceLabelCentroid(corners);
        const topMiddle = {
            x: (corners[0].x + corners[1].x) / 2,
            y: (corners[0].y + corners[1].y) / 2,
        };

        let dirX = topMiddle.x - centroid.x;
        let dirY = topMiddle.y - centroid.y;
        const length = Math.hypot(dirX, dirY);
        if (length < 1e-6) {
            dirX = 0;
            dirY = -1;
        } else {
            dirX /= length;
            dirY /= length;
        }

        return {
            x: topMiddle.x + dirX * (gap + radius),
            y: topMiddle.y + dirY * (gap + radius),
            radius,
        };
    }

    drawPriceLabelRotateHandle(corners) {
        const handleScale = this.getHandleScale();
        const handle = this.getPriceLabelRotateHandle(corners);
        this.ctx.save();
        this.ctx.fillStyle = '#ffffff';
        this.ctx.beginPath();
        this.ctx.arc(handle.x, handle.y, handle.radius, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.strokeStyle = '#0d6efd';
        this.ctx.lineWidth = 0.4 * handleScale;
        this.ctx.stroke();
        this.ctx.fillStyle = '#0d6efd';
        this.ctx.font = `bold ${3 * handleScale}px Arial`;
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText('↻', handle.x, handle.y + 0.1 * handleScale);
        this.ctx.restore();
    }

    isPointOnPriceLabelRotateHandle(pos, polygon) {
        if (!polygon || this.getPriceDisplayNumber() <= 0) {
            return false;
        }
        const quad = this.getPriceLabelQuad(polygon);
        if (!quad) {
            return false;
        }
        const handle = this.getPriceLabelRotateHandle(quad.corners);
        const threshold = handle.radius + 1.2 * this.getHandleScale();
        return Math.hypot(pos.x - handle.x, pos.y - handle.y) <= threshold;
    }

    /**
     * Góc (độ) của con trỏ so với tâm xoay, quy chiếu theo trục "trên" của nhãn
     * — tức khi rotation = 0 thì tay nắm nằm ở 0°, trùng hệ quy chiếu của
     * getPriceLabelRotateHandle().
     */
    getPointerAngleDegrees(center, pos) {
        const angle = Math.atan2(pos.y - center.y, pos.x - center.x);
        return (angle * 180) / Math.PI + 90;
    }

    /** Quy một hiệu số góc về [-180, 180) để tránh nhảy 360° khi qua mốc ±180. */
    normalizeDeltaAngle(delta) {
        return ((((delta + 180) % 360) + 360) % 360) - 180;
    }

    /** Quy góc về [0, 360) để giá trị lưu xuống DB không phình vô hạn. */
    normalizeAngle(angle) {
        return ((angle % 360) + 360) % 360;
    }

    /**
     * Bắt đầu kéo một đỉnh. Ô giá được chuyển sang dạng 4 đỉnh tự do ngay tại
     * đây, nên từ lúc này đỉnh đi thẳng theo con trỏ — không còn ràng buộc phải
     * giữ hình chữ nhật.
     */
    startPriceLabelCornerDrag(polygon, cornerIndex) {
        if (!this.ensurePriceLabelCorners(polygon)) {
            return;
        }
        this.priceLabelResizeGesture = { cornerIndex };
        this.state.isResizingPriceLabel = true;
        this.canvas.style.cursor = 'grabbing';
    }

    /** Đặt đỉnh đang kéo đúng vào vị trí con trỏ. */
    applyPriceLabelCornerDrag(pos) {
        const gesture = this.priceLabelResizeGesture;
        const polygon = this.state.polygons[this.state.selectedPolygon];
        if (!gesture || !polygon || !this.isValidPriceLabelCorners(polygon.priceLabelCorners)) {
            return;
        }

        // Thay cả mảng thay vì sửa tại chỗ để OWL nhận ra state đã đổi
        polygon.priceLabelCorners = polygon.priceLabelCorners.map((corner, index) => (
            index === gesture.cornerIndex ? { x: pos.x, y: pos.y } : corner
        ));

        // priceLabelX/Y không còn quyết định hình dạng nhưng vẫn là toạ độ neo
        // dùng khi trả ô về mặc định, nên giữ nó bám theo tâm tứ giác.
        const centroid = this.getPriceLabelCentroid(polygon.priceLabelCorners);
        polygon.priceLabelX = centroid.x;
        polygon.priceLabelY = centroid.y;
    }

    /** Dời cả 4 đỉnh (dùng khi kéo cả ô hoặc kéo cả polygon). */
    translatePriceLabelCorners(polygon, dx, dy) {
        if (!this.isValidPriceLabelCorners(polygon.priceLabelCorners)) {
            return;
        }
        polygon.priceLabelCorners = polygon.priceLabelCorners.map(corner => ({
            x: corner.x + dx,
            y: corner.y + dy,
        }));
    }

    /** Xoay cả 4 đỉnh quanh tâm tứ giác một góc cho trước (độ). */
    rotatePriceLabelCorners(polygon, deltaDegrees) {
        if (!this.isValidPriceLabelCorners(polygon.priceLabelCorners)) {
            return;
        }
        const centroid = this.getPriceLabelCentroid(polygon.priceLabelCorners);
        const angle = (deltaDegrees * Math.PI) / 180;
        const cos = Math.cos(angle);
        const sin = Math.sin(angle);

        polygon.priceLabelCorners = polygon.priceLabelCorners.map((corner) => {
            const dx = corner.x - centroid.x;
            const dy = corner.y - centroid.y;
            return {
                x: centroid.x + dx * cos - dy * sin,
                y: centroid.y + dx * sin + dy * cos,
            };
        });
    }

    /**
     * Trả ô giá về hình chữ nhật tự động (vừa khít chuỗi giá), giữ nguyên tâm ô
     * và góc xoay đã canh.
     */
    async resetPriceLabelSize(polygonIndex) {
        const polygon = this.state.polygons[polygonIndex];
        const hasCustomShape = polygon
            && (this.isValidPriceLabelCorners(polygon.priceLabelCorners)
                || polygon.priceLabelWidth
                || polygon.priceLabelHeight);
        if (!hasCustomShape) {
            return;
        }

        const quad = this.getPriceLabelQuad(polygon);
        const center = quad ? this.getPriceLabelCentroid(quad.corners) : null;

        polygon.priceLabelCorners = null;
        polygon.priceLabelWidth = 0;
        polygon.priceLabelHeight = 0;

        // Đặt lại điểm neo chữ sao cho tâm ô không xê dịch
        if (quad && center) {
            polygon.priceLabelX = center.x - quad.labelBox.autoBoxWidth / 2 + quad.labelBox.horizontalPadding;
            polygon.priceLabelY = center.y;
        }

        this.draw();
        await this.savePriceLabelPosition(polygonIndex);
    }

    async savePolygonDialog(type) {
        const recordId = this.props.record.resId;
        if (!recordId) {
            this.notification.add('Vui lòng lưu bản vẽ trước!', { type: 'warning' });
            return;
        }

        // Get list of products already assigned to any polygon (excluding decorations)
        const usedProductIds = await this.orm.searchRead(
            'site.plan.polygon',
            [['product_template_id.is_decoration', '=', false]],
            ['product_template_id']
        ).then(polygons => polygons.map(p => p.product_template_id[0]).filter(id => id));

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
            const defaultPriceLabelPosition = this.getDefaultPriceLabelPosition(this.state.currentPolygon);

            await this.orm.create('site.plan.polygon', [{
                name: name,
                site_plan_id: recordId,
                product_template_id: productId,
                coordinates: coordinates,
                color: this.state.color,
                polygon_type: type,
                price_label_x: defaultPriceLabelPosition.x,
                price_label_y: defaultPriceLabelPosition.y,
                price_label_rotation: 0,
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
                price_label_x: polygon.priceLabelX,
                price_label_y: polygon.priceLabelY,
                price_label_rotation: polygon.priceLabelRotation || 0,
                price_label_width: polygon.priceLabelWidth || 0,
                price_label_height: polygon.priceLabelHeight || 0,
                price_label_corners: this.serializePriceLabelCorners(polygon.priceLabelCorners),
            });
            // Silent save - no notification
        } catch (error) {
            this.notification.add(`Lỗi khi di chuyển: ${error.message}`, { type: 'danger' });
            // Reload to revert changes
            await this.loadPolygons();
        }
    }

    async savePriceLabelPosition(polygonIndex) {
        const polygon = this.state.polygons[polygonIndex];
        try {
            await this.orm.write('site.plan.polygon', [polygon.id], {
                price_label_x: polygon.priceLabelX,
                price_label_y: polygon.priceLabelY,
                price_label_rotation: polygon.priceLabelRotation || 0,
                price_label_width: polygon.priceLabelWidth || 0,
                price_label_height: polygon.priceLabelHeight || 0,
                price_label_corners: this.serializePriceLabelCorners(polygon.priceLabelCorners),
            });
        } catch (error) {
            this.notification.add(`Lỗi khi cập nhật vị trí giá: ${error.message}`, { type: 'danger' });
            await this.loadPolygons();
        }
    }

    async rotateSelectedPriceLabel(deltaDegrees) {
        if (this.state.selectedPolygon === null || this.getPriceDisplayNumber() <= 0) {
            return;
        }

        const polygon = this.state.polygons[this.state.selectedPolygon];
        const current = polygon.priceLabelRotation || 0;
        polygon.priceLabelRotation = this.normalizeAngle(current + deltaDegrees);
        this.draw();

        try {
            await this.orm.write('site.plan.polygon', [polygon.id], {
                price_label_rotation: polygon.priceLabelRotation,
            });
        } catch (error) {
            this.notification.add(`Lỗi khi xoay giá: ${error.message}`, { type: 'danger' });
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
