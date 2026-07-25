/**
 * Hồng Hạc City — Floating Action Button 360° tour
 * - Iframe chỉ nạp khi mở popup (đỡ tải web ngoài trên mọi trang).
 * - Xoá src khi đóng để dừng tour (video/âm thanh) và giải phóng.
 * - Đóng bằng: nút X, click nền, phím Esc.
 */
(function () {
    "use strict";

    function init() {
        var fab = document.getElementById("hhFab360");
        var modal = document.getElementById("hhFab360Modal");
        if (!fab || !modal) {
            return;
        }

        var iframe = modal.querySelector(".hh-fab-360-modal__iframe");
        var url = iframe ? iframe.getAttribute("data-src") : null;

        function openModal() {
            if (iframe && url && iframe.getAttribute("src") !== url) {
                iframe.setAttribute("src", url);
            }
            modal.classList.add("is-open");
            modal.setAttribute("aria-hidden", "false");
            document.body.classList.add("hh-modal-open");
        }

        function closeModal() {
            modal.classList.remove("is-open");
            modal.setAttribute("aria-hidden", "true");
            document.body.classList.remove("hh-modal-open");
            // Dừng tour: gỡ src.
            if (iframe) {
                iframe.setAttribute("src", "");
            }
        }

        fab.addEventListener("click", openModal);

        // Mọi phần tử có data-hh-close (nút X, backdrop) đều đóng popup.
        modal.querySelectorAll("[data-hh-close]").forEach(function (el) {
            el.addEventListener("click", closeModal);
        });

        document.addEventListener("keydown", function (ev) {
            if (ev.key === "Escape" && modal.classList.contains("is-open")) {
                closeModal();
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
