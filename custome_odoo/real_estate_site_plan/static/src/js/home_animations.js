/**
 * Hồng Hạc City — Homepage interactions (vanilla, no OWL)
 * - Scroll-reveal (IntersectionObserver)
 * - Ken Burns cho section ảnh nổi bật (toggle .is-visible)
 * - Bật full-page snap qua <html class="hh-home-active">
 * - Parallax mây/ảnh cho section phối cảnh shophouse (--hh-sky-p)
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

        // ---- Section phối cảnh shophouse: mây + ảnh dịch theo cuộn ----
        // Ghi tiến độ cuộn (0 → 1) vào biến --hh-sky-p, phần dịch chuyển do CSS lo.
        var skyline = document.querySelector(".hh-skyline");
        if (skyline && !reduceMotion) {
            var skyScene = skyline.querySelector(".hh-skyline__scene");
            var skyTicking = false;
            var updateSky = function () {
                skyTicking = false;
                var rect = skyline.getBoundingClientRect();
                var vh = window.innerHeight || document.documentElement.clientHeight;
                var span = vh + rect.height;
                var progress = span > 0 ? (vh - rect.top) / span : 0;
                progress = Math.min(1, Math.max(0, progress));
                skyline.style.setProperty("--hh-sky-p", progress.toFixed(4));

                // Tiến độ "bay lên" của dãy nhà: 0 khi khối ảnh còn nằm dưới đáy
                // màn hình → 1 khi đã vào hẳn. Bám theo cuộn cả hai chiều nên
                // cuộn ngược lên thì ảnh hạ xuống và mờ dần trở lại.
                // Quãng bay = trọn đường đi của khối ảnh: từ lúc đỉnh của nó chạm
                // mép dưới màn hình cho tới khi section nằm gọn khung nhìn. Tự co
                // giãn theo mọi cỡ màn hình và luôn đạt 1 đúng lúc ảnh đứng yên
                // (nhân 0.92 để ảnh đáp xong ngay trước khi section dừng hẳn).
                // Dùng offsetTop (vị trí bố cục) chứ không phải getBoundingClientRect
                // của khối ảnh — rect đã bị chính transform này dời đi, đo lại sẽ
                // thành vòng lặp phản hồi.
                var skyOffset = skyScene ? skyScene.offsetTop : 0; // dải trời phía trên
                var sceneTop = rect.top + skyOffset;
                var travel = Math.max(1, (vh - skyOffset) * 0.92);
                var t = (vh - sceneTop) / travel;
                t = Math.min(1, Math.max(0, t));
                var eased = t * t * (3 - 2 * t); // smoothstep — vào/ra êm, giữa đi đều
                skyline.style.setProperty("--hh-sky-in", eased.toFixed(4));
            };
            var onSkyScroll = function () {
                if (!skyTicking) {
                    skyTicking = true;
                    window.requestAnimationFrame(updateSky);
                }
            };
            updateSky();
            window.addEventListener("scroll", onSkyScroll, { passive: true });
            window.addEventListener("resize", onSkyScroll, { passive: true });
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
