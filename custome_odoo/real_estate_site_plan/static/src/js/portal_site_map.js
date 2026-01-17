/**
 * Portal Site Map - Interactive Canvas for viewing properties
 * Supports multiple popups with arrows
 */

(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        if (typeof siteMapData === 'undefined') {
            console.error('Site map data not found');
            return;
        }

        console.log('Portal Site Map loaded');
        console.log('Site map data:', siteMapData);
        console.log('Number of polygons:', siteMapData.polygons.length);

        const canvas = document.getElementById('siteMapCanvas');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');

        // State
        let state = {
            image: null,
            imageLoaded: false,
            polygons: [],
            selectedPolygons: [], // Array of selected polygon indices
            activePopups: [], // Array of popup elements
            scale: 1,
            baseScale: 1, // Base scale to fit image in canvas
            canvasScaleX: 1, // Scale from backend canvas (1200) to current canvas width
            canvasScaleY: 1, // Scale from backend canvas (800) to current canvas height
            offset: { x: 0, y: 0 },
            isPanning: false,
            panStart: null,
            // Touch state
            lastTouchPos: null,
            pinchStartDist: 0,
            pinchStartScale: 1,
            isPinching: false,
        };

        const MAX_POPUPS = 5;

        // Initialize
        init();

        function init() {
            // Set canvas size based on container
            setCanvasSize();
            window.addEventListener('resize', setCanvasSize);

            // Load image (will calculate scale)
            loadImage();

            // Parse polygons
            state.polygons = siteMapData.polygons.map(p => ({
                ...p,
                points: JSON.parse(p.coordinates)
            }));

            console.log('Parsed polygons:', state.polygons);

            // Event listeners
            canvas.addEventListener('click', onCanvasClick);
            canvas.addEventListener('mousedown', onMouseDown);
            canvas.addEventListener('mousemove', onMouseMove);
            canvas.addEventListener('mouseup', onMouseUp);
            canvas.addEventListener('wheel', onWheel, { passive: false });

            // Touch events for mobile
            canvas.addEventListener('touchstart', onTouchStart, { passive: false });
            canvas.addEventListener('touchmove', onTouchMove, { passive: false });
            canvas.addEventListener('touchend', onTouchEnd, { passive: false });

            canvas.addEventListener('contextmenu', (e) => e.preventDefault());

            // Scroll event removed - popups now stay fixed when scrolling
            // Previously: window.addEventListener('scroll', ...) caused popups to move

            // Zoom buttons
            const zoomInBtn = document.getElementById('zoomIn');
            const zoomOutBtn = document.getElementById('zoomOut');
            const resetZoomBtn = document.getElementById('resetZoom');
            const zoomSlider = document.getElementById('zoomSlider');
            const zoomLevel = document.getElementById('zoomLevel');

            if (zoomInBtn) zoomInBtn.addEventListener('click', zoomIn);
            if (zoomOutBtn) zoomOutBtn.addEventListener('click', zoomOut);
            if (resetZoomBtn) resetZoomBtn.addEventListener('click', resetZoom);

            // Zoom slider
            if (zoomSlider) {
                zoomSlider.addEventListener('input', (e) => {
                    const newScale = parseFloat(e.target.value);

                    // Get display dimensions
                    const displayWidth = state.displayWidth || 1200;
                    const displayHeight = state.displayHeight || 800;

                    // Image center in reference space (1200x800)
                    const imageCenterX = 600;  // Half of 1200
                    const imageCenterY = 400;  // Half of 800

                    // Scale to display size
                    const scaleX = displayWidth / 1200;
                    const scaleY = displayHeight / 800;
                    const displayCenterX = imageCenterX * scaleX;
                    const displayCenterY = imageCenterY * scaleY;

                    // Get current screen position of image center
                    const oldScale = state.scale;
                    const screenX = (displayCenterX + state.offset.x) * oldScale;
                    const screenY = (displayCenterY + state.offset.y) * oldScale;

                    // Update scale
                    state.scale = newScale;

                    // Calculate new offset to keep image center at same screen position
                    state.offset.x = screenX / newScale - displayCenterX;
                    state.offset.y = screenY / newScale - displayCenterY;

                    updateZoomDisplay();
                    draw();
                });
            }
        }

        // Update zoom display - moved outside to be accessible by all functions
        function updateZoomDisplay() {
            const zoomSlider = document.getElementById('zoomSlider');
            const zoomLevel = document.getElementById('zoomLevel');
            if (zoomSlider) zoomSlider.value = state.scale;
            if (zoomLevel) zoomLevel.textContent = Math.round(state.scale * 100) + '%';
        }

        function setCanvasSize() {
            const container = canvas.parentElement;
            const rect = container.getBoundingClientRect();

            // High-resolution multiplier for crisp rendering
            const RESOLUTION_SCALE = 3;

            let displayWidth, displayHeight;

            // If image is loaded, use image aspect ratio
            if (state.image) {
                const imgAspect = state.image.width / state.image.height;
                displayWidth = rect.width;
                displayHeight = Math.round(rect.width / imgAspect);
            } else {
                // Default size before image loads
                displayWidth = rect.width;
                displayHeight = Math.round(rect.width * 0.6);
            }

            // Set canvas internal resolution (3x for crisp rendering)
            canvas.width = displayWidth * RESOLUTION_SCALE;
            canvas.height = displayHeight * RESOLUTION_SCALE;

            // Set display size (CSS pixels)
            canvas.style.width = displayWidth + 'px';
            canvas.style.height = displayHeight + 'px';

            // Store scale factor
            state.resolutionScale = RESOLUTION_SCALE;

            // Enable high-quality image smoothing for smooth rendering
            // With 3x resolution, smoothing makes images look better
            ctx.imageSmoothingEnabled = true;
            ctx.imageSmoothingQuality = 'high';

            // Calculate scale factor from backend canvas to current display size
            // Backend canvas: 1200x800
            state.canvasScaleX = displayWidth / 1200;
            state.canvasScaleY = displayHeight / 800;

            // Reset zoom scale and offset
            if (state.imageLoaded) {
                state.scale = 1;
                state.offset = { x: 0, y: 0 };
                draw();
            }
        }

        function loadImage() {
            const img = new Image();
            img.onload = function () {
                state.image = img;
                state.imageLoaded = true;

                // Resize canvas to match image aspect ratio
                setCanvasSize();

                // No scaling - polygons will be scaled by canvasScale
                state.scale = 1;
                state.offset = { x: 0, y: 0 };

                draw();
            };
            img.src = siteMapData.imageUrl;
        }

        function draw() {
            if (!ctx) return;

            // Clear
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Save and transform
            ctx.save();

            // Apply resolution scale first (canvas is 3x larger than display)
            const resScale = state.resolutionScale || 1;
            ctx.scale(resScale, resScale);

            // Get display dimensions (CSS pixels)
            const rect = canvas.getBoundingClientRect();
            const displayWidth = parseFloat(canvas.style.width) || rect.width;
            const displayHeight = parseFloat(canvas.style.height) || rect.height;

            // Store in state for use in drawPolygonScaled
            state.displayWidth = displayWidth;
            state.displayHeight = displayHeight;

            // Apply user zoom and pan
            ctx.scale(state.scale, state.scale);
            ctx.translate(state.offset.x, state.offset.y);

            // Draw image at display size
            if (state.imageLoaded && state.image) {
                ctx.drawImage(state.image, 0, 0, displayWidth, displayHeight);
            }


            // Draw polygons (need to scale coordinates from 1200x800 to canvas size)
            state.polygons.forEach((polygon, index) => {
                const isSelected = state.selectedPolygons.includes(index);
                drawPolygonScaled(polygon, isSelected);
            });

            ctx.restore();

            // Draw arrows from polygons to popups
            drawArrows();
        }

        function drawPolygonScaled(polygon, isSelected) {
            const points = polygon.points;
            if (!points || points.length < 3) return;

            // Use display dimensions from state (set in draw() function)
            const displayWidth = state.displayWidth || 1200;
            const displayHeight = state.displayHeight || 800;

            // Scale polygon coordinates from reference space (1200x800) to display size
            const scaleX = displayWidth / 1200;
            const scaleY = displayHeight / 800;

            // Determine border color
            let strokeColor = polygon.color || '#3498db';

            ctx.beginPath();
            ctx.moveTo(points[0].x * scaleX, points[0].y * scaleY);
            for (let i = 1; i < points.length; i++) {
                ctx.lineTo(points[i].x * scaleX, points[i].y * scaleY);
            }
            ctx.closePath();


            // Fill logic: Gray if sold, Transparent otherwise
            if (polygon.product.is_sold) {
                ctx.fillStyle = '#ccccccCC'; // Gray with some transparency (80%)
                ctx.fill();
            } else if (isSelected) {
                // Optional: slight highlight for selection if transparent
                ctx.fillStyle = 'rgba(231, 76, 60, 0.15)';
                ctx.fill();
            }

            // Stroke
            ctx.strokeStyle = isSelected ? '#e74c3c' : strokeColor;
            ctx.lineWidth = (isSelected ? 3 : 2) / state.scale;
            ctx.stroke();

            // Draw label - DISABLED: No longer showing polygon names on portal view
            // const centerX = points.reduce((sum, p) => sum + p.x * scaleX, 0) / points.length;
            // const centerY = points.reduce((sum, p) => sum + p.y * scaleY, 0) / points.length;

            // ctx.fillStyle = '#000';
            // // Font size: static value that scales with the map (zoom in = bigger text)
            // // Base size set to small value so it looks neat at 1x zoom
            // const fontSize = 5;
            // ctx.font = `bold ${fontSize}px Arial`;
            // ctx.textAlign = 'center';
            // ctx.textBaseline = 'middle';
            // ctx.fillText(polygon.name, centerX, centerY);
        }

        function drawArrows() {
            // Get scroll offset for absolute positioning
            const scrollX = window.pageXOffset || document.documentElement.scrollLeft;
            const scrollY = window.pageYOffset || document.documentElement.scrollTop;

            state.activePopups.forEach((popupData) => {
                const polygon = state.polygons[popupData.polygonIndex];
                const popup = popupData.element;
                const arrow = popupData.arrow;

                const canvasRect = canvas.getBoundingClientRect();
                const points = polygon.points;

                // Get popup center (viewport coordinates)
                const popupRect = popup.getBoundingClientRect();
                const popupCenterX = popupRect.left + popupRect.width / 2;
                const popupCenterY = popupRect.top + popupRect.height / 2;

                // Find closest point on polygon edge (in screen coordinates)
                let minDist = Infinity;
                let closestPoint = { x: 0, y: 0 };

                for (let i = 0; i < points.length; i++) {
                    const p1 = points[i];
                    const p2 = points[(i + 1) % points.length];

                    // Convert polygon points from reference space (1200x800) to screen coordinates
                    // Step 1: Get display dimensions (CSS pixels, not canvas pixels)
                    const displayWidth = parseFloat(canvas.style.width) || canvasRect.width;
                    const displayHeight = parseFloat(canvas.style.height) || canvasRect.height;

                    // Step 2: Scale from reference (1200x800) to display size
                    const scaleX = displayWidth / 1200;
                    const scaleY = displayHeight / 800;

                    const canvasX1 = p1.x * scaleX;
                    const canvasY1 = p1.y * scaleY;
                    const canvasX2 = p2.x * scaleX;
                    const canvasY2 = p2.y * scaleY;

                    // Step 3: Apply zoom and pan (in display space)
                    const zoomedX1 = (canvasX1 + state.offset.x) * state.scale;
                    const zoomedY1 = (canvasY1 + state.offset.y) * state.scale;
                    const zoomedX2 = (canvasX2 + state.offset.x) * state.scale;
                    const zoomedY2 = (canvasY2 + state.offset.y) * state.scale;

                    // Step 4: Add canvas offset to get screen coordinates
                    const x1 = canvasRect.left + zoomedX1;
                    const y1 = canvasRect.top + zoomedY1;
                    const x2 = canvasRect.left + zoomedX2;
                    const y2 = canvasRect.top + zoomedY2;

                    // Find closest point on this edge segment
                    const edgePoint = closestPointOnSegment(x1, y1, x2, y2, popupCenterX, popupCenterY);
                    const dist = Math.sqrt(
                        (edgePoint.x - popupCenterX) ** 2 + (edgePoint.y - popupCenterY) ** 2
                    );

                    if (dist < minDist) {
                        minDist = dist;
                        closestPoint = edgePoint;
                    }
                }

                // Calculate angle from polygon to popup
                const dx = popupCenterX - closestPoint.x;
                const dy = popupCenterY - closestPoint.y;
                const angle = Math.atan2(dy, dx);

                // Extend the start point outward to account for stroke width
                // Polygon has stroke width of 2-3px, so extend by ~2px
                const strokeOffset = 2;
                const extendedStartX = closestPoint.x + Math.cos(angle) * strokeOffset;
                const extendedStartY = closestPoint.y + Math.sin(angle) * strokeOffset;

                // Find intersection point on popup edge
                const popupEdgePoint = getPopupEdgePoint(popupRect, angle);

                // Draw arrow from extended point to popup edge
                const arrowDx = popupEdgePoint.x - extendedStartX;
                const arrowDy = popupEdgePoint.y - extendedStartY;
                const arrowAngle = Math.atan2(arrowDy, arrowDx);
                const length = Math.sqrt(arrowDx * arrowDx + arrowDy * arrowDy);

                // Convert viewport coordinates to document coordinates (add scroll offset)
                arrow.style.left = (extendedStartX + scrollX) + 'px';
                arrow.style.top = (extendedStartY + scrollY) + 'px';
                arrow.style.width = length + 'px';
                arrow.style.height = '3px';
                arrow.style.transform = `rotate(${arrowAngle}rad)`;
                arrow.style.transformOrigin = '0 50%';
                arrow.style.background = '#e74c3c';
                arrow.style.position = 'absolute'; // Changed from 'fixed' - arrow now scrolls with page
                arrow.style.zIndex = '999';
                arrow.style.pointerEvents = 'none';
                arrow.style.display = 'block';
            });
        }

        function closestPointOnSegment(x1, y1, x2, y2, px, py) {
            const dx = x2 - x1;
            const dy = y2 - y1;
            const lengthSquared = dx * dx + dy * dy;

            if (lengthSquared === 0) {
                return { x: x1, y: y1 };
            }

            let t = ((px - x1) * dx + (py - y1) * dy) / lengthSquared;
            t = Math.max(0, Math.min(1, t));

            return {
                x: x1 + t * dx,
                y: y1 + t * dy
            };
        }

        function getPopupEdgePoint(rect, angle) {
            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;

            const cos = Math.cos(angle);
            const sin = Math.sin(angle);

            let x, y;

            // Determine which edge the line intersects
            if (Math.abs(cos) > Math.abs(sin)) {
                // Intersects left or right edge
                if (cos > 0) {
                    // Right edge
                    x = rect.right;
                    y = centerY + (x - centerX) * sin / cos;
                } else {
                    // Left edge
                    x = rect.left;
                    y = centerY + (x - centerX) * sin / cos;
                }
            } else {
                // Intersects top or bottom edge
                if (sin > 0) {
                    // Bottom edge
                    y = rect.bottom;
                    x = centerX + (y - centerY) * cos / sin;
                } else {
                    // Top edge
                    y = rect.top;
                    x = centerX + (y - centerY) * cos / sin;
                }
            }

            return { x, y };
        }

        function onCanvasClick(e) {
            const pos = getMousePos(e);
            const clickedIndex = findPolygonAt(pos);

            console.log('Canvas clicked at:', pos);
            console.log('Clicked polygon index:', clickedIndex);

            if (clickedIndex !== -1) {
                const existingIndex = state.selectedPolygons.indexOf(clickedIndex);

                console.log('Polygon found:', state.polygons[clickedIndex]);
                console.log('Existing index:', existingIndex);

                if (existingIndex === -1) {
                    if (state.selectedPolygons.length >= MAX_POPUPS) {
                        removePopup(0);
                    }

                    state.selectedPolygons.push(clickedIndex);
                    console.log('Showing popup for polygon:', clickedIndex);
                    showPopup(state.polygons[clickedIndex], clickedIndex);
                } else {
                    console.log('Removing popup for polygon:', clickedIndex);
                    removePopup(existingIndex);
                }

                draw();
            }
        }

        function showPopup(polygon, polygonIndex) {
            const product = polygon.product;

            const popup = document.createElement('div');
            popup.className = 'card shadow-lg property-popup';
            popup.style.position = 'absolute'; // Changed from 'fixed' - popup now scrolls with page
            popup.style.zIndex = '1000';
            popup.style.maxWidth = '300px';
            popup.style.minWidth = '260px';
            popup.style.cursor = 'move';
            popup.style.overflow = 'visible'; // Allow ribbon to overflow
            popup.style.setProperty('border', `3px solid ${polygon.color || '#3498db'}`, 'important'); // Border matches polygon color


            // Ribbon for sold status
            const ribbonColor = product.is_sold ? '#dc3545' : '#28a745';
            const ribbonText = product.is_sold ? 'ĐÃ BÁN' : 'CÒN TRỐNG';
            const ribbonHTML = `
                <div class="status-ribbon" style="
                    position: absolute;
                    top: -8px;
                    right: -5px;
                    background: ${ribbonColor};
                    color: white;
                    padding: 5px 15px;
                    font-size: 0.7rem;
                    font-weight: 700;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                    z-index: 10;
                    transform: rotate(0deg);
                    border-radius: 3px 0 0 3px;
                ">
                    ${ribbonText}
                    <div style="
                        position: absolute;
                        right: 0;
                        bottom: -5px;
                        width: 0;
                        height: 0;
                        border-left: 5px solid transparent;
                        border-right: 0px solid transparent;
                        border-top: 5px solid ${ribbonColor};
                        filter: brightness(0.7);
                    "></div>
                </div>
            `;

            const propertyTypeBadge = product.property_type
                ? `<span class="badge badge-outline-info badge-outline ms-1" style="font-size: 0.65rem; padding: 0.15rem 0.4rem;">${product.property_type}</span>`
                : '';

            const directionBadge = product.direction
                ? `<span class="badge badge-outline-primary badge-outline ms-1" style="font-size: 0.65rem; padding: 0.15rem 0.4rem;">${product.direction}</span>`
                : '';

            // Get color from image at polygon center
            let bgColor = 'rgba(255, 255, 255, 0.95)';
            let textColor = '#000000';

            try {
                const points = polygon.points;
                const centerX = points.reduce((sum, p) => sum + p.x, 0) / points.length;
                const centerY = points.reduce((sum, p) => sum + p.y, 0) / points.length;

                const displayWidth = parseFloat(canvas.style.width) || canvas.getBoundingClientRect().width;
                const displayHeight = parseFloat(canvas.style.height) || canvas.getBoundingClientRect().height;

                const scaleX = displayWidth / 1200;
                const scaleY = displayHeight / 800;

                const canvasX = Math.floor(centerX * scaleX * state.resolutionScale);
                const canvasY = Math.floor(centerY * scaleY * state.resolutionScale);

                const imageData = ctx.getImageData(canvasX, canvasY, 1, 1);
                const data = imageData.data;

                const r = data[0];
                const g = data[1];
                const b = data[2];

                const brightness = (r * 299 + g * 587 + b * 114) / 1000;
                textColor = brightness > 128 ? '#000000' : '#ffffff';
                bgColor = `rgba(${r}, ${g}, ${b}, 0.95)`;
            } catch (e) {
                console.warn('Could not get color from image:', e);
            }

            // Buyer info display
            const buyerInfo = product.buyer_name
                ? `<div class="mt-1" style="font-size: 0.7rem; opacity: 0.9;">
                       <i class="fa fa-user" style="font-size: 0.65rem;"></i> ${product.buyer_name}
                   </div>`
                : '';

            popup.innerHTML = `
                ${ribbonHTML}
                <div class="card-header border-0 pb-2" style="cursor: move; background: ${bgColor}; color: ${textColor};">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <div class="text-muted mb-1" style="font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; opacity: 0.8;">Mã căn</div>
                            <div class="d-flex align-items-center gap-2">
                                <h6 class="mb-0 fw-bold" style="font-size: 0.95rem;">${product.name}</h6>
                                ${propertyTypeBadge}
                                ${directionBadge}
                            </div>
                            ${buyerInfo}
                        </div>
                        <div class="d-flex align-items-center gap-2">
                            <button type="button" class="btn-close close-popup-btn" style="cursor: pointer; background: white; border-radius: 50%; padding: 0.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); opacity: 0.8;"></button>
                        </div>
                    </div>
                </div>
                <div class="card-body pt-2 pb-3">
                    <div class="px-0">
                        <div class="d-flex justify-content-between mb-1 pb-1 border-bottom border-light">
                            <span class="text-dark fw-medium" style="font-size: 0.8rem;">Diện tích đất</span>
                            <span class="fw-bold text-dark" style="font-size: 0.85rem;">${product.area} m²</span>
                        </div>
                        <div class="d-flex justify-content-between mb-1 pb-1 border-bottom border-light">
                            <span class="text-dark fw-medium" style="font-size: 0.8rem;">DT xây dựng</span>
                            <span class="fw-bold text-dark" style="font-size: 0.85rem;">${product.construction_area || 0} m²</span>
                        </div>
                        <div class="d-flex justify-content-between mb-1 pb-1 border-bottom border-light">
                            <span class="text-dark fw-medium" style="font-size: 0.8rem;">Giá bán</span>
                            <span class="fw-bold text-danger" style="font-size: 0.9rem;">${product.currency_symbol}${formatNumber(product.price)}</span>
                        </div>
                        <div class="d-flex justify-content-between mb-0">
                            <span class="text-dark fw-medium" style="font-size: 0.8rem;">Đơn giá/m²</span>
                            <span class="fw-semibold text-muted" style="font-size: 0.8rem;">${product.currency_symbol}${formatNumber(product.price_per_m2)}</span>
                        </div>
                    </div>
                    <div class="mt-3">
                        <a href="/my/property/${product.id}" class="btn btn-dark w-100 py-1 fw-bold" style="border-radius: 6px; font-size: 0.8rem; letter-spacing: 0.3px;">
                            CHI TIẾT <i class="fa fa-arrow-right ms-1 small"></i>
                        </a>
                    </div>
                </div>
            `;

            const arrow = document.createElement('div');
            arrow.className = 'popup-arrow';
            arrow.style.display = 'none';

            document.body.appendChild(popup);
            document.body.appendChild(arrow);

            positionPopup(popup, polygon, state.activePopups.length);

            // Close button
            popup.querySelector('.close-popup-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                const index = state.activePopups.findIndex(p => p.element === popup);
                if (index !== -1) {
                    removePopup(index);
                    draw();
                }
            });

            // Make popup draggable
            makeDraggable(popup);

            state.activePopups.push({
                element: popup,
                arrow: arrow,
                polygonIndex: polygonIndex
            });

            draw();
        }

        function makeDraggable(popup) {
            let isDragging = false;
            let currentX;
            let currentY;
            let initialX;
            let initialY;

            const header = popup.querySelector('.card-header');

            header.addEventListener('mousedown', dragStart);
            document.addEventListener('mousemove', drag);
            document.addEventListener('mouseup', dragEnd);

            // Add touch support for dragging
            header.addEventListener('touchstart', (e) => {
                if (e.target.classList.contains('btn-close')) return;
                const touch = e.touches[0];
                initialX = touch.clientX - popup.offsetLeft;
                initialY = touch.clientY - popup.offsetTop;
                isDragging = true;
                popup.style.zIndex = '1001';
                e.preventDefault();
            }, { passive: false });

            document.addEventListener('touchmove', (e) => {
                if (isDragging) {
                    const touch = e.touches[0];
                    currentX = touch.clientX - initialX;
                    currentY = touch.clientY - initialY;

                    // Keep popup within document (not just viewport)
                    const docWidth = Math.max(
                        document.documentElement.scrollWidth,
                        document.body.scrollWidth
                    );
                    const docHeight = Math.max(
                        document.documentElement.scrollHeight,
                        document.body.scrollHeight
                    );

                    const minX = 0;
                    const maxX = docWidth - popup.offsetWidth;
                    const minY = 0;
                    const maxY = docHeight - popup.offsetHeight;

                    currentX = Math.max(minX, Math.min(currentX, maxX));
                    currentY = Math.max(minY, Math.min(currentY, maxY));

                    popup.style.left = currentX + 'px';
                    popup.style.top = currentY + 'px';
                    draw();
                    e.preventDefault();
                }
            }, { passive: false });

            document.addEventListener('touchend', () => {
                if (isDragging) {
                    isDragging = false;
                    popup.style.zIndex = '1000';
                }
            });

            function dragStart(e) {
                if (e.target.classList.contains('btn-close')) {
                    return; // Don't drag when clicking close button
                }

                initialX = e.clientX - popup.offsetLeft;
                initialY = e.clientY - popup.offsetTop;

                isDragging = true;
                popup.style.zIndex = '1001'; // Bring to front
            }

            function drag(e) {
                if (isDragging) {
                    e.preventDefault();

                    currentX = e.clientX - initialX;
                    currentY = e.clientY - initialY;

                    // Keep popup within document (not just viewport)
                    // Allow dragging to any part of the page
                    const scrollX = window.pageXOffset || document.documentElement.scrollLeft;
                    const scrollY = window.pageYOffset || document.documentElement.scrollTop;

                    const docWidth = Math.max(
                        document.documentElement.scrollWidth,
                        document.body.scrollWidth
                    );
                    const docHeight = Math.max(
                        document.documentElement.scrollHeight,
                        document.body.scrollHeight
                    );

                    const minX = 0;
                    const maxX = docWidth - popup.offsetWidth;
                    const minY = 0;
                    const maxY = docHeight - popup.offsetHeight;

                    currentX = Math.max(minX, Math.min(currentX, maxX));
                    currentY = Math.max(minY, Math.min(currentY, maxY));

                    popup.style.left = currentX + 'px';
                    popup.style.top = currentY + 'px';

                    // Update arrow
                    draw();
                }
            }

            function dragEnd(e) {
                if (isDragging) {
                    isDragging = false;
                    popup.style.zIndex = '1000';
                }
            }
        }

        function positionPopup(popup, polygon, stackIndex) {
            const canvasRect = canvas.getBoundingClientRect();
            const points = polygon.points;

            // Scale factor to convert 1200x800 coordinates to current canvas size
            const scaleX = canvas.width / 1200;
            const scaleY = canvas.height / 800;

            const centerX = points.reduce((sum, p) => sum + p.x, 0) / points.length;
            const centerY = points.reduce((sum, p) => sum + p.y, 0) / points.length;

            // Point in screen pixels (viewport coordinates)
            const screenX = canvasRect.left + (centerX * scaleX + state.offset.x) * state.scale;
            // const screenY = canvasRect.top + (centerY * scaleY + state.offset.y) * state.scale;

            const popupWidth = 300;
            const popupHeight = 220; // Reduced - sold badge moved to header
            const edgeMargin = 20;
            const verticalSpacing = 230; // Space between stacked popups (height + 10px gap)

            let popupX, popupY;

            // Determine if polygon is on left or right half of CANVAS
            const canvasMidX = canvasRect.left + canvasRect.width / 2;
            const isLeftSide = screenX < canvasMidX;

            if (isLeftSide) {
                // Polygon on left → place popup on LEFT side at top
                popupX = canvasRect.left + edgeMargin;
            } else {
                // Polygon on right → place popup on RIGHT side at top
                popupX = canvasRect.right - popupWidth - edgeMargin;
            }

            // Position at top of canvas
            popupY = canvasRect.top + edgeMargin;

            // Stack vertically if multiple popups (don't overlap)
            popupY += (stackIndex * verticalSpacing);

            // Convert viewport coordinates to document coordinates (add scroll offset)
            const scrollX = window.pageXOffset || document.documentElement.scrollLeft;
            const scrollY = window.pageYOffset || document.documentElement.scrollTop;

            popupX += scrollX;
            popupY += scrollY;

            // Bounds checking (keep within document, accounting for scroll)
            const minX = scrollX + 10;
            const maxX = scrollX + window.innerWidth - popupWidth - 10;
            const minY = scrollY + 10;
            const maxY = scrollY + window.innerHeight - popupHeight - 10;

            popup.style.left = Math.max(minX, Math.min(popupX, maxX)) + 'px';
            popup.style.top = Math.max(minY, Math.min(popupY, maxY)) + 'px';
        }

        function removePopup(index) {
            const popupData = state.activePopups[index];
            if (popupData) {
                popupData.element.remove();
                popupData.arrow.remove();
                state.activePopups.splice(index, 1);
                state.selectedPolygons.splice(index, 1);
            }
        }

        function findPolygonAt(pos) {
            console.log('Finding polygon at position:', pos);
            console.log('Total polygons to check:', state.polygons.length);

            for (let i = state.polygons.length - 1; i >= 0; i--) {
                const polygon = state.polygons[i];
                console.log(`\n=== Polygon ${i}: ${polygon.name} ===`);
                polygon.points.forEach((p, idx) => {
                    console.log(`  Point ${idx}: x=${p.x}, y=${p.y}`);
                });

                // Calculate bounding box
                const minX = Math.min(...polygon.points.map(p => p.x));
                const maxX = Math.max(...polygon.points.map(p => p.x));
                const minY = Math.min(...polygon.points.map(p => p.y));
                const maxY = Math.max(...polygon.points.map(p => p.y));
                console.log(`Bounding box: x[${minX.toFixed(2)}, ${maxX.toFixed(2)}], y[${minY.toFixed(2)}, ${maxY.toFixed(2)}]`);
                console.log(`Click: x=${pos.x.toFixed(2)}, y=${pos.y.toFixed(2)}`);

                const isInside = isPointInPolygon(pos, polygon.points);
                console.log(`Inside? ${isInside}`);

                if (isInside) {
                    return i;
                }
            }
            return -1;
        }

        function isPointInPolygon(point, polygon) {
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

        function getMousePos(e) {
            const rect = canvas.getBoundingClientRect();

            let clientX, clientY;
            if (e.touches && e.touches.length > 0) {
                clientX = e.touches[0].clientX;
                clientY = e.touches[0].clientY;
            } else if (e.changedTouches && e.changedTouches.length > 0) {
                clientX = e.changedTouches[0].clientX;
                clientY = e.changedTouches[0].clientY;
            } else {
                clientX = e.clientX;
                clientY = e.clientY;
            }

            // Get mouse position in canvas pixels
            const canvasX = clientX - rect.left;
            const canvasY = clientY - rect.top;

            // Get display dimensions - use from state for consistency
            const displayWidth = state.displayWidth || rect.width;
            const displayHeight = state.displayHeight || rect.height;

            // Undo zoom and pan FIRST (these are applied in display space)
            // In draw(): ctx.scale(userScale) → ctx.translate(offset) → draw at displayWidth
            const displayX = canvasX / state.scale - state.offset.x;
            const displayY = canvasY / state.scale - state.offset.y;

            // Then convert from display space to reference space (1200x800)
            // Polygon points are scaled: point.x * (displayWidth / 1200)
            // So to get reference coords: displayX * (1200 / displayWidth)
            const scaleX = 1200 / displayWidth;
            const scaleY = 800 / displayHeight;

            const x = displayX * scaleX;
            const y = displayY * scaleY;

            return { x, y };
        }

        function onMouseDown(e) {
            if (e.button === 2) {
                e.preventDefault();
                state.isPanning = true;
                state.panStart = { x: e.clientX, y: e.clientY };
                canvas.style.cursor = 'grabbing';
            }
        }

        function onMouseMove(e) {
            if (state.isPanning && state.panStart) {
                const dx = (e.clientX - state.panStart.x) / state.scale;
                const dy = (e.clientY - state.panStart.y) / state.scale;

                state.offset.x += dx;
                state.offset.y += dy;

                state.panStart = { x: e.clientX, y: e.clientY };
                draw(); // Only redraw canvas and arrows, don't move popups
            }
        }

        function onMouseUp(e) {
            if (state.isPanning) {
                state.isPanning = false;
                state.panStart = null;
                canvas.style.cursor = 'pointer';
            }
        }

        // Touch handlers
        function onTouchStart(e) {
            e.preventDefault();
            if (e.touches.length === 1) {
                state.isPanning = true;
                state.lastTouchPos = { x: e.touches[0].clientX, y: e.touches[0].clientY };
                state.isPinching = false;
            } else if (e.touches.length === 2) {
                state.isPanning = false;
                state.isPinching = true;
                state.pinchStartDist = getPinchDist(e);
                state.pinchStartScale = state.scale;

                // Keep the center point of pinch for smooth zooming
                const rect = canvas.getBoundingClientRect();
                state.lastTouchPos = {
                    x: (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left,
                    y: (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top
                };
            }
        }

        function onTouchMove(e) {
            e.preventDefault();
            if (state.isPanning && e.touches.length === 1) {
                const dx = (e.touches[0].clientX - state.lastTouchPos.x) / state.scale;
                const dy = (e.touches[0].clientY - state.lastTouchPos.y) / state.scale;

                state.offset.x += dx;
                state.offset.y += dy;
                state.lastTouchPos = { x: e.touches[0].clientX, y: e.touches[0].clientY };
                draw();
            } else if (state.isPinching && e.touches.length === 2) {
                const newDist = getPinchDist(e);
                const zoomFactor = newDist / state.pinchStartDist;

                const rect = canvas.getBoundingClientRect();
                const midX = (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left;
                const midY = (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top;

                const worldPosX = midX / state.scale - state.offset.x;
                const worldPosY = midY / state.scale - state.offset.y;

                const newScale = Math.max(1.0, Math.min(10, state.pinchStartScale * zoomFactor));

                state.scale = newScale;
                state.offset.x = midX / newScale - worldPosX;
                state.offset.y = midY / newScale - worldPosY;

                draw();
            }
        }

        function onTouchEnd(e) {
            if (e.touches.length === 0) {
                // If it was a quick tap (not panning or pinching long)
                if (!state.isPinching && state.isPanning) {
                    // Check if it's a tap by distance or time if needed,
                    // but usually mobile browsers handle click events too.
                    // To be safe, trigger click logic if move dist was small
                }
                state.isPanning = false;
                state.isPinching = false;
                state.lastTouchPos = null;
            } else if (e.touches.length === 1) {
                // Switched from pinch to pan
                state.isPanning = true;
                state.isPinching = false;
                state.lastTouchPos = { x: e.touches[0].clientX, y: e.touches[0].clientY };
            }
        }

        function getPinchDist(e) {
            return Math.sqrt(
                Math.pow(e.touches[0].clientX - e.touches[1].clientX, 2) +
                Math.pow(e.touches[0].clientY - e.touches[1].clientY, 2)
            );
        }

        function onWheel(e) {
            e.preventDefault();

            const rect = canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            const worldPosX = mouseX / state.scale - state.offset.x;
            const worldPosY = mouseY / state.scale - state.offset.y;

            const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
            const oldScale = state.scale;
            const newScale = Math.max(1.0, Math.min(10, oldScale * zoomFactor));

            if (oldScale === newScale) return;

            state.scale = newScale;
            state.offset.x = mouseX / newScale - worldPosX;
            state.offset.y = mouseY / newScale - worldPosY;

            draw(); // Only redraw canvas and arrows
        }

        function zoomIn() {
            zoom(1.2);
        }

        function zoomOut() {
            zoom(1 / 1.2);
        }

        function zoom(factor) {
            // Get display dimensions
            const displayWidth = state.displayWidth || 1200;
            const displayHeight = state.displayHeight || 800;

            // Image center in reference space (1200x800)
            const imageCenterX = 600;  // Half of 1200
            const imageCenterY = 400;  // Half of 800

            // Scale to display size
            const scaleX = displayWidth / 1200;
            const scaleY = displayHeight / 800;
            const displayCenterX = imageCenterX * scaleX;
            const displayCenterY = imageCenterY * scaleY;

            const oldScale = state.scale;
            const newScale = Math.max(1.0, Math.min(10, oldScale * factor));

            if (oldScale === newScale) return;

            // Get current screen position of image center
            const screenX = (displayCenterX + state.offset.x) * oldScale;
            const screenY = (displayCenterY + state.offset.y) * oldScale;

            state.scale = newScale;

            // Calculate new offset to keep image center at same screen position
            state.offset.x = screenX / newScale - displayCenterX;
            state.offset.y = screenY / newScale - displayCenterY;

            updateZoomDisplay();
            draw(); // Only redraw canvas and arrows
        }

        function resetZoom() {
            state.scale = 1;
            state.offset = { x: 0, y: 0 };
            updateZoomDisplay();
            draw();
        }

        function formatNumber(num) {
            return Math.round(num).toLocaleString();
        }
    });
})();
