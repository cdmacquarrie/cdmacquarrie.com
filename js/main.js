/* cdmacquarrie.com — progressive enhancement only.
   Everything below is optional: the page reads fine with JS disabled. */
(function () {
  "use strict";

  var root = document.documentElement;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- theme ---------- */
  var themeBtn = document.getElementById("themeToggle");
  function applyTheme(mode) {
    root.setAttribute("data-theme", mode);
    if (themeBtn) {
      themeBtn.setAttribute("aria-label",
        mode === "dark" ? "Switch to light theme" : "Switch to dark theme");
    }
  }
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(next);
      try { localStorage.setItem("theme", next); } catch (e) {}
    });
  }

  /* ---------- sticky header ---------- */
  var header = document.getElementById("siteHeader");
  function onScroll() {
    if (header) header.classList.toggle("is-stuck", window.scrollY > 12);
  }
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  /* ---------- mobile nav ---------- */
  var navToggle = document.getElementById("navToggle");
  var navMenu = document.getElementById("navMenu");
  function closeNav() {
    if (!navToggle || !navMenu) return;
    navToggle.setAttribute("aria-expanded", "false");
    navMenu.classList.remove("is-open");
  }
  if (navToggle && navMenu) {
    navToggle.addEventListener("click", function () {
      var open = navToggle.getAttribute("aria-expanded") === "true";
      navToggle.setAttribute("aria-expanded", String(!open));
      navMenu.classList.toggle("is-open", !open);
    });
    navMenu.addEventListener("click", function (e) {
      if (e.target.closest("a")) closeNav();
    });
  }
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeNav(); });

  /* ---------- reveal on scroll ---------- */
  var revealables = document.querySelectorAll(".reveal");
  if (reduceMotion || !("IntersectionObserver" in window)) {
    revealables.forEach(function (el) { el.classList.add("is-in"); });
  } else {
    var revealObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-in");
        revealObserver.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    revealables.forEach(function (el, i) {
      el.style.transitionDelay = Math.min(i % 4, 3) * 70 + "ms";
      revealObserver.observe(el);
    });
  }

  /* ---------- scrollspy ---------- */
  var navLinks = Array.prototype.slice.call(document.querySelectorAll('.nav-menu a[href^="#"]'));
  var sections = navLinks
    .map(function (a) { return document.querySelector(a.getAttribute("href")); })
    .filter(Boolean);

  if (sections.length && "IntersectionObserver" in window) {
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        navLinks.forEach(function (a) {
          a.classList.toggle("is-current", a.getAttribute("href") === "#" + entry.target.id);
        });
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    sections.forEach(function (s) { spy.observe(s); });
  }

  /* ---------- publication filters ---------- */
  var chips = document.querySelectorAll(".chip[data-filter]");
  var pubs = document.querySelectorAll(".pub");
  var groups = document.querySelectorAll(".pub-year");
  var emptyMsg = document.getElementById("pubEmpty");
  var status = document.getElementById("filterStatus");

  function filterPubs(kind) {
    // A chip may cover several kinds, e.g. "journal,arcadia".
    var wanted = kind.split(",");
    var shown = 0;
    pubs.forEach(function (p) {
      var match = kind === "all" || wanted.indexOf(p.dataset.kind) !== -1;
      p.hidden = !match;
      if (match) shown++;
    });
    groups.forEach(function (g) {
      g.hidden = !g.querySelector(".pub:not([hidden])");
    });
    if (emptyMsg) emptyMsg.hidden = shown > 0;
    if (status) status.textContent = shown + (shown === 1 ? " publication" : " publications") + " shown.";
  }

  chips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      chips.forEach(function (c) {
        var active = c === chip;
        c.classList.toggle("is-active", active);
        c.setAttribute("aria-pressed", String(active));
      });
      filterPubs(chip.dataset.filter);
    });
  });

  /* ---------- footer year ---------- */
  var yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());

  /* ---------- carousel + lightbox ---------- */
  var carousel = document.getElementById("carousel");
  var track = document.getElementById("carTrack");
  var carCaption = document.getElementById("carCaption");
  var carDots = document.getElementById("carDots");
  var items = (window.GALLERY || []);
  var lb = document.getElementById("lightbox");
  var lbImg = document.getElementById("lbImg");
  var lbCap = document.getElementById("lbCap");
  var current = 0;
  var lastFocused = null;
  var slides = [];
  var timer = 0;
  var DWELL = 5000;

  if (carousel && items.length) {
    carousel.hidden = false;
    items.forEach(function (item, i) {
      var img = document.createElement("img");
      img.src = item.src;
      img.alt = item.caption;
      img.loading = i === 0 ? "eager" : "lazy";
      img.decoding = "async";
      if (i === 0) img.classList.add("is-on");
      track.appendChild(img);
      slides.push(img);

      var dot = document.createElement("button");
      dot.type = "button";
      dot.setAttribute("aria-label", "Image " + (i + 1) + " of " + items.length);
      if (i === 0) dot.classList.add("is-on");
      dot.addEventListener("click", function () { show(i); restart(); });
      carDots.appendChild(dot);
    });
    if (items.length < 2) {
      carDots.hidden = true;
      document.getElementById("carPrev").hidden = true;
      document.getElementById("carNext").hidden = true;
    }
    show(0);
    start();
  } else if (carousel) {
    carousel.closest("section").hidden = true;
  }

  function show(i) {
    if (!slides.length) return;
    current = (i + slides.length) % slides.length;
    slides.forEach(function (s, n) { s.classList.toggle("is-on", n === current); });
    Array.prototype.forEach.call(carDots.children, function (d, n) {
      d.classList.toggle("is-on", n === current);
    });
    carCaption.textContent = items[current].caption;
  }
  function start() {
    if (reduceMotion || slides.length < 2) return;
    timer = setInterval(function () { show(current + 1); }, DWELL);
  }
  function stop() { clearInterval(timer); timer = 0; }
  function restart() { stop(); start(); }

  if (carousel && slides.length) {
    document.getElementById("carPrev").addEventListener("click", function () { show(current - 1); restart(); });
    document.getElementById("carNext").addEventListener("click", function () { show(current + 1); restart(); });
    carousel.addEventListener("pointerenter", stop);
    carousel.addEventListener("pointerleave", start);
    carousel.addEventListener("focusin", stop);
    carousel.addEventListener("focusout", start);
    track.addEventListener("click", function () { openLightbox(current); });
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) stop(); else start();
    });
  }

  function showImage(i) {
    current = (i + items.length) % items.length;
    lbImg.src = items[current].src;
    lbImg.alt = items[current].caption;
    lbCap.textContent = items[current].caption;
  }
  function openLightbox(i) {
    if (!lb) return;
    stop();
    lastFocused = document.activeElement;
    showImage(i);
    lb.hidden = false;
    document.body.style.overflow = "hidden";
    document.getElementById("lbClose").focus();
  }
  function closeLightbox() {
    if (!lb) return;
    lb.hidden = true;
    document.body.style.overflow = "";
    if (lastFocused) lastFocused.focus();
    show(current);
    start();
  }

  if (lb) {
    document.getElementById("lbClose").addEventListener("click", closeLightbox);
    document.getElementById("lbPrev").addEventListener("click", function () { showImage(current - 1); });
    document.getElementById("lbNext").addEventListener("click", function () { showImage(current + 1); });
    lb.addEventListener("click", function (e) { if (e.target === lb) closeLightbox(); });
    document.addEventListener("keydown", function (e) {
      if (lb.hidden) return;
      if (e.key === "Escape") closeLightbox();
      if (e.key === "ArrowLeft") showImage(current - 1);
      if (e.key === "ArrowRight") showImage(current + 1);
    });
  }

  /* ---------- hero field ----------
     A sparse drift of fluorescent points, nudged by the pointer.
     Purely decorative; skipped entirely under reduced-motion. */
  var canvas = document.getElementById("heroCanvas");
  if (canvas && canvas.getContext) {
    var ctx = canvas.getContext("2d");
    var pts = [];
    var w = 0, h = 0, dpr = 1;
    var pointer = { x: -9999, y: -9999 };
    var running = true;

    function sizeCanvas() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      var r = canvas.getBoundingClientRect();
      w = r.width; h = r.height;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function seed() {
      var count = Math.round(Math.min(58, Math.max(18, (w * h) / 24000)));
      pts = [];
      for (var i = 0; i < count; i++) {
        pts.push({
          x: Math.random() * w,
          y: Math.random() * h,
          r: 1 + Math.random() * 2.6,
          vx: (Math.random() - 0.5) * 0.16,
          vy: (Math.random() - 0.5) * 0.16,
          hue: Math.random() < 0.7 ? "green" : "magenta",
          a: 0.16 + Math.random() * 0.4
        });
      }
    }

    function colorFor(p, alpha) {
      return p.hue === "green"
        ? "rgba(66, 226, 164, " + alpha + ")"
        : "rgba(242, 107, 208, " + alpha + ")";
    }

    function draw() {
      ctx.clearRect(0, 0, w, h);
      for (var i = 0; i < pts.length; i++) {
        var p = pts[i];
        var g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 7);
        g.addColorStop(0, colorFor(p, p.a));
        g.addColorStop(1, colorFor(p, 0));
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r * 7, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    function tick() {
      if (!running) return;
      for (var i = 0; i < pts.length; i++) {
        var p = pts[i];
        var dx = p.x - pointer.x, dy = p.y - pointer.y;
        var d2 = dx * dx + dy * dy;
        if (d2 < 20000 && d2 > 0.01) {
          var f = (1 - d2 / 20000) * 0.55;
          var d = Math.sqrt(d2);
          p.vx += (dx / d) * f * 0.09;
          p.vy += (dy / d) * f * 0.09;
        }
        p.vx *= 0.985; p.vy *= 0.985;
        p.x += p.vx; p.y += p.vy;
        if (p.x < -30) p.x = w + 30; else if (p.x > w + 30) p.x = -30;
        if (p.y < -30) p.y = h + 30; else if (p.y > h + 30) p.y = -30;
      }
      draw();
      requestAnimationFrame(tick);
    }

    sizeCanvas(); seed(); draw();

    window.addEventListener("resize", function () { sizeCanvas(); seed(); draw(); });

    if (!reduceMotion) {
      canvas.parentElement.addEventListener("pointermove", function (e) {
        var r = canvas.getBoundingClientRect();
        pointer.x = e.clientX - r.left;
        pointer.y = e.clientY - r.top;
      });
      canvas.parentElement.addEventListener("pointerleave", function () {
        pointer.x = -9999; pointer.y = -9999;
      });
      document.addEventListener("visibilitychange", function () {
        running = !document.hidden;
        if (running) tick();
      });
      if ("IntersectionObserver" in window) {
        new IntersectionObserver(function (entries) {
          running = entries[0].isIntersecting && !document.hidden;
          if (running) tick();
        }, { threshold: 0 }).observe(canvas);
      }
      tick();
    }
  }
})();
