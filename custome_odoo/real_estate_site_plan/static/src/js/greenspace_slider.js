/**
 * Hồng Hạc City — Slideshow "Mảng Xanh" (tiện ích)
 * Slider ngang: prev/next, autoplay, thanh tiến độ, vuốt (touch), tạm dừng khi hover.
 */
(function () {
    "use strict";

    function pad(n) { return (n < 10 ? "0" : "") + n; }

    function initSlider(root) {
        var track = root.querySelector(".hh-green__track");
        var slides = root.querySelectorAll(".hh-green__slide");
        var total = slides.length;
        if (!track || total === 0) { return; }

        var cur = root.querySelector(".hh-green__cur");
        var totalEl = root.querySelector(".hh-green__total");
        var fill = root.querySelector(".hh-green__fill");
        var prev = root.querySelector(".hh-green__nav--prev");
        var next = root.querySelector(".hh-green__nav--next");

        var index = 0;
        var timer = null;
        var DELAY = 5000;

        if (totalEl) { totalEl.textContent = pad(total); }

        function render() {
            track.style.transform = "translateX(" + (-index * 100) + "%)";
            if (cur) { cur.textContent = pad(index + 1); }
            if (fill) { fill.style.width = ((index + 1) / total * 100) + "%"; }
        }

        function go(i) {
            index = (i + total) % total;
            render();
        }

        function start() {
            stop();
            timer = window.setInterval(function () { go(index + 1); }, DELAY);
        }
        function stop() {
            if (timer) { window.clearInterval(timer); timer = null; }
        }

        if (prev) { prev.addEventListener("click", function () { go(index - 1); start(); }); }
        if (next) { next.addEventListener("click", function () { go(index + 1); start(); }); }

        // Tạm dừng khi hover
        root.addEventListener("mouseenter", stop);
        root.addEventListener("mouseleave", start);

        // Vuốt (touch/pointer)
        var x0 = null;
        var vp = root.querySelector(".hh-green__viewport") || track;
        vp.addEventListener("touchstart", function (e) {
            x0 = e.touches[0].clientX; stop();
        }, { passive: true });
        vp.addEventListener("touchend", function (e) {
            if (x0 === null) { return; }
            var dx = e.changedTouches[0].clientX - x0;
            if (Math.abs(dx) > 40) { go(index + (dx < 0 ? 1 : -1)); }
            x0 = null; start();
        }, { passive: true });

        render();
        start();
    }

    function init() {
        var sliders = document.querySelectorAll(".hh-green__slider");
        sliders.forEach(initSlider);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
