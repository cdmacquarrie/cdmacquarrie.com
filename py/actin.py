"""
Branched actin network assembly.

A toy dendritic-nucleation model in the spirit of the Arp2/3 work:
filaments elongate from a free monomer pool, Arp2/3 nucleates daughter
filaments off the sides of existing ones at ~70 degrees, and capping
protein permanently stops growth.

The interesting part is that there is an optimum. Crank branching up and
you make many filaments that exhaust the monomer pool before any of them
push very far. Crank it down and you have too few pushers. Somewhere in
between, the network does the most work against the membrane.

Deliberately qualitative -- this is intuition, not a quantitative model.
"""

import math
import random

BRANCH_ANGLE = math.radians(70.0)


class Sim:
    name = "Branched actin"
    blurb = "Grow a dendritic actin network and push the membrane as far as you can."
    cite = "Related: MacQuarrie et al., J Cell Sci (2019); Arp2/3 nucleation work, 2020-21."

    def __init__(self, width, height):
        self.w = float(width)
        self.h = float(height)
        self.params = {"arp": 0.20, "cap": 0.20, "pool": 1.0}
        self.reset()

    # ---- interface -------------------------------------------------
    def controls(self):
        return [
            {"id": "arp", "label": "Arp2/3 branching", "min": 0.0, "max": 1.0,
             "step": 0.01, "value": self.params["arp"],
             "hint": "How readily a new filament nucleates off an existing one."},
            {"id": "cap", "label": "Capping protein", "min": 0.0, "max": 1.0,
             "step": 0.01, "value": self.params["cap"],
             "hint": "How quickly growing barbed ends are shut down."},
            {"id": "pool", "label": "Monomer pool", "min": 0.2, "max": 2.0,
             "step": 0.05, "value": self.params["pool"],
             "hint": "Total G-actin available to the network."},
        ]

    def set_param(self, key, value):
        if key in self.params:
            self.params[key] = float(value)

    def set_pointer(self, x, y, down):
        pass

    def reset(self):
        self.membrane_y = 250.0
        self.membrane_y0 = 250.0
        self.t = 0.0
        self.total_length = 0.0
        base = self.h - 60.0
        self.fils = []
        for i in range(6):
            x = self.w * (0.22 + 0.56 * (i / 5.0))
            self.fils.append({
                "x": x, "y": base, "tx": x, "ty": base,
                "ang": -math.pi / 2 + random.uniform(-0.35, 0.35),
                "capped": False, "gen": 0,
            })

    # ---- dynamics --------------------------------------------------
    def _budget(self):
        capacity = 16000.0 * self.params["pool"]
        return max(0.0, 1.0 - self.total_length / capacity)

    def step(self, dt):
        self.t += dt
        free = self._budget()
        # Elongation never stops dead -- a starved network still creeps
        # forward, it just does far less work.
        drive = 0.12 + 0.88 * free
        growth = 85.0 * dt * drive
        arp = self.params["arp"]
        cap = self.params["cap"]

        newborn = []
        for f in self.fils:
            if f["capped"]:
                continue

            f["tx"] += math.cos(f["ang"]) * growth
            f["ty"] += math.sin(f["ang"]) * growth
            self.total_length += growth

            # Sideways drift keeps the network from looking like a comb.
            f["ang"] += random.uniform(-0.05, 0.05) * dt * 60.0

            # Push the membrane when a barbed end runs into it.
            if f["ty"] <= self.membrane_y + 4.0:
                f["ty"] = self.membrane_y + 4.0
                self.membrane_y -= 70.0 * dt * drive
                f["ang"] += random.uniform(-0.5, 0.5)

            # Keep filaments on stage.
            if f["tx"] < 20.0 or f["tx"] > self.w - 20.0:
                f["ang"] = math.pi - f["ang"]

            if random.random() < cap * dt * 2.2:
                f["capped"] = True

            if len(self.fils) + len(newborn) < 420:
                if random.random() < arp * dt * 3.4 * drive:
                    side = 1.0 if random.random() < 0.5 else -1.0
                    newborn.append({
                        "x": f["tx"], "y": f["ty"], "tx": f["tx"], "ty": f["ty"],
                        "ang": f["ang"] + side * BRANCH_ANGLE + random.uniform(-0.12, 0.12),
                        "capped": False, "gen": f["gen"] + 1,
                    })

        self.fils.extend(newborn)

    # ---- rendering -------------------------------------------------
    def scene(self):
        shapes = []
        growing = 0

        for f in self.fils:
            if not f["capped"]:
                growing += 1
            shade = "accent" if not f["capped"] else "dim"
            shapes.append({
                "t": "line", "x1": f["x"], "y1": f["y"], "x2": f["tx"], "y2": f["ty"],
                "c": shade, "w": max(0.7, 1.7 - f["gen"] * 0.08),
                "a": 0.85 if not f["capped"] else 0.30,
            })
            if not f["capped"]:
                shapes.append({"t": "dot", "x": f["tx"], "y": f["ty"], "r": 2.0,
                               "c": "accent2", "a": 0.9})

        shapes.append({"t": "band", "y": self.membrane_y, "h": 10.0, "c": "accent2", "a": 0.22})
        shapes.append({"t": "line", "x1": 0, "y1": self.membrane_y, "x2": self.w,
                       "y2": self.membrane_y, "c": "accent2", "w": 2.0, "a": 0.9})

        pushed = self.membrane_y0 - self.membrane_y
        return {
            "shapes": shapes,
            "readout": [
                {"label": "Filaments", "value": str(len(self.fils))},
                {"label": "Still growing", "value": str(growing)},
                {"label": "Monomer left", "value": "%d%%" % round(self._budget() * 100)},
                {"label": "Membrane pushed", "value": "%.1f" % pushed},
            ],
            "status": "t = %.1f s" % self.t,
        }
