"""
A hunting chlorarachniophyte.

Chlorarachniophytes throw out fine, branching extensions that depend on
light and on the Arp2/3 complex, and they use them to move and to catch
prey. This is a toy version of that: move your pointer to place the light,
and the cell extends pseudopodia toward it, sweeping up bacteria on the way.

Turn Arp2/3 off and the extensions stop forming -- which is roughly the
experiment.
"""

import math
import random


def _seg_dist(px, py, ax, ay, bx, by):
    """Distance from a point to the segment ab -- a pseudopod catches prey
    anywhere along its length, not just at the very tip."""
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    if denom <= 1e-9:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / denom
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _wrap(v, lo, hi):
    if v < lo:
        return hi
    if v > hi:
        return lo
    return v


class Sim:
    name = "Hunting cell"
    blurb = "Move the light. The cell extends toward it and eats what it touches."
    cite = "Related: Avasthi & MacQuarrie, Arcadia Science (2022), doi:10.57844/arcadia-eqg7-kf54"

    def __init__(self, width, height):
        self.w = float(width)
        self.h = float(height)
        self.params = {"arp": 0.8, "photo": 0.7, "reach": 0.6}
        self.reset()

    # ---- interface -------------------------------------------------
    def controls(self):
        return [
            {"id": "arp", "label": "Arp2/3 activity", "min": 0.0, "max": 1.0,
             "step": 0.01, "value": self.params["arp"],
             "hint": "Set to zero to inhibit branched-actin extension entirely."},
            {"id": "photo", "label": "Light dependence", "min": 0.0, "max": 1.0,
             "step": 0.01, "value": self.params["photo"],
             "hint": "How strongly extensions orient toward the light."},
            {"id": "reach", "label": "Extension reach", "min": 0.2, "max": 1.0,
             "step": 0.01, "value": self.params["reach"],
             "hint": "Maximum pseudopod length."},
        ]

    def set_param(self, key, value):
        if key in self.params:
            self.params[key] = float(value)

    def set_pointer(self, x, y, down):
        self.light = (float(x), float(y))

    def reset(self):
        self.cx = self.w * 0.5
        self.cy = self.h * 0.5
        self.light = (self.w * 0.78, self.h * 0.28)
        self.t = 0.0
        self.eaten = 0
        self.pseudopods = []
        self.prey = []
        for _ in range(22):
            self._spawn_prey()

    def _spawn_prey(self):
        edge = random.random()
        if edge < 0.5:
            x = random.uniform(20, self.w - 20)
            y = random.choice([15.0, self.h - 15.0])
        else:
            x = random.choice([15.0, self.w - 15.0])
            y = random.uniform(20, self.h - 20)
        self.prey.append({
            "x": x, "y": y,
            "vx": random.uniform(-18, 18),
            "vy": random.uniform(-18, 18),
            "ph": random.uniform(0, 6.28),
        })

    # ---- dynamics --------------------------------------------------
    def step(self, dt):
        self.t += dt
        arp = self.params["arp"]
        photo = self.params["photo"]
        max_len = 60.0 + 210.0 * self.params["reach"]

        lx, ly = self.light
        to_light = math.atan2(ly - self.cy, lx - self.cx)

        # Drift the cell body gently toward the light.
        self.cx += math.cos(to_light) * 11.0 * dt * arp
        self.cy += math.sin(to_light) * 11.0 * dt * arp
        self.cx = min(max(self.cx, 40.0), self.w - 40.0)
        self.cy = min(max(self.cy, 40.0), self.h - 40.0)

        # Nucleate new pseudopodia -- Arp2/3 dependent.
        if len(self.pseudopods) < 14 and random.random() < arp * dt * 7.0:
            spread = (1.0 - photo) * math.pi + 0.25
            ang = to_light + random.uniform(-spread, spread)
            self.pseudopods.append({
                "ang": ang, "len": 6.0,
                "grow": True, "life": 0.0,
                "wob": random.uniform(-0.6, 0.6),
            })

        for p in self.pseudopods:
            p["life"] += dt
            p["ang"] += math.sin(self.t * 1.6 + p["wob"]) * 0.35 * dt
            if p["grow"]:
                p["len"] += (95.0 * arp + 12.0) * dt
                if p["len"] >= max_len:
                    p["grow"] = False
            else:
                p["len"] -= 70.0 * dt
        self.pseudopods = [p for p in self.pseudopods if p["len"] > 3.0]

        # Prey wander, and get eaten on contact with the cell or a tip.
        survivors = []
        for b in self.prey:
            b["ph"] += dt * 3.0
            b["x"] += (b["vx"] + math.cos(b["ph"]) * 9.0) * dt
            b["y"] += (b["vy"] + math.sin(b["ph"] * 1.3) * 9.0) * dt
            b["x"] = _wrap(b["x"], -10.0, self.w + 10.0)
            b["y"] = _wrap(b["y"], -10.0, self.h + 10.0)

            if math.hypot(b["x"] - self.cx, b["y"] - self.cy) < 30.0:
                self.eaten += 1
                continue

            caught = False
            for p in self.pseudopods:
                tx = self.cx + math.cos(p["ang"]) * p["len"]
                ty = self.cy + math.sin(p["ang"]) * p["len"]
                if _seg_dist(b["x"], b["y"], self.cx, self.cy, tx, ty) < 11.0:
                    caught = True
                    break
            if caught:
                self.eaten += 1
                continue
            survivors.append(b)

        self.prey = survivors
        while len(self.prey) < 22:
            self._spawn_prey()

    # ---- rendering -------------------------------------------------
    def scene(self):
        shapes = []
        lx, ly = self.light

        shapes.append({"t": "glow", "x": lx, "y": ly, "r": 115.0, "c": "warm", "a": 0.20})

        for p in self.pseudopods:
            tx = self.cx + math.cos(p["ang"]) * p["len"]
            ty = self.cy + math.sin(p["ang"]) * p["len"]
            mx = self.cx + math.cos(p["ang"] + 0.22) * p["len"] * 0.55
            my = self.cy + math.sin(p["ang"] + 0.22) * p["len"] * 0.55
            shapes.append({"t": "curve", "x1": self.cx, "y1": self.cy,
                           "cx": mx, "cy": my, "x2": tx, "y2": ty,
                           "c": "accent", "w": 1.6, "a": 0.75})
            shapes.append({"t": "dot", "x": tx, "y": ty, "r": 3.0, "c": "accent", "a": 0.95})

        for b in self.prey:
            shapes.append({"t": "dot", "x": b["x"], "y": b["y"], "r": 3.2, "c": "accent2", "a": 0.85})

        shapes.append({"t": "glow", "x": self.cx, "y": self.cy, "r": 46.0, "c": "accent", "a": 0.20})
        shapes.append({"t": "dot", "x": self.cx, "y": self.cy, "r": 21.0, "c": "accent", "a": 0.55})
        shapes.append({"t": "dot", "x": self.cx - 5.0, "y": self.cy - 4.0, "r": 8.0, "c": "accent2", "a": 0.55})

        note = "Arp2/3 inhibited - no extensions" if self.params["arp"] < 0.05 else "hunting"
        return {
            "shapes": shapes,
            "readout": [
                {"label": "Prey captured", "value": str(self.eaten)},
                {"label": "Extensions", "value": str(len(self.pseudopods))},
                {"label": "State", "value": note},
            ],
            "status": "t = %.1f s  -  move the pointer to steer the light" % self.t,
        }
