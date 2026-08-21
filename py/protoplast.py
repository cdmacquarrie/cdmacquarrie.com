"""
Stripping the diatom: a tower defence.

Built from "Inducing protoplast formation in Phaeodactylum tricornutum by
silica deprivation, enzymatic treatment, or cytoskeletal inhibition"
(Arcadia Science, 2023).

A diatom's silica frustule is its armour, and the goal of the paper was to
get it off without killing the cell. So this is a defence game played from
the wrong side: cells stream down a channel, you place treatments along it,
and you are trying to strip every wall to nothing while keeping the cell
inside alive.

  Alcalase        a serine endopeptidase, screened at 0.3-1.5 Anson U/mL.
                  At 0.3 and 0.6 U/mL, 33-43% of cells made protoplasts.
                  Higher doses strip faster and lyse more.
  Silica-free     F/2 minus Si. Weakens every wall in the channel at once.
  Blebbistatin    myosin II inhibitor. Around 50% protoplast formation.
  CK-666          Arp2/3 inhibitor. Substantial formation.
  Latrunculin B   blocks actin polymerisation.
  SMIFH2          formin inhibitor.

The catch is the honest part. The cytoskeletal inhibitors only worked in
the first two trials; every attempt to replicate them gave 0% protoplast
formation. So in this game they are potent in trials 1 and 2 and inert
afterwards, which is exactly what the paper reports. Alcalase and silica
deprivation keep working.

The underlying idea is that the actin cytoskeleton helps *prevent*
protoplast formation, perhaps by anchoring the wall to the membrane -- so
knocking actin down should help you, and for two trials it does.
"""

import math
import random

TREATMENTS = {
    "alcalase": {
        "label": "Alcalase", "mech": "serine endopeptidase",
        "strip": 53.0, "harm": 0.42, "cyto": False,
        "note": "Digests the wall directly. Dose set by the slider. The only reliable option."},
    "blebbistatin": {
        "label": "(-)-Blebbistatin", "mech": "myosin II inhibitor",
        "strip": 30.0, "harm": 0.16, "cyto": True,
        "note": "~50% protoplasts in trial 1-2, then nothing. Modelled binding myosin E."},
    "ck666": {
        "label": "CK-666", "mech": "Arp2/3 inhibitor",
        "strip": 26.0, "harm": 0.14, "cyto": True,
        "note": "Substantial formation in the first trials, irreproducible after."},
    "latrunculin": {
        "label": "Latrunculin B", "mech": "blocks actin polymerisation",
        "strip": 24.0, "harm": 0.18, "cyto": True,
        "note": "If actin anchors the wall, removing it should help. For two trials it did."},
    "smifh2": {
        "label": "SMIFH2", "mech": "formin inhibitor",
        "strip": 20.0, "harm": 0.15, "cyto": True,
        "note": "Formin inhibition, same irreproducibility as the others."},
}
ORDER = ["alcalase", "blebbistatin", "ck666", "latrunculin", "smifh2"]

# Anson units/mL -> multiplier on stripping and on damage to the cell.
DOSES = [(0.3, 0.97, 0.5), (0.6, 1.00, 0.9), (1.0, 1.30, 2.2), (1.5, 1.62, 3.6)]

SLOTS = [(215.0, 150.0), (355.0, 150.0), (495.0, 150.0),
         (215.0, 410.0), (355.0, 410.0), (495.0, 410.0)]
LANE_Y = 280.0
LANE_H = 96.0
ENTRY_X = 40.0
EXIT_X = 700.0
RADIUS = 88.0


class Cell:
    """One diatom drifting down the channel."""

    def __init__(self, w, morph):
        self.morph = morph                 # "fusiform" or "triradiate"
        self.x = ENTRY_X
        self.y = LANE_Y + random.uniform(-LANE_H * 0.4, LANE_H * 0.4)
        self.wall = 100.0                  # frustule integrity, %
        self.viability = 100.0
        self.v = random.uniform(52.0, 74.0)
        self.spin = random.uniform(0.0, 6.28)
        self.fate = None                   # protoplast | lysed | escaped

    def step(self, dt):
        self.x += self.v * dt
        self.y += math.sin(self.x * 0.02 + self.spin) * 7.0 * dt


