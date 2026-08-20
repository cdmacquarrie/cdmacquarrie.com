"""
Endocytic actin patch assembly, and why position matters.

Clathrin-mediated endocytosis in fission yeast needs a branched actin
network to pull the membrane inward against turgor. The nucleation
promoting factor Wsp1 has to sit at the right distance from the membrane
for that force to be productive -- too close and the network pushes on
nothing, too far and it never engages the invagination.

Bbc1 is one of the adaptors that keeps Wsp1 where it belongs. Drop Bbc1
here and Wsp1 smears out along the tubule, exactly as you would expect
from the mutant.
"""

import math
import random


class Sim:
    name = "Endocytic patch"
    blurb = "Position Wsp1 relative to the membrane and try to internalise a vesicle."
    cite = "Related: MacQuarrie et al., J Cell Sci 132:jcs233502 (2019), doi:10.1242/jcs.233502"

    OPTIMUM = 74.0        # px offset where force transfer is best
    TARGET_DEPTH = 118.0  # invagination depth needed to pinch off

    def __init__(self, width, height):
        self.w = float(width)
        self.h = float(height)
        self.params = {"offset": 74.0, "bbc1": 0.85, "rate": 0.7}
        self.reset()

    # ---- interface -------------------------------------------------
    def controls(self):
        return [
            {"id": "offset", "label": "Wsp1 offset from membrane", "min": 10.0, "max": 150.0,
             "step": 1.0, "value": self.params["offset"],
             "hint": "Where the nucleation promoting factor sits along the tubule."},
            {"id": "bbc1", "label": "Bbc1 level", "min": 0.0, "max": 1.0,
             "step": 0.01, "value": self.params["bbc1"],
             "hint": "Low Bbc1 lets Wsp1 spread out - the mutant phenotype."},
            {"id": "rate", "label": "Actin assembly rate", "min": 0.1, "max": 1.0,
             "step": 0.01, "value": self.params["rate"],
             "hint": "How fast the patch builds filaments."},
        ]

    def set_param(self, key, value):
        if key in self.params:
            self.params[key] = float(value)

    def set_pointer(self, x, y, down):
        pass

    def reset(self):
        self.mem_y = 120.0
        self.depth = 0.0
        self.t = 0.0
        self.vesicles = 0
        self.attempts = 1
        self.stall = 0.0
        self.patch = []
        self.free = []

    # ---- dynamics --------------------------------------------------
    def _efficiency(self):
        """Gaussian around the optimal offset, degraded by Wsp1 spread."""
        off = self.params["offset"]
        sigma = 34.0
        placement = math.exp(-((off - self.OPTIMUM) ** 2) / (2.0 * sigma * sigma))
        focus = 0.35 + 0.65 * self.params["bbc1"]
        return placement * focus

    def _spread(self):
        return 8.0 + 46.0 * (1.0 - self.params["bbc1"])

    def step(self, dt):
        self.t += dt
        eff = self._efficiency()
        rate = self.params["rate"]

        # Build the patch around the Wsp1 site.
        cx = self.w * 0.5
        wy = self.mem_y + self.params["offset"]
        target_n = int(24 + 116 * rate * (0.4 + 0.6 * self.params["bbc1"]))
        spread = self._spread()

        while len(self.patch) < target_n:
            self.patch.append({
                "ox": random.gauss(0.0, spread * 0.8),
                "oy": random.gauss(0.0, spread),
                "ph": random.uniform(0.0, 6.28),
                "r": random.uniform(1.2, 2.6),
            })
        while len(self.patch) > target_n:
            self.patch.pop()

        # Force on the invagination.
        drive = 46.0 * rate * eff
        if drive > 6.0:
            self.depth += drive * dt
            self.stall = 0.0
        else:
            self.depth = max(0.0, self.depth - 14.0 * dt)
            self.stall += dt

        if self.depth >= self.TARGET_DEPTH:
            self.vesicles += 1
            self.attempts += 1
            self.free.append({"x": cx, "y": self.mem_y + self.depth,
                              "vy": random.uniform(26.0, 46.0),
                              "vx": random.uniform(-14.0, 14.0), "a": 1.0})
            self.depth = 0.0

        if self.stall > 6.0:
            self.attempts += 1
            self.stall = 0.0

        for v in self.free:
            v["y"] += v["vy"] * dt
            v["x"] += v["vx"] * dt
            v["a"] -= 0.22 * dt
        self.free = [v for v in self.free if v["a"] > 0.02 and v["y"] < self.h + 20]

        self._cx, self._wy = cx, wy

    # ---- rendering -------------------------------------------------
    def scene(self):
        shapes = []
        cx = self.w * 0.5
        neck = 26.0
        tip_y = self.mem_y + self.depth

        # Membrane, drawn as two segments flanking the invagination.
        shapes.append({"t": "line", "x1": 0, "y1": self.mem_y, "x2": cx - neck,
                       "y2": self.mem_y, "c": "accent2", "w": 2.2, "a": 0.9})
        shapes.append({"t": "line", "x1": cx + neck, "y1": self.mem_y, "x2": self.w,
                       "y2": self.mem_y, "c": "accent2", "w": 2.2, "a": 0.9})
        shapes.append({"t": "band", "y": self.mem_y - 5.0, "h": 5.0, "c": "accent2", "a": 0.10})

        # The tubule.
        shapes.append({"t": "curve", "x1": cx - neck, "y1": self.mem_y,
                       "cx": cx - neck * 0.55, "cy": tip_y, "x2": cx, "y2": tip_y,
                       "c": "accent2", "w": 2.2, "a": 0.9})
        shapes.append({"t": "curve", "x1": cx + neck, "y1": self.mem_y,
                       "cx": cx + neck * 0.55, "cy": tip_y, "x2": cx, "y2": tip_y,
                       "c": "accent2", "w": 2.2, "a": 0.9})

        # The actin patch.
        wy = self.mem_y + self.params["offset"]
        for p in self.patch:
            j = math.sin(self.t * 4.0 + p["ph"]) * 2.2
            shapes.append({"t": "dot", "x": cx + p["ox"] + j, "y": wy + p["oy"],
                           "r": p["r"], "c": "accent", "a": 0.6})

        shapes.append({"t": "glow", "x": cx, "y": wy, "r": self._spread() * 1.9,
                       "c": "accent", "a": 0.14})
        shapes.append({"t": "line", "x1": cx - 46, "y1": wy, "x2": cx + 46, "y2": wy,
                       "c": "accent", "w": 1.2, "a": 0.5})
        shapes.append({"t": "text", "x": cx + 54, "y": wy + 4, "s": "Wsp1", "c": "accent"})

        for v in self.free:
            shapes.append({"t": "dot", "x": v["x"], "y": v["y"], "r": 13.0,
                           "c": "accent2", "a": max(0.0, v["a"]) * 0.55})

        eff = self._efficiency()
        if eff > 0.75:
            verdict = "productive"
        elif eff > 0.4:
            verdict = "sluggish"
        else:
            verdict = "stalled"

        return {
            "shapes": shapes,
            "readout": [
                {"label": "Vesicles internalised", "value": str(self.vesicles)},
                {"label": "Force transfer", "value": "%d%%" % round(eff * 100)},
                {"label": "Invagination", "value": "%d%%" % round(100 * self.depth / self.TARGET_DEPTH)},
                {"label": "Patch", "value": verdict},
            ],
            "status": "t = %.1f s" % self.t,
        }
