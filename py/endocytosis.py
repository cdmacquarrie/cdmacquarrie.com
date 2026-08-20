"""
Clathrin-mediated endocytosis in fission yeast: a sandbox.

Built from the model in Cameron MacQuarrie's PhD thesis, "Mechanisms of
Wiskott-Aldrich syndrome protein Wsp1 positioning and regulation at sites
of endocytosis in S. pombe" (SUNY Upstate, 2020), which threads six
chapters into one regulatory cycle:

  1. Wsp1 arrives with Vrp1 ~1-2 s before actin onset, already active.
  2. Vrp1 binds the Wsp1 WH1 domain and switches on its NPF activity
     (Ch. 3). Delete Vrp1, or just its Wsp1-binding domain, and patch
     actin drops by roughly a third.
  3. Wsp1 and Vrp1 both bind the Myo1 tail, holding nucleation next to
     the membrane where the resulting filaments push productively (Ch. 2).
  4. Bbc1 binds that same Myo1 tail and competes Vrp1-Wsp1 off it,
     releasing them to internalise with the vesicle (Ch. 2). Without
     Bbc1 they stay at the base and invaginations grow twice as deep.
  5. Once released, the freed Wsp1-Vrp1 proline-rich domains are open for
     the three SH3 domains of Sla1, forming the SWIM complex -- Sla1-
     mediated Wsp1 Inhibition after Movement -- which shuts off NPF
     activity and starts disassembly (Ch. 4).
  6. Myo1 supplies force as a motor, not as an NPF: myo1-dCA patches
     travel a normal distance (Ch. 5). Capping protein barely matters
     for patch actin (Ch. 6).

Distance travelled by tip markers (End4, Ent1, Sla1) is the readout for
force generated, exactly as in the thesis: 0.5 um in wild type, 1.0 um in
bbc1-delta.

Simplified on purpose -- rates are tuned so the genotypes land on the
published numbers, not derived from biochemistry.
"""

import math
import random

# Genotype -> which parts of the machinery are intact.
# wsp1/vrp1/myo1/bbc1/sla1 = protein present; the rest are domain mutants.
WT = {"wsp1": 1, "wsp1_ca": 1, "vrp1": 1, "vrp1_wbd": 1, "myo1": 1,
      "myo1_motor": 1, "myo1_ca": 1, "myo1_sh3": 1, "bbc1": 1, "sla1": 1, "cp": 1}


def _g(**kw):
    d = dict(WT)
    d.update(kw)
    return d


GENOTYPES = [
    ("wt",          "wild type",          _g(),
     "0.5 um internalisation. The reference."),
    ("bbc1D",       "bbc1\u0394",         _g(bbc1=0),
     "Nothing competes Vrp1-Wsp1 off the Myo1 tail, so they stay at the base and keep pushing: ~1.0 um, twice wild type (Ch. 2)."),
    ("sla1D",       "sla1\u0394",         _g(sla1=0),
     "No SWIM complex, so Wsp1 is never switched off -- but depth is unchanged. Sla1 terminates, it does not position (Ch. 4)."),
    ("bbc1D_sla1D", "bbc1\u0394 sla1\u0394", _g(bbc1=0, sla1=0),
     "Still ~2x deep. Myo1 itself partially internalises here (Ch. 2)."),
    ("vrp1D",       "vrp1\u0394",         _g(vrp1=0),
     "Wsp1 is present but poorly activated: actin down ~33-43%, internalisation down ~28-40% (Ch. 3)."),
    ("vrp1_wbd",    "vrp1-\u0394WBD",     _g(vrp1_wbd=0),
     "Vrp1 without its Wsp1-binding domain phenocopies the full deletion -- the interaction is what matters (Ch. 3)."),
    ("vrp1_wh2",    "vrp1-\u0394WH2",     _g(),
     "Normal. Vrp1's own actin-binding domain is dispensable for patch assembly (Ch. 3)."),
    ("wsp1D",       "wsp1\u0394",         _g(wsp1=0, wsp1_ca=0),
     "The main NPF is gone. About half of patches never internalise at all, and everything slows down (Ch. 3, 5)."),
    ("wsp1_ca",     "wsp1-\u0394CA",      _g(wsp1_ca=0),
     "Wsp1 is there but cannot touch Arp2/3. Same internalisation failure as the deletion -- it is the NPF activity that counts (Ch. 3)."),
    ("myo1D",       "myo1\u0394",         _g(myo1=0, myo1_motor=0, myo1_ca=0, myo1_sh3=0),
     "No motor, no retention, no Bbc1 recruitment. Patches rarely internalise (Ch. 5)."),
    ("myo1_ca",     "myo1-\u0394CA",      _g(myo1_ca=0),
     "Myo1 NPF activity deleted -- and nothing changes. Myo1 contributes force as a motor, not as a nucleator (Ch. 2, 5)."),
    ("myo1_sh3",    "myo1-SH3-LCA",       _g(myo1_sh3=0),
     "The SH3 domain that holds Wsp1 at the base is gone, so Wsp1 leaves early."),
    ("bbc1D_myo1sh3", "bbc1\u0394 myo1-SH3-LCA", _g(bbc1=0, myo1_sh3=0),
     "The rescue: deleting the retention domain cancels the bbc1\u0394 phenotype, back to 0.5 um (Ch. 2)."),
    ("acp2D",       "capping protein\u2193", _g(),
     "Blocking barbed ends barely touches patch actin -- mildly increased, assembly unchanged (Ch. 6)."),
]