class Sim:
    name = "Protoplast siege"
    blurb = "Strip the silica wall off every diatom without killing the cell."
    cite = ("Avasthi P, Bigge BM, Hochstrasser ML, MacQuarrie CD, Radkov A. "
            "Inducing protoplast formation in Phaeodactylum tricornutum. "
            "Arcadia Science (2023), doi:10.57844/arcadia-fh8f-xz51")

    def __init__(self, width, height):
        self.w = float(width)
        self.h = float(height)
        self.selected = "alcalase"
        self.params = {"dose": 0.6, "silica": 0.0, "speed": 1.0}
        self.reset()

    # ---- interface -------------------------------------------------
    def controls(self):
        return [
            {"id": "treat", "type": "select", "label": "Treatment to place",
             "value": self.selected,
             "options": [{"value": k, "label": TREATMENTS[k]["label"],
                          "hint": TREATMENTS[k]["note"]} for k in ORDER]},
            {"id": "dose", "label": "Alcalase dose (Anson U/mL)", "min": 0.3, "max": 1.5,
             "step": 0.3, "value": self.params["dose"],
             "hint": "0.3-0.6 gave 33-43% protoplasts. Higher strips faster and lyses more."},
            {"id": "silica", "label": "Silica-free medium", "min": 0.0, "max": 1.0,
             "step": 1.0, "value": self.params["silica"],
             "hint": "F/2 minus Si. Thins every wall in the channel. 1 is on."},
            {"id": "speed", "label": "Playback speed", "min": 0.3, "max": 2.5,
             "step": 0.05, "value": self.params["speed"], "hint": ""},
        ]

    def set_param(self, key, value):
        if key in self.params:
            self.params[key] = float(value)

    def set_choice(self, key, value):
        if key == "treat" and value in TREATMENTS:
            self.selected = value

    def set_pointer(self, x, y, down):
        """Click a station to place the selected treatment, or clear it."""
        if not down:
            return
        for i, (sx, sy) in enumerate(SLOTS):
            if math.hypot(x - sx, y - sy) < 34.0:
                self.towers[i] = None if self.towers[i] == self.selected else self.selected
                return

    def reset(self):
        self.towers = [None] * len(SLOTS)
        self.cells = []
        self.trial = 1
        self.spawned = 0
        self.protoplasts = 0
        self.lysed = 0
        self.escaped = 0
        self.trial_done = 0
        self.clock = 0.0
        self.spawn_t = 0.0
        self.flash = ""
        self.flash_t = 0.0

    # ---- mechanics -------------------------------------------------
    def _dose(self):
        best = DOSES[0]
        for d in DOSES:
            if self.params["dose"] >= d[0] - 0.01:
                best = d
        return best

    def _tower_effect(self, key):
        """Stripping power and collateral damage for one station, this trial."""
        t = TREATMENTS[key]
        strip, harm = t["strip"], t["harm"]
        if key == "alcalase":
            _u, sm, hm = self._dose()
            strip *= sm
            harm *= hm
        elif t["cyto"] and self.trial > 2:
            # The finding that matters: it stopped working after two trials.
            return 0.0, 0.0
        return strip, harm

    def step(self, dt):
        dt = min(dt, 0.05) * self.params["speed"]
        self.clock += dt
        self.flash_t = max(0.0, self.flash_t - dt)

        # 12 cells per trial.
        self.spawn_t -= dt
        if self.spawned < 12 and self.spawn_t <= 0.0:
            self.cells.append(Cell(self.w, "fusiform" if random.random() < 0.6 else "triradiate"))
            self.spawned += 1
            self.spawn_t = 0.9

        silica = self.params["silica"] > 0.5
        for c in self.cells:
            c.step(dt)
            if silica:
                c.wall = max(0.0, c.wall - 3.4 * dt)
            for i, key in enumerate(self.towers):
                if not key:
                    continue
                sx, _sy = SLOTS[i]
                # The station sits off to the side; its field covers the
                # channel itself, which is what the glow draws.
                d = math.hypot(c.x - sx, c.y - LANE_Y)
                if d > RADIUS:
                    continue
                strip, harm = self._tower_effect(key)
                falloff = 1.0 - (d / RADIUS) ** 2
                if c.wall > 0.0:
                    c.wall = max(0.0, c.wall - strip * falloff * dt)
                else:
                    # Nothing left to digest; the enzyme starts on the cell.
                    c.viability = max(0.0, c.viability - harm * 95.0 * falloff * dt)
                c.viability = max(0.0, c.viability - harm * 3.0 * falloff * dt)

            if c.viability <= 0.0 and c.fate is None:
                c.fate = "lysed"
            elif c.x >= EXIT_X and c.fate is None:
                c.fate = "protoplast" if c.wall <= 6.0 else "escaped"

        for c in [c for c in self.cells if c.fate]:
            if c.fate == "protoplast":
                self.protoplasts += 1
            elif c.fate == "lysed":
                self.lysed += 1
            else:
                self.escaped += 1
            self.trial_done += 1
        self.cells = [c for c in self.cells if not c.fate]

        if self.spawned >= 12 and not self.cells:
            self.trial += 1
            self.spawned = 0
            self.trial_done = 0
            if self.trial == 3 and any(t and TREATMENTS[t]["cyto"] for t in self.towers):
                self.flash = "trial 3: the cytoskeletal drugs stopped working"
                self.flash_t = 4.0

    # ---- rendering -------------------------------------------------
    COLOURS = {"alcalase": "warm", "blebbistatin": "accent2", "ck666": "accent",
               "latrunculin": "cool", "smifh2": "dim"}

    def scene(self):
        shapes = []
        top = LANE_Y - LANE_H / 2.0

        # The channel.
        shapes.append({"t": "band", "y": top, "h": LANE_H, "c": "cool", "a": 0.07})
        for y in (top, top + LANE_H):
            shapes.append({"t": "line", "x1": 0, "y1": y, "x2": EXIT_X + 60, "y2": y,
                           "c": "cool", "w": 1.0, "a": 0.3})
        shapes.append({"t": "line", "x1": EXIT_X, "y1": top - 12, "x2": EXIT_X,
                       "y2": top + LANE_H + 12, "c": "accent", "w": 1.8, "a": 0.7})
        shapes.append({"t": "text", "x": EXIT_X + 8, "y": top - 18, "s": "collect", "c": "accent"})

        # Treatment stations.
        for i, (sx, sy) in enumerate(SLOTS):
            key = self.towers[i]
            if key:
                col = self.COLOURS[key]
                strip, _h = self._tower_effect(key)
                live = strip > 0.0
                shapes.append({"t": "glow", "x": sx, "y": LANE_Y, "r": RADIUS,
                               "c": col, "a": 0.10 if live else 0.03})
                shapes.append({"t": "line", "x1": sx, "y1": sy, "x2": sx, "y2": LANE_Y,
                               "c": col, "w": 1.2, "a": 0.35 if live else 0.12})
                shapes.append({"t": "dot", "x": sx, "y": sy, "r": 13.0, "c": col,
                               "a": 0.85 if live else 0.22})
                label = TREATMENTS[key]["label"]
                if not live:
                    label += " (inert)"
                shapes.append({"t": "text", "x": sx - 30, "y": sy + (28 if sy < LANE_Y else -20),
                               "s": label, "c": col if live else "dim"})
            else:
                shapes.append({"t": "dot", "x": sx, "y": sy, "r": 6.0, "c": "dim", "a": 0.30})

        # Cells.
        for c in self.cells:
            wall_a = 0.15 + 0.75 * (c.wall / 100.0)
            via = c.viability / 100.0
            if c.wall <= 6.0:
                shapes.append({"t": "glow", "x": c.x, "y": c.y, "r": 20.0, "c": "accent", "a": 0.18 * via})
                shapes.append({"t": "dot", "x": c.x, "y": c.y, "r": 8.0, "c": "accent", "a": 0.75 * via})
            elif c.morph == "fusiform":
                for s in (-1, 1):
                    shapes.append({"t": "curve", "x1": c.x - 13, "y1": c.y,
                                   "cx": c.x, "cy": c.y + s * 8, "x2": c.x + 13, "y2": c.y,
                                   "c": "cool", "w": 1.8, "a": wall_a})
                shapes.append({"t": "dot", "x": c.x, "y": c.y, "r": 3.6, "c": "accent", "a": 0.7 * via})
            else:
                for k in range(3):
                    a = c.spin + k * 2.094
                    shapes.append({"t": "line", "x1": c.x, "y1": c.y,
                                   "x2": c.x + math.cos(a) * 13, "y2": c.y + math.sin(a) * 13,
                                   "c": "cool", "w": 2.0, "a": wall_a})
                shapes.append({"t": "dot", "x": c.x, "y": c.y, "r": 3.6, "c": "accent", "a": 0.7 * via})

        shapes.append({"t": "text", "x": 14, "y": 40,
                       "s": "click a station to place %s" % TREATMENTS[self.selected]["label"],
                       "c": "dim"})
        if self.flash_t > 0.0:
            shapes.append({"t": "band", "y": 496, "h": 32, "c": "accent2", "a": 0.14})
            shapes.append({"t": "text", "x": 18, "y": 516, "s": self.flash, "c": "accent2"})

        total = self.protoplasts + self.lysed + self.escaped
        pct = (100.0 * self.protoplasts / total) if total else 0.0
        return {
            "shapes": shapes,
            "readout": [
                {"label": "Protoplasts", "value": "%d  (%d%%)" % (self.protoplasts, round(pct))},
                {"label": "Lysed", "value": str(self.lysed)},
                {"label": "Wall intact", "value": str(self.escaped)},
                {"label": "Trial", "value": str(self.trial)},
            ],
            "status": "trial %d  \u2014  %d cells collected" % (self.trial, total),
        }
