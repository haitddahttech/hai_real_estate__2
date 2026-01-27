async function downloadScreenshot() {
    try {
        const btn = document.getElementById('downloadScreenshot');
        const originalHTML = btn.innerHTML;
        btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Đang chụp...';
        btn.disabled = true;

        // Simply capture the entire map container
        const mapContainer = document.querySelector('.map-container');

        if (!mapContainer) {
            alert('Không tìm thấy bản đồ!');
            btn.innerHTML = originalHTML;
            btn.disabled = false;
            return;
        }

        // Capture the map container directly
        const screenshot = await html2canvas(mapContainer, {
            backgroundColor: '#f8f9fa',
            scale: 2,
            logging: false,
            useCORS: true,
            allowTaint: true,
            scrollY: 0,
            scrollX: 0,
        });

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
        }, 'image/png');

    } catch (error) {
        console.error('Screenshot error:', error);
        alert('Lỗi: ' + error.message);

        const btn = document.getElementById('downloadScreenshot');
        btn.innerHTML = '<i class="fa fa-camera"></i> Chụp màn hình';
        btn.disabled = false;
    }
}
