/**
 * Hồng Hạc City — Homepage interactions (vanilla, no OWL)
 * - Scroll-reveal (IntersectionObserver)
 * - Ken Burns cho section ảnh nổi bật (toggle .is-visible)
 * - Bật full-page snap qua <html class="hh-home-active">
 * - Đảm bảo video hero autoplay; navbar đổ bóng khi cuộn
 */
(function () {
    "use strict";

    function init() {
        var home = document.querySelector(".hh-home");
        if (!home) {
            return; // Không phải trang chủ Hồng Hạc City
        }

        var reduceMotion = window.matchMedia
            && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        // Bật snap cấp document
        document.documentElement.classList.add("hh-home-active");

        // ---- Scroll reveal + Ken Burns ----
        var revealTargets = document.querySelectorAll(".reveal, .hh-feature");

        if (reduceMotion || !("IntersectionObserver" in window)) {
            revealTargets.forEach(function (el) {
                el.classList.add("is-visible");
            });
        } else {
            var observer = new IntersectionObserver(function (entries, obs) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("is-visible");
                        // Reveal chạy 1 lần; feature giữ observe để Ken Burns lặp lại
                        if (entry.target.classList.contains("reveal")) {
                            obs.unobserve(entry.target);
                        }
                    } else if (entry.target.classList.contains("hh-feature")) {
                        entry.target.classList.remove("is-visible");
                    }
                });
            }, { threshold: 0.2, rootMargin: "0px 0px -8% 0px" });

            revealTargets.forEach(function (el) {
                observer.observe(el);
            });
        }

        // ---- Đảm bảo video hero autoplay (một số trình duyệt chặn) ----
        var video = document.querySelector(".hh-hero__video");
        if (video) {
            video.muted = true;
            video.setAttribute("muted", "");
            video.setAttribute("playsinline", "");
            var playPromise = video.play();
            if (playPromise && typeof playPromise.catch === "function") {
                playPromise.catch(function () {
                    // Autoplay bị chặn → poster sẽ hiển thị, không cần làm gì thêm.
                });
            }
        }

        // ---- Navbar đổ bóng khi cuộn qua hero ----
        var header = document.querySelector("header#top, #wrapwrap header, header .navbar");
        if (header) {
            var onScroll = function () {
                if (window.scrollY > 60) {
                    header.classList.add("hh-nav-scrolled");
                } else {
                    header.classList.remove("hh-nav-scrolled");
                }
            };
            onScroll();
            window.addEventListener("scroll", onScroll, { passive: true });
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
