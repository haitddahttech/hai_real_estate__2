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
            isZoomLocked: true, // Default to locked
            touchStartPos: null,
            touchMoved: false,
            touchStartedOnPolygonIndex: -1,
            touchStartedOnPolygonIndex: -1,
            polygonsVisible: true,
            forceAllGray: false,
            interactiveGrayMode: false,
            manuallyGrayIndices: [], // Array of indices set to gray manually (added to gray list)
            manuallyUngrayIndices: [], // Array of indices set to NOT gray manually (removed from gray list)
            isDrawing: false, // Flag for requestAnimationFrame
            isDrawingArrows: false, // Flag for arrow RAF
        };

        const MAX_POPUPS = 5;

        // Cached DOM elements for performance
        let cachedWrapper = null;
        function getWrapper() {
            if (!cachedWrapper) {
                cachedWrapper = document.querySelector('.canvas-wrapper') || document.body;
            }
            return cachedWrapper;
        }

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

            // Toggle Polygons button
            const togglePolygonsBtn = document.getElementById('togglePolygons');
            if (togglePolygonsBtn) togglePolygonsBtn.addEventListener('click', togglePolygons);

            // Toggle All Gray button
            const toggleAllGrayBtn = document.getElementById('toggleAllGray');
            if (toggleAllGrayBtn) toggleAllGrayBtn.addEventListener('click', toggleAllGray);

            // Toggle Interactive Gray Mode button
            const toggleInteractiveGrayBtn = document.getElementById('toggleInteractiveGray');
            if (toggleInteractiveGrayBtn) toggleInteractiveGrayBtn.addEventListener('click', toggleInteractiveGrayMode);

            // Zoom Lock button
            const toggleZoomLockBtn = document.getElementById('toggleZoomLock');
            if (toggleZoomLockBtn) {
                toggleZoomLockBtn.addEventListener('click', toggleZoomLock);
                updateZoomLockButtonUI();
            }

            // Download screenshot button
            const downloadBtn = document.getElementById('downloadScreenshot');
            if (downloadBtn) downloadBtn.addEventListener('click', downloadScreenshot);

            // Zoom slider
            if (zoomSlider) {
                zoomSlider.addEventListener('input', (e) => {
                    if (state.isZoomLocked) {
                        e.target.value = state.scale;
                        return;
                    }
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
            // Reduced to 2 for better performance while maintaining good quality
            const RESOLUTION_SCALE = 2;

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

            // Enable high-quality image smoothing
            ctx.imageSmoothingEnabled = true;
            ctx.imageSmoothingQuality = 'high';

            // Calculate scale factor from backend canvas to current display size
            state.canvasScaleX = displayWidth / 1200;
            state.canvasScaleY = displayHeight / 800;

            // Reset zoom scale and offset if first load
            if (state.imageLoaded && !state.cachedImage) {
                // Create downsampled version for better quality when zoomed out
                createDownsampledImage();

                state.scale = 1;
                state.offset = { x: 0, y: 0 };
                draw();
            } else {
                draw();
            }
        }

        function createDownsampledImage() {
            if (!state.image) return;

            // Create an offscreen canvas for the cached image (approx 50% size or fixed reasonable size)
            // Target width around 2000px is usually good balance
            const targetWidth = Math.min(state.image.width, 2048);
            const scale = targetWidth / state.image.width;

            if (scale >= 1) {
                state.cachedImage = state.image; // No need to cache if image is small
                return;
            }

            const offCanvas = document.createElement('canvas');
            offCanvas.width = state.image.width * scale;
            offCanvas.height = state.image.height * scale;

            const offCtx = offCanvas.getContext('2d');
            offCtx.imageSmoothingEnabled = true;
            offCtx.imageSmoothingQuality = 'high';

            // Step-down scaling (optional, but 1-step high quality is usually enough for 50%)
            offCtx.drawImage(state.image, 0, 0, offCanvas.width, offCanvas.height);

            state.cachedImage = offCanvas;
            state.cachedImageScale = scale; // Remember scale factor (e.g., 0.5)
        }

        function loadImage() {
            const img = new Image();
            img.onload = function () {
                state.image = img;
                state.imageLoaded = true;
                state.cachedImage = null; // Reset cache

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

            if (state.isDrawing) return; // Prevent stacking

            state.isDrawing = true;
            requestAnimationFrame(() => {
                actualDraw();
                state.isDrawing = false;
            });
        }

        function actualDraw() {

            // Clear
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Save and transform
            ctx.save();

            // Apply resolution scale first
            const resScale = state.resolutionScale || 1;
            ctx.scale(resScale, resScale);

            // Get display dimensions
            const rect = canvas.getBoundingClientRect();
            const displayWidth = parseFloat(canvas.style.width) || rect.width;
            const displayHeight = parseFloat(canvas.style.height) || rect.height;

            // Store in state
            state.displayWidth = displayWidth;
            state.displayHeight = displayHeight;

            // Apply user zoom and pan
            ctx.scale(state.scale, state.scale);
            ctx.translate(state.offset.x, state.offset.y);

            // Draw image
            if (state.imageLoaded && state.image) {
                // Smart drawing based on User Request:
                // Zoom <= 130%: Use downsampled image (smoother, faster)
                // Zoom > 130%: Use original image (sharpest details)

                if (state.cachedImage && state.cachedImage !== state.image && state.scale <= 1.3) {
                    // Use downsampled image
                    // We need to draw it to match the dimensions of the original image
                    ctx.drawImage(state.cachedImage, 0, 0, displayWidth, displayHeight);
                } else {
                    // Use original image (High res)
                    ctx.drawImage(state.image, 0, 0, displayWidth, displayHeight);
                }
            }


            // Draw polygons (need to scale coordinates from 1200x800 to canvas size)
            // Draw polygons (need to scale coordinates from 1200x800 to canvas size)
            // Draw polygons (need to scale coordinates from 1200x800 to canvas size)

            // First pass: Draw all UNSELECTED polygons (Only if visible)
            if (state.polygonsVisible) {
                state.polygons.forEach((polygon, index) => {
                    // Skip if selected (will be drawn later)
                    if (state.selectedPolygons.includes(index)) return;

                    let isEffectivelySold;
                    if (state.forceAllGray) {
                        isEffectivelySold = !state.manuallyUngrayIndices.includes(index);
                    } else {
                        isEffectivelySold = state.manuallyGrayIndices.includes(index);
                    }
                    drawPolygonScaled(polygon, false, isEffectivelySold);
                });
            }

            // Second pass: Draw SELECTED polygons on top (ALWAYS DRAW)
            state.selectedPolygons.forEach(index => {
                const polygon = state.polygons[index];
                if (!polygon) return;

                let isEffectivelySold;
                if (state.forceAllGray) {
                    isEffectivelySold = !state.manuallyUngrayIndices.includes(index);
                } else {
                    isEffectivelySold = state.manuallyGrayIndices.includes(index);
                }
                drawPolygonScaled(polygon, true, isEffectivelySold);
            });

            ctx.restore();

            // Draw arrows from polygons to popups
            drawArrows();
        }

        function invertColor(hex) {
            if (!hex) return '#e74c3c';
            if (hex.indexOf('#') === 0) {
                hex = hex.slice(1);
            }
            // convert 3-digit hex to 6-digits.
            if (hex.length === 3) {
                hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2];
            }
            if (hex.length !== 6) {
                return '#e74c3c'; // Fallback
            }
            var r = (255 - parseInt(hex.slice(0, 2), 16)).toString(16),
                g = (255 - parseInt(hex.slice(2, 4), 16)).toString(16),
                b = (255 - parseInt(hex.slice(4, 6), 16)).toString(16);
            // pad each with zeros and return
            return '#' + (r.length < 2 ? '0' + r : r) + (g.length < 2 ? '0' + g : g) + (b.length < 2 ? '0' + b : b);
        }

        function drawPolygonScaled(polygon, isSelected, isEffectivelySold = false) {
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
            // Use inverted color for selection to ensure contrast
            let selectionColor = isSelected ? invertColor(strokeColor) : strokeColor;

            ctx.beginPath();
            ctx.moveTo(points[0].x * scaleX, points[0].y * scaleY);
            for (let i = 1; i < points.length; i++) {
                ctx.lineTo(points[i].x * scaleX, points[i].y * scaleY);
            }
            ctx.closePath();


            // Fill logic: Gray if sold, Transparent otherwise
            if (polygon.product.is_sold || isEffectivelySold) {
                ctx.fillStyle = '#dddddd'; // Solid light gray
                ctx.fill();
            } else if (isSelected) {
                // HIGHLIGHT: Stronger fill but transparent
                ctx.fillStyle = 'rgba(231, 76, 60, 0.4)';
                ctx.fill();
            }

            // No Glow Effect - Solid Border

            // Stroke
            // Use solid selectionColor if selected
            ctx.strokeStyle = (polygon.product.is_sold || isEffectivelySold) ? '#bbbbbb' : (isSelected ? selectionColor : strokeColor);

            const baseStrokeWidth = polygon.product && polygon.product.is_decoration ? 0.6 : 2.0;

            // Make line significantly thicker when selected
            ctx.lineWidth = (isSelected ? baseStrokeWidth * 3.0 : baseStrokeWidth) / state.scale;

            ctx.setLineDash([]);
            ctx.stroke();
        }

        function drawArrows() {
            // Use RAF for throttling - only one arrow update per frame
            if (state.isDrawingArrows) return;
            state.isDrawingArrows = true;

            requestAnimationFrame(() => {
                actualDrawArrows();
                state.isDrawingArrows = false;
            });
        }

        function actualDrawArrows() {
            // Cache all expensive DOM operations
            const canvasRect = canvas.getBoundingClientRect();
            const wrapper = getWrapper();
            const wrapperRect = wrapper.getBoundingClientRect();

            const displayWidth = state.displayWidth || canvasRect.width;
            const displayHeight = state.displayHeight || canvasRect.height;
            const scaleX = displayWidth / 1200;
            const scaleY = displayHeight / 800;

            const popupCount = state.activePopups.length;
            for (let p = 0; p < popupCount; p++) {
                const popupData = state.activePopups[p];
                const popup = popupData.element;
                const popupRect = popup.getBoundingClientRect();
                const popupCenterX = popupRect.left + popupRect.width / 2;
                const popupCenterY = popupRect.top + popupRect.height / 2;

                const originCount = popupData.origins.length;
                for (let o = 0; o < originCount; o++) {
                    const origin = popupData.origins[o];
                    const polygon = state.polygons[origin.polygonIndex];
                    const arrow = origin.arrow;
                    const points = polygon.points;

                    // Find closest point on polygon edge (in screen coordinates)
                    let minDist = Infinity;
                    let closestX = 0, closestY = 0;

                    const pointCount = points.length;
                    for (let i = 0; i < pointCount; i++) {
                        const p1 = points[i];
                        const p2 = points[(i + 1) % pointCount];

                        const zoomedX1 = (p1.x * scaleX + state.offset.x) * state.scale;
                        const zoomedY1 = (p1.y * scaleY + state.offset.y) * state.scale;
                        const zoomedX2 = (p2.x * scaleX + state.offset.x) * state.scale;
                        const zoomedY2 = (p2.y * scaleY + state.offset.y) * state.scale;

                        const x1 = canvasRect.left + zoomedX1;
                        const y1 = canvasRect.top + zoomedY1;
                        const x2 = canvasRect.left + zoomedX2;
                        const y2 = canvasRect.top + zoomedY2;

                        const edgePoint = closestPointOnSegment(x1, y1, x2, y2, popupCenterX, popupCenterY);
                        const edgeDx = edgePoint.x - popupCenterX;
                        const edgeDy = edgePoint.y - popupCenterY;
                        const dist = edgeDx * edgeDx + edgeDy * edgeDy; // Skip sqrt for comparison

                        if (dist < minDist) {
                            minDist = dist;
                            closestX = edgePoint.x;
                            closestY = edgePoint.y;
                        }
                    }

                    const dx = popupCenterX - closestX;
                    const dy = popupCenterY - closestY;
                    const angle = Math.atan2(dy, dx);

                    const strokeOffset = 2;
                    const extendedStartX = closestX + Math.cos(angle) * strokeOffset;
                    const extendedStartY = closestY + Math.sin(angle) * strokeOffset;

                    const popupEdgePoint = getPopupEdgePoint(popupRect, angle);
                    const arrowDx = popupEdgePoint.x - extendedStartX;
                    const arrowDy = popupEdgePoint.y - extendedStartY;
                    const arrowAngle = Math.atan2(arrowDy, arrowDx);
                    const length = Math.sqrt(arrowDx * arrowDx + arrowDy * arrowDy);

                    // Batch style updates using cssText for better performance
                    arrow.style.cssText = `
                        left: ${extendedStartX - wrapperRect.left}px;
                        top: ${extendedStartY - wrapperRect.top}px;
                        width: ${length}px;
                        height: 4px;
                        transform: rotate(${arrowAngle}rad);
                        transform-origin: 0 50%;
                        background: #e74c3c;
                        position: absolute;
                        z-index: 999;
                        pointer-events: none;
                        display: block;
                    `;
                }
            }
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

            if (clickedIndex !== -1) {
                // Interactive Gray Mode Logic
                // Interactive Gray Mode Logic
                if (state.interactiveGrayMode) {
                    if (state.forceAllGray) {
                        // When Force All Gray is ON: Clicking toggles "Not Gray" (Un-gray)
                        const idxInUngray = state.manuallyUngrayIndices.indexOf(clickedIndex);
                        if (idxInUngray !== -1) {
                            // Already un-grayed -> remove from un-gray list (becomes gray again)
                            state.manuallyUngrayIndices.splice(idxInUngray, 1);
                        } else {
                            // Currently gray -> add to un-gray list (becomes colored)
                            state.manuallyUngrayIndices.push(clickedIndex);
                        }
                    } else {
                        // When Force All Gray is OFF: Clicking toggles "Gray"
                        const idxInManual = state.manuallyGrayIndices.indexOf(clickedIndex);
                        if (idxInManual !== -1) {
                            state.manuallyGrayIndices.splice(idxInManual, 1);
                        } else {
                            state.manuallyGrayIndices.push(clickedIndex);
                        }
                    }
                    draw();
                    return; // Stop normal popup logic
                }


                const polygon = state.polygons[clickedIndex];
                const productId = polygon.product.id;

                const selectedIdx = state.selectedPolygons.indexOf(clickedIndex);

                if (selectedIdx !== -1) {
                    // DESELECT
                    removePolygonSelection(clickedIndex);
                } else {
                    // SELECT
                    // Find if a popup for this product already exists
                    let popupData = state.activePopups.find(p => p.productId === productId);

                    if (popupData) {
                        // Popup exists, just add this polygon as an origin
                        state.selectedPolygons.push(clickedIndex);
                        addOriginToPopup(popupData, clickedIndex);
                    } else {
                        // Create new popup
                        if (state.activePopups.length >= MAX_POPUPS) {
                            // Prune oldest popup (including all its origins)
                            const oldestPopup = state.activePopups[0];
                            // Remove all its polygon indices from selectedPolygons
                            oldestPopup.origins.forEach(orig => {
                                const idx = state.selectedPolygons.indexOf(orig.polygonIndex);
                                if (idx !== -1) state.selectedPolygons.splice(idx, 1);
                            });
                            removePopup(0);
                        }

                        state.selectedPolygons.push(clickedIndex);
                        showPopup(polygon, clickedIndex);
                    }
                }

                draw();
            }
        }

        function addOriginToPopup(popupData, polygonIndex) {
            const arrow = document.createElement('div');
            arrow.className = 'popup-arrow';
            arrow.style.display = 'none';

            const wrapper = getWrapper();
            wrapper.appendChild(arrow);

            popupData.origins.push({
                polygonIndex: polygonIndex,
                arrow: arrow
            });
        }

        function removePolygonSelection(polygonIndex) {
            // Find which popup owns this polygon
            const popupIndex = state.activePopups.findIndex(p => p.origins.some(o => o.polygonIndex === polygonIndex));
            if (popupIndex !== -1) {
                const popupData = state.activePopups[popupIndex];
                const originIndex = popupData.origins.findIndex(o => o.polygonIndex === polygonIndex);

                if (originIndex !== -1) {
                    // Remove arrow element
                    popupData.origins[originIndex].arrow.remove();
                    popupData.origins.splice(originIndex, 1);
                }

                // If it was the last origin, remove the whole popup
                if (popupData.origins.length === 0) {
                    removePopup(popupIndex);
                }

                // Remove from selected list
                const idx = state.selectedPolygons.indexOf(polygonIndex);
                if (idx !== -1) state.selectedPolygons.splice(idx, 1);
            }
        }

        function showPopup(polygon, polygonIndex) {
            const product = polygon.product;

            const popup = document.createElement('div');
            popup.className = 'card shadow-lg property-popup';
            popup.style.position = 'absolute';
            popup.style.zIndex = '1000';
            popup.style.maxWidth = product.is_decoration ? '320px' : '300px';
            popup.style.minWidth = product.is_decoration ? '250px' : '260px';
            popup.style.cursor = 'move';
            popup.style.overflow = 'visible';
            popup.style.setProperty('border', `1.5px solid ${polygon.color || '#3498db'}`, 'important');


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
                ? `<span class="badge badge-outline-primary badge-outline" style="font-size: 0.65rem; padding: 0.15rem 0.4rem;">${product.direction}</span>`
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

            let popupContent = '';

            if (product.is_decoration) {
                // REDESIGNED popup for decoration (Utility/Amenity)
                let imageHtml = '';
                if (product.attachments && product.attachments.length > 0) {
                    if (product.attachments.length === 1) {
                        imageHtml = `
                            <div class="decoration-main-image mb-1 overflow-hidden shadow-sm" style="border-radius: 8px; border: 1px solid #eee;">
                                <img src="${product.attachments[0].url}" 
                                     alt="${product.attachments[0].name}" 
                                     style="width: 100%; height: auto; max-height: 200px; object-fit: cover; cursor: zoom-in;"
                                     class="decoration-img-large"
                                     onclick="window.open('${product.attachments[0].url}', '_blank')"
                                />
                            </div>
                        `;
                    } else {
                        imageHtml = `
                            <div class="decoration-gallery-label mb-1 text-muted" style="font-size: 0.6rem; text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px;">
                                <i class="fa fa-picture-o me-1"></i> Hình ảnh (${product.attachments.length})
                            </div>
                            <div class="decoration-images d-flex overflow-auto gap-2 pb-1" style="scrollbar-width: none; -ms-overflow-style: none; -webkit-overflow-scrolling: touch;">
                                ${product.attachments.map(att => `
                                    <div style="flex: 0 0 auto; width: 120px; height: 120px; border-radius: 6px; overflow: hidden; border: 1px solid #eee;">
                                        <img src="${att.url}" 
                                             alt="${att.name}" 
                                             style="width: 100%; height: 100%; object-fit: cover; cursor: zoom-in;"
                                             class="decoration-thumb"
                                             onclick="window.open('${att.url}', '_blank')"
                                        />
                                    </div>
                                `).join('')}
                            </div>
                            <style>
                                .decoration-images::-webkit-scrollbar { display: none; }
                            </style>
                        `;
                    }
                }

                popupContent = `
                    <div class="card-header border-0 pb-2" style="cursor: move; background: ${bgColor}; color: ${textColor}; padding: 0.85rem 1rem;">
                        <div class="d-flex justify-content-between align-items-start">
                            <div class="flex-grow-1">
                                <span class="badge mb-1 d-inline-block" style="background: rgba(255,255,255,0.25); backdrop-filter: blur(4px); color: ${textColor}; border: 1px solid rgba(255,255,255,0.3); font-size: 0.55rem; padding: 0.15rem 0.4rem; letter-spacing: 0.5px; font-weight: 700;">TIỆN ÍCH DỰ ÁN</span>
                                <h6 class="mb-0 fw-bold" style="font-size: 0.95rem;">${product.name}</h6>
                            </div>
                            <button type="button" class="close-popup-btn" style="cursor: pointer; background: rgba(255,255,255,0.2); border: none; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(4px); transition: all 0.2s; color: ${textColor};">
                                <i class="fa fa-times" style="font-size: 0.8rem;"></i>
                            </button>
                        </div>
                    </div>
                    <div class="card-body pt-2 pb-2" style="padding: 0.85rem 1rem;">
                        ${product.decoration_note ? `
                            <div class="decoration-note-container mb-2">
                                <div class="decoration-note-text text-dark" style="
                                    font-size: 0.725rem; 
                                    line-height: 1.4; 
                                    border-radius: 6px; 
                                    background-color: #f8f9fa; 
                                    border-left: 3px solid #0dcaf0;
                                    padding: 0.5rem;
                                    display: -webkit-box;
                                    -webkit-line-clamp: 2;
                                    -webkit-box-orient: vertical;
                                    overflow: hidden;
                                ">
                                    ${product.decoration_note}
                                </div>
                                <div class="text-end mt-1">
                                    <button type="button" class="btn btn-link p-0 text-info text-decoration-none fw-bold" 
                                            style="font-size: 0.65rem;"
                                            onclick="toggleDecorationNote(this)">
                                        Xem thêm <i class="fa fa-chevron-down ms-1"></i>
                                    </button>
                                </div>
                            </div>
                        ` : ''}
                        ${imageHtml || '<div class="text-center py-3 bg-light rounded-3 text-muted" style="font-size: 0.65rem;"><i class="fa fa-image d-block fs-4 mb-1 opacity-25"></i>Chưa có ảnh</div>'}
                    </div>
                `;
            } else {
                // Full Popup for Real Estate
                popupContent = `
                ${ribbonHTML}
                <div class="card-header border-0 pb-2" style="cursor: move; background: ${bgColor}; color: ${textColor};">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <div class="text-muted mb-1" style="font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; opacity: 0.8;">Mã căn</div>
                            <div class="d-flex align-items-center gap-2">
                                <h6 class="mb-0 fw-bold" style="font-size: 0.95rem;">${product.name}</h6>
                                ${propertyTypeBadge}
                            </div>
                            ${buyerInfo}
                        </div>
                        <div class="d-flex align-items-center gap-2">
                            <button type="button" class="close-popup-btn" style="cursor: pointer; background: #e9ecef; border: none; border-radius: 50%; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); transition: all 0.2s; color: #333;">
                                <i class="fa fa-times" style="font-size: 1rem;"></i>
                            </button>
                        </div>
                    </div>
                </div>
                <div class="card-body pt-2 pb-3">
                    <div class="px-0">
                        <div class="d-flex justify-content-between mb-1 pb-1 border-bottom border-light">
                            <span class="text-dark fw-medium" style="font-size: 0.8rem;">Loại hình</span>
                            <span class="fw-bold text-dark" style="font-size: 0.85rem;">${product.property_type || '---'}</span>
                        </div>
                        <div class="d-flex justify-content-between mb-1 pb-1 border-bottom border-light">
                            <span class="text-dark fw-medium" style="font-size: 0.8rem;">Hướng</span>
                            <span class="fw-bold text-dark" style="font-size: 0.85rem;">${product.direction || '---'}</span>
                        </div>
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
                        <a href="/my/property/${product.id}" class="btn btn-success w-100 py-2 fw-bold" style="border-radius: 6px; font-size: 0.8rem; letter-spacing: 0.3px; border: none; background: linear-gradient(135deg, #28a745 0%, #218838 100%); transition: all 0.3s ease;">
                            CHI TIẾT <i class="fa fa-arrow-right ms-1 small"></i>
                        </a>
                    </div>
                </div>
                `;
            }

            popup.innerHTML = popupContent;

            const arrow = document.createElement('div');
            arrow.className = 'popup-arrow';
            arrow.style.display = 'none';

            const wrapper = getWrapper();
            wrapper.appendChild(popup);
            wrapper.appendChild(arrow);

            positionPopup(popup, polygon, state.activePopups.length);

            // Close button rewritten
            popup.querySelector('.close-popup-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                const popupIdx = state.activePopups.findIndex(p => p.element === popup);
                if (popupIdx !== -1) {
                    const popupData = state.activePopups[popupIdx];
                    // Remove all associated polygon indices from selection
                    popupData.origins.forEach(orig => {
                        const selIdx = state.selectedPolygons.indexOf(orig.polygonIndex);
                        if (selIdx !== -1) state.selectedPolygons.splice(selIdx, 1);
                    });
                    removePopup(popupIdx);
                    draw();
                }
            });

            // Make popup draggable
            makeDraggable(popup);

            state.activePopups.push({
                productId: product.id,
                element: popup,
                origins: [{
                    polygonIndex: polygonIndex,
                    arrow: arrow
                }]
            });

            draw();
        }

        function makeDraggable(popup) {
            let isDragging = false;
            let startX, startY; // Mouse start position
            let initialPopupX, initialPopupY; // Popup start position relative to wrapper
            let cachedWrapperWidth, cachedWrapperHeight; // Cache wrapper dimensions

            const header = popup.querySelector('.card-header');
            const wrapper = getWrapper();

            const dragStart = (e) => {
                if (e.target.closest('.close-popup-btn')) return;

                isDragging = true;
                popup.classList.add('dragging-popup');

                // Get mouse/touch start position
                startX = e.type === 'touchstart' ? e.touches[0].clientX : e.clientX;
                startY = e.type === 'touchstart' ? e.touches[0].clientY : e.clientY;

                // Get current popup position relative to wrapper
                // For safety, use offsetLeft/Top which are relative to offsetParent (wrapper).
                initialPopupX = popup.offsetLeft;
                initialPopupY = popup.offsetTop;

                // Cache wrapper dimensions at drag start (don't query during drag)
                const wrapperRect = wrapper.getBoundingClientRect();
                cachedWrapperWidth = wrapperRect.width;
                cachedWrapperHeight = wrapperRect.height;

                if (e.type === 'touchstart') {
                    // e.preventDefault(); 
                }
            };

            const drag = (e) => {
                if (!isDragging) return;
                e.preventDefault();

                const clientX = e.type === 'touchmove' ? e.touches[0].clientX : e.clientX;
                const clientY = e.type === 'touchmove' ? e.touches[0].clientY : e.clientY;

                const dx = clientX - startX;
                const dy = clientY - startY;

                // Calculate new position
                let newX = initialPopupX + dx;
                let newY = initialPopupY + dy;

                // Use cached dimensions for faster constraints
                const popupWidth = popup.offsetWidth;
                const popupHeight = popup.offsetHeight;

                // Max allowed position (width - popup width)
                const maxX = cachedWrapperWidth - popupWidth;
                const maxY = cachedWrapperHeight - popupHeight;

                // Apply constraints: Prevent popup from going outside wrapper
                newX = Math.max(0, Math.min(newX, maxX));
                newY = Math.max(0, Math.min(newY, maxY));

                // Apply directly - left/top for final position
                popup.style.left = `${newX}px`;
                popup.style.top = `${newY}px`;

                // Update arrows (already throttled via RAF)
                drawArrows();
            };

            const dragEnd = () => {
                if (isDragging) {
                    isDragging = false;
                    popup.classList.remove('dragging-popup');
                    drawArrows(); // Ensure arrows are finalized
                }
            };

            header.addEventListener('mousedown', dragStart);
            window.addEventListener('mousemove', drag);
            window.addEventListener('mouseup', dragEnd);

            header.addEventListener('touchstart', (e) => {
                dragStart(e);
            }, { passive: false });

            window.addEventListener('touchmove', (e) => {
                if (isDragging) drag(e);
            }, { passive: false });

            window.addEventListener('touchend', dragEnd);
        }

        function positionPopup(popup, polygon, popupIndex) {
            const canvasRect = canvas.getBoundingClientRect();
            const wrapper = getWrapper();
            const wrapperRect = wrapper.getBoundingClientRect();

            // Dimensions and Config
            const popupWidth = 300;
            const popupHeight = 230; // Approx max height
            const edgeMargin = 20;
            const columnSpacing = 10;

            // Layout Calculations
            const canvasRelX = canvasRect.left - wrapperRect.left;
            const canvasRelY = canvasRect.top - wrapperRect.top;
            const canvasWidth = canvasRect.width;
            const canvasHeight = canvasRect.height;

            // Available height for popups
            const availableHeight = canvasHeight - (edgeMargin * 2);

            // How many popups fit in one column?
            const popupsPerColumn = Math.floor(availableHeight / popupHeight) || 1;

            // Calculate grid Position (Row, Col)
            // Index 0 -> Col 0, Row 0
            // Index 1 -> Col 0, Row 1
            // ...
            // Index N -> Col 1, Row 0 ...
            const colIndex = Math.floor(popupIndex / popupsPerColumn);
            const rowIndex = popupIndex % popupsPerColumn;

            // Position Logic: Start from Right edge and go Left
            let relativeX, relativeY;

            // If polygon is on the far right, maybe we want to put popups on the left?
            // For simplicity, let's default to stacking from the Right side, 
            // moving inwards (Leftwards) as columns overflow.

            const rightEdge = canvasRelX + canvasWidth - edgeMargin;
            const leftEdge = canvasRelX + edgeMargin;

            // X Position: RightEdge - Width - (ColIndex * (Width + Spacing))
            relativeX = rightEdge - popupWidth - (colIndex * (popupWidth + columnSpacing));

            // Check if we ran out of space on the left side
            if (relativeX < leftEdge) {
                // Determine layout mode based on map width
                // Fallback: Just pile them on the left edge or wrap wildly
                // OR: Start stacking from Left edge going right?
                relativeX = leftEdge + (colIndex * (popupWidth + columnSpacing));
            }

            // Y Position: TopEdge + (RowIndex * Height)
            relativeY = canvasRelY + edgeMargin + (rowIndex * popupHeight);

            // Clamp locally (just in case)
            const minX = canvasRelX + edgeMargin;
            const maxX = canvasRelX + canvasWidth - popupWidth - edgeMargin;
            const minY = canvasRelY + edgeMargin;
            const maxY = canvasRelY + canvasHeight - popupHeight - edgeMargin;

            relativeX = Math.max(minX, Math.min(relativeX, maxX));
            relativeY = Math.max(minY, Math.min(relativeY, maxY));

            popup.style.left = relativeX + 'px';
            popup.style.top = relativeY + 'px';
        }

        function removePopup(index) {
            const popupData = state.activePopups[index];
            if (popupData) {
                popupData.element.remove();
                // Remove all arrows associated with this popup
                popupData.origins.forEach(orig => orig.arrow.remove());
                state.activePopups.splice(index, 1);
            }
        }

        function findPolygonAt(pos) {
            console.log('Finding polygon at position:', pos);
            console.log('Total polygons to check:', state.polygons.length);

            for (let i = state.polygons.length - 1; i >= 0; i--) {
                // If polygons are hidden, only allow interaction with SELECTED ones
                if (!state.polygonsVisible && !state.selectedPolygons.includes(i)) {
                    continue;
                }

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
            const touch = (e.touches && e.touches[0]) || (e.changedTouches && e.changedTouches[0]);

            if (touch) {
                clientX = touch.clientX !== undefined ? touch.clientX : touch.x;
                clientY = touch.clientY !== undefined ? touch.clientY : touch.y;
            } else {
                clientX = e.clientX !== undefined ? e.clientX : e.x;
                clientY = e.clientY !== undefined ? e.clientY : e.y;
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
            if (state.isZoomLocked) return; // Allow native scroll/click if locked

            if (e.touches.length === 1) {
                const pos = getMousePos(e);
                state.touchStartedOnPolygonIndex = findPolygonAt(pos);

                state.isPanning = true;
                state.touchStartPos = { x: e.touches[0].clientX, y: e.touches[0].clientY };
                state.lastTouchPos = { x: e.touches[0].clientX, y: e.touches[0].clientY };
                state.isPinching = false;
                state.touchMoved = false;

                // Try to prevent default to stop browser scrolling ONLY if we are unlocked
                // However, some browsers require passive: false listener to prevent default
                // Checking Polygon hit might help deciding but if unlocked we want to PAN map anywhere
                // e.preventDefault(); 
            } else if (e.touches.length === 2) {
                e.preventDefault(); // Prevent scroll/zoom when pinching
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
            if (state.isZoomLocked) return; // Allow native scroll if locked

            if (state.isPanning && e.touches.length === 1) {
                const dx = (e.touches[0].clientX - state.lastTouchPos.x) / state.scale;
                const dy = (e.touches[0].clientY - state.lastTouchPos.y) / state.scale;

                // If moved significantly, it's definitely a pan, not a tap
                const totalDist = Math.sqrt(
                    Math.pow(e.touches[0].clientX - state.touchStartPos.x, 2) +
                    Math.pow(e.touches[0].clientY - state.touchStartPos.y, 2)
                );

                // Movement threshold:
                // If started on a polygon, increase threshold to 15px to prioritize TAP
                // If started on empty space, keep it at 5px for responsive PAN
                const threshold = state.touchStartedOnPolygonIndex !== -1 ? 15 : 5;

                if (totalDist > threshold) {
                    state.touchMoved = true;
                    if (e.cancelable) e.preventDefault(); // Stop document scroll
                }

                if (state.touchMoved) {
                    state.offset.x += dx;
                    state.offset.y += dy;
                    state.lastTouchPos = { x: e.touches[0].clientX, y: e.touches[0].clientY };
                    draw();
                }
            } else if (state.isPinching && e.touches.length === 2) {
                e.preventDefault();
                const newDist = getPinchDist(e);
                const zoomFactor = newDist / state.pinchStartDist;

                const rect = canvas.getBoundingClientRect();
                const midX = (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left;
                const midY = (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top;

                const worldPosX = midX / state.scale - state.offset.x;
                const worldPosY = midY / state.scale - state.offset.y;

                if (state.isZoomLocked) return;

                const newScale = Math.max(1.0, Math.min(10, state.pinchStartScale * zoomFactor));

                state.scale = newScale;
                state.offset.x = midX / newScale - worldPosX;
                state.offset.y = midY / newScale - worldPosY;

                updateZoomDisplay();
                draw();
            }
        }

        function onTouchEnd(e) {
            if (state.isZoomLocked) return; // Allow native processing if locked

            if (e.touches.length === 0) {
                // If it was a quick tap (not panning or pinching long)
                if (!state.isPinching && state.isPanning && !state.touchMoved) {
                    // Prevent the native 'click' event from being dispatched by the browser
                    // This prevents double-triggering (toggle effect) on iPad/iOS
                    if (e.cancelable) e.preventDefault();

                    // Trigger click logic manually for immediate response
                    // Construct synthetic mouse event for getMousePos
                    // We use lastTouchPos which stores the clientX/Y from touchStart/Move
                    const syntheticEvent = {
                        clientX: state.lastTouchPos.x,
                        clientY: state.lastTouchPos.y,
                        // Add other properties if getMousePos needs them
                        touches: [], // Empty for touchend
                        target: canvas
                    };

                    // Call click handler with synthetic event
                    // Since getMousePos handles both touch and mouse, we just need to adapt structure
                    // But onCanvasClick uses getMousePos(e) which looks for e.touches[0] or e.clientX
                    // Let's make sure we pass what getMousePos expects

                    // Simple hack: Call click logic directly or ensure event mimics MouseEvent
                    onCanvasClick(syntheticEvent);
                }
                state.isPanning = false;
                state.isPinching = false;
                state.lastTouchPos = null;
                state.touchStartPos = null;
                state.touchStartedOnPolygonIndex = -1;
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
            // If zoom is locked, allow default scroll behavior
            if (state.isZoomLocked) return;

            // Prevent page scroll only when zooming
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

            updateZoomDisplay();
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
            if (state.isZoomLocked) return;
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
            if (state.isZoomLocked) return;
            state.scale = 1;
            state.offset = { x: 0, y: 0 };
            updateZoomDisplay();
            draw();
        }

        function togglePolygons() {
            state.polygonsVisible = !state.polygonsVisible;
            updateTogglePolygonsUI();
            draw();
        }

        function updateTogglePolygonsUI() {
            const btn = document.getElementById('togglePolygons');
            if (!btn) return;

            if (state.polygonsVisible) {
                btn.innerHTML = '<i class="fa fa-eye-slash"></i> Ẩn lô đất';
                btn.title = 'Ẩn các lô đất trên bản đồ';
            } else {
                btn.innerHTML = '<i class="fa fa-eye"></i> Tổng';
                btn.title = 'Hiện các lô đất trên bản đồ';
            }
        }

        function toggleAllGray() {
            state.forceAllGray = !state.forceAllGray;

            // If turning off (Undo), also clear manual selection
            // When turning ON, we also clear ungray list
            // Basically, reset manual lists on toggle
            state.manuallyGrayIndices = [];
            state.manuallyUngrayIndices = [];

            // Update UI
            const btn = document.getElementById('toggleAllGray');
            const interactiveBtn = document.getElementById('toggleInteractiveGray');

            if (btn) {
                if (state.forceAllGray) {
                    btn.innerHTML = '<i class="fa fa-undo"></i> Hoàn tác';
                    btn.classList.add('active-tool-btn');
                    btn.style.background = '#e2e8f0';
                    // Show "Chọn sản phẩm" button when forceAllGray is ON
                    if (interactiveBtn) {
                        interactiveBtn.style.display = '';
                    }
                } else {
                    btn.innerHTML = '<i class="fa fa-paint-brush"></i> Ẩn sản phẩm';
                    btn.classList.remove('active-tool-btn');
                    btn.style.background = 'white';
                    // Hide "Chọn sản phẩm" button when forceAllGray is OFF
                    if (interactiveBtn) {
                        interactiveBtn.style.display = 'none';
                        // Also turn off interactive mode if it was active
                        if (state.interactiveGrayMode) {
                            state.interactiveGrayMode = false;
                            interactiveBtn.innerHTML = '<i class="fa fa-magic"></i> Chọn sản phẩm';
                            interactiveBtn.style.background = 'white';
                            interactiveBtn.style.borderColor = '#dee2e6';
                            canvas.style.cursor = 'pointer';
                        }
                    }
                }
            }
            draw();
        }

        function toggleInteractiveGrayMode() {
            state.interactiveGrayMode = !state.interactiveGrayMode;
            // Update UI
            const btn = document.getElementById('toggleInteractiveGray');
            if (btn) {
                if (state.interactiveGrayMode) {
                    btn.innerHTML = '<i class="fa fa-times"></i> Tắt chọn xám';
                    btn.style.background = '#e2e8f0';
                    btn.style.borderColor = '#cbd5e0';
                    canvas.style.cursor = 'cell';
                } else {
                    btn.innerHTML = '<i class="fa fa-magic"></i> Chọn sản phẩm';
                    btn.style.background = 'white';
                    btn.style.borderColor = '#dee2e6';
                    canvas.style.cursor = 'pointer';
                }
            }
        }

        function toggleZoomLock() {
            state.isZoomLocked = !state.isZoomLocked;
            updateZoomLockButtonUI();
        }

        function updateZoomLockButtonUI() {
            const btn = document.getElementById('toggleZoomLock');
            const zoomInBtn = document.getElementById('zoomIn');
            const zoomOutBtn = document.getElementById('zoomOut');
            const resetZoomBtn = document.getElementById('resetZoom');
            const zoomSlider = document.getElementById('zoomSlider');

            if (!btn) return;

            if (state.isZoomLocked) {
                btn.innerHTML = '<i class="fa fa-lock"></i> Mở Zoom';
                btn.style.background = '#2d3748';
                btn.style.color = 'white';
                btn.style.borderColor = '#2d3748';
            } else {
                btn.innerHTML = '<i class="fa fa-unlock"></i> Khóa Zoom';
                btn.style.background = 'white';
                btn.style.color = '#495057';
                btn.style.borderColor = '#dee2e6';
            }

            // Visually disable zoom controls when locked
            const controls = [zoomInBtn, zoomOutBtn, resetZoomBtn, zoomSlider];
            controls.forEach(ctrl => {
                if (ctrl) {
                    ctrl.style.opacity = state.isZoomLocked ? '0.5' : '1';
                    ctrl.style.pointerEvents = state.isZoomLocked ? 'none' : 'auto';
                }
            });
        }

        async function downloadScreenshot() {
            try {
                const btn = document.getElementById('downloadScreenshot');
                const originalHTML = btn.innerHTML;
                btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Đang chụp...';
                btn.disabled = true;

                // Get canvas wrapper
                const canvasWrapper = getWrapper();

                if (!canvasWrapper) {
                    alert('Không tìm thấy canvas!');
                    btn.innerHTML = originalHTML;
                    btn.disabled = false;
                    return;
                }

                // === FORCE HIGH-RES RENDERING FOR SCREENSHOT ===
                // Save current state
                const originalCachedImage = state.cachedImage;

                // Temporarily use original image (not downsampled) for sharper output
                state.cachedImage = state.image;

                // Force synchronous redraw with original image
                actualDraw();

                // Add optimization class
                canvasWrapper.classList.add('taking-screenshot');

                // Capture canvas wrapper with higher scale for better quality
                const screenshot = await html2canvas(canvasWrapper, {
                    backgroundColor: '#f8f9fa',
                    scale: 4, // Higher scale for sharper output
                    logging: false,
                    useCORS: true,
                    allowTaint: true,
                    imageTimeout: 0, // Disable timeout for large images
                });

                // Remove optimization class
                canvasWrapper.classList.remove('taking-screenshot');

                // === RESTORE ORIGINAL STATE ===
                state.cachedImage = originalCachedImage;

                // Redraw with original cached image
                actualDraw();

                // Download
                screenshot.toBlob((blob) => {
                    const url = URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
                    link.download = `site-plan-${timestamp}.png`;
                    link.href = url;
                    link.click();
                    URL.revokeObjectURL(url);

                    btn.innerHTML = originalHTML;
                    btn.disabled = false;
                }, 'image/png', 1.0); // Maximum quality

            } catch (error) {
                console.error('Screenshot error:', error);
                alert('Lỗi: ' + error.message);

                // Restore state on error
                setCanvasSize();
                draw();

                const btn = document.getElementById('downloadScreenshot');
                btn.innerHTML = '<i class="fa fa-camera"></i> Chụp màn hình';
                btn.disabled = false;
            }
        }

        function formatNumber(num) {
            return Math.round(num).toLocaleString();
        }
        // Helper to toggle description expansion
        window.toggleDecorationNote = function (btn) {
            const container = btn.closest('.decoration-note-container');
            const note = container.querySelector('.decoration-note-text');
            const isExpanded = note.style.webkitLineClamp === 'unset';

            if (isExpanded) {
                note.style.webkitLineClamp = '2';
                btn.innerHTML = 'Xem thêm <i class="fa fa-chevron-down ms-1"></i>';
            } else {
                note.style.webkitLineClamp = 'unset';
                btn.innerHTML = 'Thu gọn <i class="fa fa-chevron-up ms-1"></i>';
            }

            // Redraw arrows because popup height changed
            drawArrows();
        };

    });
})();
