/* Playground: runs the Python simulations in py/ via Pyodide.
   Nothing here loads until the visitor asks for it. */
(function () {
  "use strict";

  var PYODIDE_VERSION = "0.26.4";
  var PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v" + PYODIDE_VERSION + "/full/";

  var SIMS = {
    patch: { file: "py/endocytosis.py", label: "Endocytic patch" },
    hunt:  { file: "py/hunt.py",        label: "Hunting cell" }
  };

  var canvas = document.getElementById("pgCanvas");
  if (!canvas) return;

  var ctx = canvas.getContext("2d");
  var tabs = document.querySelectorAll(".pg-tab");
  var overlay = document.getElementById("pgOverlay");
  var startBtn = document.getElementById("pgStart");
  var resetBtn = document.getElementById("pgReset");
  var pauseBtn = document.getElementById("pgPause");
  var statusEl = document.getElementById("pgStatus");
  var nameEl = document.getElementById("pgName");
  var descEl = document.getElementById("pgDesc");
  var blurbEl = document.getElementById("pgBlurb");
  var citeEl = document.getElementById("pgCite");
  var controlsEl = document.getElementById("pgControls");
  var readoutEl = document.getElementById("pgReadout");
  var codeEl = document.getElementById("pgCode");

  var pyodide = null;
  var loading = false;
  var currentKey = "patch";
  var running = false;
  var lastTime = 0;
  var rafId = 0;
  var palette = {};

  /* ---------- colours follow the site theme ---------- */
  function refreshPalette() {
    var cs = getComputedStyle(document.documentElement);
    palette = {
      accent: cs.getPropertyValue("--accent").trim() || "#42e2a4",
      accent2: cs.getPropertyValue("--accent-2").trim() || "#f26bd0",
      dim: cs.getPropertyValue("--muted").trim() || "#8d99aa",
      warm: "#ffd479",
      cool: "#5b9dff"
    };
  }
  refreshPalette();
  new MutationObserver(refreshPalette).observe(document.documentElement, {
    attributes: true, attributeFilter: ["data-theme"]
  });

  function colorOf(key, alpha) {
    var c = palette[key] || palette.accent;
    if (alpha === undefined || alpha === null) alpha = 1;
    // Accept #rgb / #rrggbb and fall back to the raw value otherwise.
    var m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(c);
    if (!m) return c;
    var hex = m[1];
    if (hex.length === 3) hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2];
    var r = parseInt(hex.slice(0, 2), 16),
        g = parseInt(hex.slice(2, 4), 16),
        b = parseInt(hex.slice(4, 6), 16);
    return "rgba(" + r + "," + g + "," + b + "," + alpha + ")";
  }

  /* ---------- drawing ---------- */
  function drawScene(scene) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    var shapes = scene.shapes || [];

    for (var i = 0; i < shapes.length; i++) {
      var s = shapes[i];
      var a = s.a === undefined ? 1 : s.a;

      if (s.t === "line") {
        ctx.strokeStyle = colorOf(s.c, a);
        ctx.lineWidth = s.w || 1;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(s.x1, s.y1);
        ctx.lineTo(s.x2, s.y2);
        ctx.stroke();

      } else if (s.t === "curve") {
        ctx.strokeStyle = colorOf(s.c, a);
        ctx.lineWidth = s.w || 1;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(s.x1, s.y1);
        ctx.quadraticCurveTo(s.cx, s.cy, s.x2, s.y2);
        ctx.stroke();

      } else if (s.t === "dot") {
        ctx.fillStyle = colorOf(s.c, a);
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fill();

      } else if (s.t === "glow") {
        var g = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, s.r);
        g.addColorStop(0, colorOf(s.c, a));
        g.addColorStop(1, colorOf(s.c, 0));
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fill();

      } else if (s.t === "band") {
        ctx.fillStyle = colorOf(s.c, a);
        ctx.fillRect(0, s.y, canvas.width, s.h);

      } else if (s.t === "text") {
        ctx.fillStyle = colorOf(s.c, a);
        ctx.font = "12px ui-sans-serif, system-ui, sans-serif";
        ctx.fillText(s.s, s.x, s.y);
      }
    }
  }

  function renderReadout(rows) {
    if (!rows) return;
    var html = "";
    for (var i = 0; i < rows.length; i++) {
      html += '<div class="ro-row"><span class="ro-label">' + rows[i].label +
              '</span><span class="ro-value">' + rows[i].value + "</span></div>";
    }
    readoutEl.innerHTML = html;
  }

  /* ---------- controls ---------- */
  function buildControls(list) {
    controlsEl.innerHTML = "";
    list.forEach(function (c) {
      var wrap = document.createElement("div");
      wrap.className = "ctrl";
      var id = "ctrl-" + c.id;

      if (c.type === "select") {
        var slabel = document.createElement("label");
        slabel.setAttribute("for", id);
        slabel.innerHTML = "<span>" + c.label + "</span>";

        var sel = document.createElement("select");
        sel.id = id;
        sel.className = "ctrl-select";
        c.options.forEach(function (o) {
          var opt = document.createElement("option");
          opt.value = o.value;
          opt.innerHTML = o.label;
          if (o.value === c.value) opt.selected = true;
          sel.appendChild(opt);
        });

        var note = document.createElement("p");
        note.className = "ctrl-hint";
        note.innerHTML = describe(c, sel.value);

        sel.addEventListener("change", function () {
          note.innerHTML = describe(c, sel.value);
          if (pyodide) pyodide.globals.get("_set_choice")(c.id, sel.value);
        });

        wrap.appendChild(slabel);
        wrap.appendChild(sel);
        wrap.appendChild(note);
        controlsEl.appendChild(wrap);
        return;
      }

      var label = document.createElement("label");
      label.setAttribute("for", id);
      label.innerHTML = '<span>' + c.label + '</span><output id="out-' + c.id + '">' +
                        formatVal(c.value) + "</output>";

      var input = document.createElement("input");
      input.type = "range";
      input.id = id;
      input.min = c.min; input.max = c.max; input.step = c.step; input.value = c.value;
      if (c.hint) input.title = c.hint;

      input.addEventListener("input", function () {
        document.getElementById("out-" + c.id).textContent = formatVal(input.value);
        if (pyodide) {
          pyodide.globals.get("_set_param")(c.id, parseFloat(input.value));
        }
      });

      wrap.appendChild(label);
      wrap.appendChild(input);
      if (c.hint) {
        var hint = document.createElement("p");
        hint.className = "ctrl-hint";
        hint.textContent = c.hint;
        wrap.appendChild(hint);
      }
      controlsEl.appendChild(wrap);
    });
  }

  function describe(control, value) {
    var match = (control.options || []).filter(function (o) { return o.value === value; })[0];
    return match && match.hint ? match.hint : (control.hint || "");
  }

  function formatVal(v) {
    var n = parseFloat(v);
    return Math.abs(n) >= 10 ? String(Math.round(n)) : n.toFixed(2);
  }

  /* ---------- python glue ---------- */
  var GLUE = [
    "import json, types",
    "def _boot(src, w, h):",
    "    global _sim, _mod",
    "    _mod = types.ModuleType('simmod')",
    "    exec(src, _mod.__dict__)",
    "    _sim = _mod.Sim(w, h)",
    "    return _meta()",
    "def _meta():",
    "    return json.dumps({",
    "        'name': _sim.name, 'blurb': _sim.blurb, 'cite': _sim.cite,",
    "        'doc': (_mod.__doc__ or '').strip(),",
    "        'controls': _sim.controls(),",
    "    })",
    "def _set_param(k, v):",
    "    _sim.set_param(k, v)",
    "def _set_choice(k, v):",
    "    _sim.set_choice(k, v)",
    "def _pointer(x, y, d):",
    "    _sim.set_pointer(x, y, d)",
    "def _reset():",
    "    _sim.reset()",
    "def _frame(dt):",
    "    _sim.step(dt)",
    "    return json.dumps(_sim.scene())",
    ""
  ].join("\n");

  function setStatus(msg) { statusEl.textContent = msg || ""; }

  function loadPyodideOnce() {
    if (pyodide) return Promise.resolve(pyodide);
    if (loading) return loading;

    setStatus("Fetching the Python runtime\u2026");
    loading = new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = PYODIDE_URL + "pyodide.js";
      s.onload = resolve;
      s.onerror = function () { reject(new Error("Could not load Pyodide from the CDN.")); };
      document.head.appendChild(s);
    })
      .then(function () { return window.loadPyodide({ indexURL: PYODIDE_URL }); })
      .then(function (py) {
        pyodide = py;
        py.runPython(GLUE);
        return py;
      });

    return loading;
  }

  function loadSim(key) {
    var spec = SIMS[key];
    if (!spec) return;

    stopLoop();
    setStatus("Starting " + spec.label + "\u2026");

    return loadPyodideOnce()
      .then(function () { return fetch(spec.file, { cache: "no-cache" }); })
      .then(function (r) {
        if (!r.ok) throw new Error("Could not fetch " + spec.file + " (" + r.status + ")");
        return r.text();
      })
      .then(function (src) {
        codeEl.textContent = src;
        var metaJson = pyodide.globals.get("_boot")(src, canvas.width, canvas.height);
        var meta = JSON.parse(metaJson);

        nameEl.textContent = meta.name;
        descEl.textContent = meta.doc.split("\n\n")[1] || meta.blurb;
        citeEl.textContent = meta.cite;
        buildControls(meta.controls);

        overlay.hidden = true;
        resetBtn.disabled = false;
        pauseBtn.disabled = false;
        setStatus("");
        startLoop();
      })
      .catch(function (err) {
        overlay.hidden = false;
        setStatus(err.message || String(err));
      });
  }

  /* ---------- loop ---------- */
  function frame(now) {
    if (!running) return;
    var dt = lastTime ? Math.min((now - lastTime) / 1000, 0.05) : 0.016;
    lastTime = now;
    try {
      var scene = JSON.parse(pyodide.globals.get("_frame")(dt));
      drawScene(scene);
      renderReadout(scene.readout);
      setStatus(scene.status || "");
    } catch (err) {
      running = false;
      setStatus("Simulation error: " + err.message);
      return;
    }
    rafId = requestAnimationFrame(frame);
  }

  function startLoop() {
    if (running || !pyodide) return;
    running = true;
    lastTime = 0;
    pauseBtn.textContent = "Pause";
    rafId = requestAnimationFrame(frame);
  }

  function stopLoop() {
    running = false;
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;
  }

  /* ---------- wiring ---------- */
  startBtn.addEventListener("click", function () {
    startBtn.disabled = true;
    startBtn.textContent = "Loading\u2026";
    loadSim(currentKey).then(function () {
      startBtn.disabled = false;
      startBtn.textContent = "Load Python & run";
    });
  });

  resetBtn.addEventListener("click", function () {
    if (!pyodide) return;
    pyodide.globals.get("_reset")();
  });

  pauseBtn.addEventListener("click", function () {
    if (!pyodide) return;
    if (running) { stopLoop(); pauseBtn.textContent = "Resume"; }
    else { startLoop(); }
  });

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      currentKey = tab.dataset.sim;
      tabs.forEach(function (t) {
        var on = t === tab;
        t.classList.toggle("is-active", on);
        t.setAttribute("aria-selected", String(on));
      });
      nameEl.textContent = SIMS[currentKey].label;
      if (pyodide) {
        loadSim(currentKey);
      } else {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        overlay.hidden = false;
      }
    });
  });

  /* pointer -> simulation coordinates */
  function sendPointer(e, down) {
    if (!pyodide || !running) return;
    var r = canvas.getBoundingClientRect();
    var x = (e.clientX - r.left) * (canvas.width / r.width);
    var y = (e.clientY - r.top) * (canvas.height / r.height);
    pyodide.globals.get("_pointer")(x, y, !!down);
  }
  canvas.addEventListener("pointermove", function (e) { sendPointer(e, e.pressure > 0); });
  canvas.addEventListener("pointerdown", function (e) { sendPointer(e, true); });

  /* pause when off-screen or in a hidden tab */
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) stopLoop();
  });
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (entries) {
      if (!pyodide) return;
      if (!entries[0].isIntersecting) stopLoop();
    }, { threshold: 0 }).observe(canvas);
  }

  /* initial copy in the side panel before anything loads */
  blurbEl.textContent = "A fission yeast endocytic patch, built from the thesis below.";
  descEl.textContent = "Pick a simulation and press the button. The Python runs in your browser \u2014 you can read the source below it.";
})();