GENO_MAP = dict((k, v) for k, _l, v, _h in GENOTYPES)

# Seconds, relative to Wsp1/Vrp1 arrival at the patch.
T_ACTIN_ONSET = 2.0     # Wsp1 precedes actin by ~1-2 s
T_BBC1 = 2.3            # Bbc1 arrives and starts competing Vrp1 off Myo1
MAX_LIFETIME = 17.0     # Wsp1 patch lifetime is ~10-17 s

NM_PER_PX = 3.0         # drawing scale for the invagination


class Sim:
    name = "Endocytic patch"
    blurb = "Pick a genotype and watch a fission yeast endocytic patch succeed or fail."
    cite = ("Built from MacQuarrie CD, PhD thesis, SUNY Upstate (2020); "
            "MacQuarrie et al., J Cell Sci 132:jcs233502 (2019).")

    # Tuned so the genotypes land on the measured numbers.
    VRP1_OFF = 0.60      # Wsp1 NPF activity without Vrp1 activation
    MYO1_NPF = 0.10      # Myo1's own weak NPF contribution
    OTHER_NPF = 0.30     # Pan1, Dip1 and friends; why half of wsp1D still goes
    POS_NOMYO = 0.13     # force transfer with no Myo1 anchoring the network
    POS_FLOOR = 0.50     # force transfer once Wsp1 has left the Myo1 tail
    K_ASSEMBLY = 1.05
    K_DECAY = 0.22
    K_HALF = 2.80        # actin at which force transfer is half-maximal
    LOAD = 0.80          # membrane tension pulling back, per nm of depth
    K_ACTIN = 1262.0     # nm/s per unit actin at perfect positioning
    K_MYO = 20.0         # nm/s from Myo1 motor power strokes
    RELEASE = 1.10       # rate Bbc1 competes Vrp1-Wsp1 off the Myo1 tail
    SWIM_RATE = 0.10     # rate Sla1 captures freed PRDs
    FAIL_BELOW = 150.0   # nm; below this the patch never really internalised
    D_MOVE = 150.0       # nm the patch must travel before Sla1 can shut Wsp1 down
    SCISSION_FRAC = 0.55 # fraction of peak actin at which the neck constricts
    RESEAL = 1500.0      # nm/s the tubule collapses after scission or failure
    PINCH_TIME = 0.40    # s for the neck to constrict once disassembly starts
    HOB1_REF = 500.0     # nm of invagination taken as the wild-type Hob1 level

    def __init__(self, width, height):
        self.w = float(width)
        self.h = float(height)
        self.geno_key = "wt"
        self.g = dict(GENO_MAP["wt"])
        self.params = {"arp": 1.0, "turgor": 1.0, "speed": 1.0}
        self.reset()

    # ---- interface -------------------------------------------------
    def controls(self):
        return [
            {"id": "geno", "type": "select", "label": "Genotype", "value": self.geno_key,
             "options": [{"value": k, "label": lab, "hint": hint}
                         for k, lab, _cfg, hint in GENOTYPES]},
            {"id": "arp", "label": "Arp2/3 availability", "min": 0.0, "max": 1.5,
             "step": 0.01, "value": self.params["arp"],
             "hint": "Scales branched nucleation downstream of whatever NPF activity survives."},
            {"id": "turgor", "label": "Turgor pressure", "min": 0.5, "max": 2.0,
             "step": 0.01, "value": self.params["turgor"],
             "hint": "The load the actin network works against. Fission yeast is unusually high."},
            {"id": "speed", "label": "Playback speed", "min": 0.25, "max": 3.0,
             "step": 0.05, "value": self.params["speed"],
             "hint": "Real patches last 10-17 s."},
        ]

    def set_param(self, key, value):
        if key in self.params:
            self.params[key] = float(value)

    def set_choice(self, key, value):
        if key == "geno" and value in GENO_MAP:
            self.geno_key = value
            self.g = dict(GENO_MAP[value])
            self.reset()

    def set_pointer(self, x, y, down):
        pass

    def reset(self):
        self.clock = 0.0
        self.free_vesicles = []
        self.depths = []
        self.n_failed = 0
        self.n_released = 0
        self._new_patch()

    def _new_patch(self):
        g = self.g
        self.t = 0.0
        self.actin = 0.0
        self.depth = 0.0
        self.max_depth = 0.0
        self.swim = 0.0
        self.wsp1 = 0.0
        self.peak_actin = 0.0
        self.retained = 1.0 if (g["myo1"] and g["myo1_sh3"]) else 0.0
        self.jitter = random.uniform(0.72, 1.32)
        self.phase = "growing"
        self.pinch = 0.0
        self.flash = 0.0
        self.trace = []

    # ---- model -----------------------------------------------------
    def _npf(self):
        """Total Arp2/3-activating capacity at the patch."""
        g = self.g
        wsp = 0.0
        if g["wsp1"] and g["wsp1_ca"]:
            vrp = 1.0 if (g["vrp1"] and g["vrp1_wbd"]) else self.VRP1_OFF
            wsp = vrp * (1.0 - self.swim) * self.wsp1
        myo = self.MYO1_NPF if (g["myo1"] and g["myo1_ca"]) else 0.0
        return wsp + myo + self.OTHER_NPF

    def _positioning(self):
        """How much of the actin network's push reaches the invagination tip.

        While Vrp1-Wsp1 are held on the Myo1 tail, nucleation happens right
        at the base of the tubule and the filaments elongate it efficiently.
        Once Bbc1 competes them off, they ride the tip inward and their
        filaments push on geometry that no longer lengthens the invagination.
        Losing that retention early is not catastrophic, because in wild type
        it is lost after only a few seconds anyway -- but never losing it, as
        in bbc1D, keeps the productive geometry for the whole patch.
        """
        floor = self.POS_FLOOR if self.g["myo1"] else self.POS_NOMYO
        return floor + (1.0 - floor) * self.retained

    def step(self, dt):
        dt = min(dt, 0.05) * self.params["speed"]
        self.clock += dt
        g = self.g

        # Wsp1 and Vrp1 arrive together, active on arrival.
        if g["wsp1"]:
            self.wsp1 = min(1.0, self.wsp1 + dt * 1.8)
        # SWIM shuts Wsp1 down and clears it from the patch.
        self.wsp1 = max(0.0, self.wsp1 - dt * 0.55 * max(0.0, self.t - 7.0))

        # Retention on the Myo1 tail, and Bbc1 competing it off.
        if not (g["myo1"] and g["myo1_sh3"]):
            self.retained = 0.0
        elif g["bbc1"] and self.t > T_BBC1:
            self.retained = max(0.0, self.retained - self.RELEASE * dt)

        # Freed proline-rich domains are captured by Sla1 -> SWIM complex.
        # "Inhibition after Movement": Sla1 only captures the freed proline-rich
        # domains once the patch has actually internalised some distance. Being
        # off the Myo1 tail is necessary but not sufficient.
        if g["sla1"]:
            moved = min(1.0, self.depth / self.D_MOVE)
            self.swim = min(1.0, self.swim + self.SWIM_RATE *
                            (1.0 - self.retained) * self.wsp1 * moved * dt)

        # Branched actin.
        assembly = 0.0
        if self.t >= T_ACTIN_ONSET:
            assembly = self.K_ASSEMBLY * self._npf() * self.params["arp"]
            if not g["cp"]:
                assembly *= 1.13
        decay = self.K_DECAY + 0.42 * max(0.0, self.t - 6.5)
        self.actin = max(0.0, self.actin + (assembly - decay * self.actin) * dt)
        self.peak_actin = max(self.peak_actin, self.actin)

        # Force -> internalisation, but only while the tubule is still being
        # pulled in. Once the neck constricts the geometry no longer applies.
        if self.phase == "growing":
            # Force saturates with actin: the load is carried by the filaments
            # oriented usefully against the membrane, not by the total polymer.
            # This is why sla1D, which never switches Wsp1 off and so keeps
            # building actin, still internalises a normal distance.
            a2 = self.actin * self.actin
            drive = a2 / (a2 + self.K_HALF * self.K_HALF)
            force = self.K_ACTIN * drive * self._positioning()
            if g["myo1"] and g["myo1_motor"]:
                force += self.K_MYO * min(1.0, self.actin / 0.55)
            # The tubule resists its own elongation: membrane tension and turgor
            # pull back in proportion to how far it has been drawn in.
            load = self.LOAD * self.depth * self.params["turgor"]
            self.depth = max(0.0, self.depth +
                             (force * self.jitter - load) * dt)
            self.max_depth = max(self.max_depth, self.depth)

            if len(self.trace) < 900:
                self.trace.append((self.t, self.actin, self.wsp1,
                                   self.retained, self.swim, self.depth))

            # Disassembly begins. Either the neck pinches off a vesicle, or the
            # invagination was never drawn in far enough and simply relaxes back.
            disassembling = (self.peak_actin > 0.12 and
                             self.actin < self.SCISSION_FRAC * self.peak_actin and
                             self.t > T_ACTIN_ONSET + 1.5)
            if disassembling or self.t > MAX_LIFETIME:
                if self.max_depth >= self.FAIL_BELOW:
                    # The BAR-domain collar constricts the neck.
                    self.phase = "pinching"
                else:
                    self.n_failed += 1
                    self.phase = "reseal"

        elif self.phase == "pinching":
            self.pinch = min(1.0, self.pinch + dt / self.PINCH_TIME)
            if self.pinch >= 1.0:
                self._scission()
        else:
            # Membrane reseals behind the departing vesicle, or the failed
            # invagination relaxes flat again.
            self.depth = max(0.0, self.depth - self.RESEAL * dt)

        # Released vesicles carry on into the cytoplasm.
        for v in self.free_vesicles:
            v["y"] += v["vy"] * dt
            v["x"] += v["vx"] * dt
            v["a"] -= 0.30 * dt
        self.free_vesicles = [v for v in self.free_vesicles
                              if v["a"] > 0.02 and v["y"] < self.h + 30]

        self.flash = max(0.0, self.flash - dt)
        self.t += dt

        if self.phase == "reseal" and self.depth <= 0.5:
            self._new_patch()

    def _scission(self):
        """The neck has closed; the vesicle leaves with its actin coat."""
        self.depths.append(self.max_depth)
        if len(self.depths) > 40:
            self.depths.pop(0)
        self.n_released += 1
        self.free_vesicles.append({
            "x": self.CX + random.uniform(-6.0, 6.0),
            "y": self.MEM_Y + self.depth / NM_PER_PX,
            "vy": random.uniform(26.0, 42.0),
            "vx": random.uniform(-10.0, 10.0),
            "a": 1.0,
        })
        self.phase = "reseal"
        self.flash = 0.9

    def _stats(self):
        total = self.n_released + self.n_failed
        mean = sum(self.depths) / len(self.depths) if self.depths else 0.0
        pct = (100.0 * self.n_released / total) if total else 100.0
        return mean, pct, total

    # ---- rendering -------------------------------------------------
    MEM_Y = 118.0
    CX = 262.0
    NECK = 26.0

    def _plot(self, shapes, x0, x1, y0, y1, series, ymax, title, refs=()):
        shapes.append({"t": "line", "x1": x0, "y1": y1, "x2": x1, "y2": y1,
                       "c": "dim", "w": 1.0, "a": 0.45})
        shapes.append({"t": "line", "x1": x0, "y1": y0, "x2": x0, "y2": y1,
                       "c": "dim", "w": 1.0, "a": 0.45})
        shapes.append({"t": "text", "x": x0, "y": y0 - 9, "s": title, "c": "dim"})

        for val, label in refs:
            yy = y1 - (val / ymax) * (y1 - y0)
            shapes.append({"t": "line", "x1": x0, "y1": yy, "x2": x1, "y2": yy,
                           "c": "dim", "w": 1.0, "a": 0.25})
            shapes.append({"t": "text", "x": x1 - 52, "y": yy - 4, "s": label, "c": "dim"})

        span = max(MAX_LIFETIME, 1.0)
        for idx, colour, label in series:
            pts = self.trace
            if len(pts) < 2:
                continue
            prev = None
            for p in pts:
                px = x0 + min(p[0] / span, 1.0) * (x1 - x0)
                py = y1 - min(p[idx] / ymax, 1.0) * (y1 - y0)
                if prev is not None:
                    shapes.append({"t": "line", "x1": prev[0], "y1": prev[1],
                                   "x2": px, "y2": py, "c": colour, "w": 1.6, "a": 0.9})
                prev = (px, py)
            if prev:
                shapes.append({"t": "text", "x": prev[0] + 5, "y": prev[1] + 4,
                               "s": label, "c": colour})

    def scene(self):
        shapes = []
        g = self.g
        cx, mem = self.CX, self.MEM_Y
        neck = self.NECK * (1.0 - 0.94 * self.pinch)
        tip = mem + self.depth / NM_PER_PX

        # Cell exterior above the plasma membrane.
        shapes.append({"t": "band", "y": 0.0, "h": mem, "c": "dim", "a": 0.07})

        # Plasma membrane, split around the neck of the invagination.
        shapes.append({"t": "line", "x1": 0, "y1": mem, "x2": cx - neck, "y2": mem,
                       "c": "accent2", "w": 2.4, "a": 0.9})
        shapes.append({"t": "line", "x1": cx + neck, "y1": mem, "x2": 545, "y2": mem,
                       "c": "accent2", "w": 2.4, "a": 0.9})

        # The tubule. Gone once the vesicle has pinched off.
        if self.depth > 2.0:
          shapes.append({"t": "curve", "x1": cx - neck, "y1": mem,
                       "cx": cx - neck * 0.5, "cy": tip, "x2": cx, "y2": tip,
                       "c": "accent2", "w": 2.4, "a": 0.9})
          shapes.append({"t": "curve", "x1": cx + neck, "y1": mem,
                       "cx": cx + neck * 0.5, "cy": tip, "x2": cx, "y2": tip,
                       "c": "accent2", "w": 2.4, "a": 0.9})

        # Hob1 and Hob3 wrap the tubule along its whole length, which is why
        # how much of them a patch accumulates reports the length of the
        # invagination (Ch. 2 used exactly this as the readout).
        if self.depth > 12.0:
            rungs = int(min(16, max(2, (tip - mem) / 13.0)))
            for i in range(rungs):
                f = (i + 0.5) / rungs
                y = mem + 6.0 + f * (tip - mem - 8.0)
                half = neck * (1.0 - 0.45 * f) + 3.0
                for side in (-1, 1):
                    shapes.append({"t": "dot", "x": cx + side * half, "y": y,
                                   "r": 2.6, "c": "cool", "a": 0.85})
            shapes.append({"t": "text", "x": cx + neck + 22,
                           "y": mem + (tip - mem) * 0.55,
                           "s": "Hob1 / Hob3", "c": "cool"})

        # Vesicles that have pinched off, heading into the cytoplasm with
        # their actin coat still on them.
        for v in self.free_vesicles:
            shapes.append({"t": "glow", "x": v["x"], "y": v["y"], "r": 34.0,
                           "c": "accent", "a": 0.10 * v["a"]})
            shapes.append({"t": "dot", "x": v["x"], "y": v["y"], "r": 14.0,
                           "c": "accent2", "a": 0.55 * v["a"]})
            shapes.append({"t": "dot", "x": v["x"], "y": v["y"], "r": 9.0,
                           "c": "accent2", "a": 0.30 * v["a"]})

        if self.flash > 0.0:
            shapes.append({"t": "text", "x": cx + neck + 16, "y": mem + 44,
                           "s": "scission", "c": "warm"})

        # Where Wsp1-Vrp1 currently sits: base while retained, tip once released.
        wy = mem + (1.0 - self.retained) * (tip - mem)

        # Branched actin around the active NPF.
        n = int(min(150, self.actin * 105))
        for i in range(n):
            a = (i * 2.39996) % 6.28318
            r = 12.0 + 30.0 * ((i / max(n, 1)) ** 0.5)
            jitter = math.sin(self.clock * 3.0 + i) * 1.8
            shapes.append({"t": "dot", "x": cx + math.cos(a) * r + jitter,
                           "y": wy + math.sin(a) * r * 0.8, "r": 1.9,
                           "c": "accent", "a": 0.55})
        if self.actin > 0.02:
            shapes.append({"t": "glow", "x": cx, "y": wy, "r": 62.0,
                           "c": "accent", "a": 0.13})

        # Myo1 stays at the base throughout.
        if g["myo1"]:
            for side in (-1, 1):
                shapes.append({"t": "dot", "x": cx + side * (neck + 5), "y": mem,
                               "r": 5.0, "c": "accent2", "a": 0.95})
            shapes.append({"t": "text", "x": cx + neck + 14, "y": mem - 8,
                           "s": "Myo1", "c": "accent2"})

        # Wsp1-Vrp1.
        if self.wsp1 > 0.03:
            shapes.append({"t": "dot", "x": cx, "y": wy, "r": 7.0,
                           "c": "accent", "a": 0.35 + 0.6 * self.wsp1})
            shapes.append({"t": "text", "x": cx + 14, "y": wy + 4,
                           "s": "Wsp1-Vrp1", "c": "accent"})

        # Bbc1 arrives at the base and competes them off.
        if g["bbc1"] and g["myo1"] and g["myo1_sh3"] and self.t > T_BBC1:
            shapes.append({"t": "dot", "x": cx - neck - 18, "y": mem + 9,
                           "r": 4.5, "c": "warm", "a": 0.9})
            shapes.append({"t": "text", "x": cx - neck - 66, "y": mem + 26,
                           "s": "Bbc1", "c": "warm"})

        # Sla1 capturing the freed PRDs: the SWIM complex.
        if self.swim > 0.05:
            shapes.append({"t": "dot", "x": cx, "y": wy, "r": 13.0,
                           "c": "warm", "a": 0.30 * self.swim})
            shapes.append({"t": "text", "x": cx - 74, "y": wy + 4,
                           "s": "SWIM", "c": "warm"})

        shapes.append({"t": "text", "x": 12, "y": mem - 10, "s": "outside", "c": "dim"})
        shapes.append({"t": "text", "x": 12, "y": mem + 20, "s": "cytoplasm", "c": "dim"})

        # Live traces, in the style of the thesis figures.
        self._plot(shapes, 592, 852, 70, 232,
                   [(1, "accent", "actin"), (2, "warm", "Wsp1"),
                    (3, "accent2", "at base"), (4, "dim", "SWIM")],
                   1.8, "patch intensity (A.U.)")
        self._plot(shapes, 592, 852, 300, 470,
                   [(5, "accent", "depth")], 1200.0,
                   "distance travelled (nm)",
                   refs=((500.0, "0.5 um  WT"), (1000.0, "1.0 um  bbc1")))

        mean, pct, total = self._stats()
        return {
            "shapes": shapes,
            "readout": [
                {"label": "Mean internalisation", "value": "%d nm" % round(mean)},
                {"label": "Vesicles released", "value": "%d of %d (%d%%)" % (self.n_released, total, round(pct))},
                {"label": "Hob1 (invagination)", "value": "%d%% of WT" % round(100.0 * mean / self.HOB1_REF)},
                {"label": "Peak actin", "value": "%.2f A.U." % self.peak_actin},
                {"label": "Wsp1 at base", "value": "%d%%" % round(self.retained * 100)},
            ],
            "status": "t = %.1f s in patch  -  %s" % (self.t, self.geno_key),
        }
