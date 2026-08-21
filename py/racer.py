"""
Rescuing Chlamydomonas motility: a race.

Built from "Rescuing Chlamydomonas motility in mutants modeling
spermatogenic failure" (Arcadia Science, 2024). Two Chlamydomonas
motility mutants stand in for human spermatogenic failure disorders:

  ida4    disrupts DNALI1  -> SPGF83. Loses the I-projections of the
          flagellar axoneme. Mean linear speed 44% below wild type,
          longest sprint 45% shorter.
  cpc1-1  disrupts SPEF2   -> SPGF43. Severely disorganised axonemes.
          Mean linear speed 56% below wild type, longest sprint 30%
          shorter.

Six compounds were screened at 50 uM. The point of the paper is that
rescue is mutation-specific: linsitinib improves cpc1-1 swimming and
makes ida4 worse. Torin2 is the only compound that helps both.

You race three lanes at once, which is how the experiment is actually
read: wild type as the benchmark, your mutant untreated as the control,
and your mutant plus drug. Beating your own untreated control is the
result that counts. Catching wild type is harder.

Speeds are shown as a percentage of wild type, because the publication
reports relative differences rather than absolute um/s.
"""

import math
import random

# Mean linear speed and longest sprint, as a fraction of wild type.
STRAINS = {
    "wt":     {"label": "CC-125 wild type", "speed": 1.00, "sprint": 1.00,
               "note": "The benchmark. Only ATP measurably increased its speed."},
    "ida4":   {"label": "CC-2670 ida4", "speed": 0.56, "sprint": 0.55,
               "note": "DNALI1 / SPGF83. Torin2 rescues it; ibudilast and linsitinib make it worse."},
    "cpc1":   {"label": "CC-3707 cpc1-1", "speed": 0.44, "sprint": 0.70,
               "note": "SPEF2 / SPGF43. Responds to almost everything, Torin2 most of all."},
}

# Multiplier applied to that strain's speed, per compound. 1.0 is no change.
DRUGS = {
    "dmso":        {"label": "0.1% DMSO (control)", "mech": "vehicle only",
                    "wt": 1.00, "ida4": 1.00, "cpc1": 1.00},
    "torin2":      {"label": "Torin2", "mech": "mTOR inhibitor",
                    "wt": 1.00, "ida4": 1.30, "cpc1": 1.45},
    "tak063":      {"label": "TAK-063", "mech": "PDE10A inhibitor",
                    "wt": 1.00, "ida4": 1.00, "cpc1": 1.20},
    "linsitinib":  {"label": "Linsitinib", "mech": "IGF-1R inhibitor",
                    "wt": 1.00, "ida4": 0.85, "cpc1": 1.30},
    "ibudilast":   {"label": "Ibudilast", "mech": "PDE inhibitor",
                    "wt": 1.00, "ida4": 0.78, "cpc1": 1.10},
    "dynarrestin": {"label": "Dynarrestin", "mech": "dynein inhibitor",
                    "wt": 1.00, "ida4": 1.00, "cpc1": 1.15},
    "atp":         {"label": "ATP", "mech": "energy substrate",
                    "wt": 1.12, "ida4": 1.00, "cpc1": 1.18},
}
DRUG_ORDER = ["dmso", "torin2", "tak063", "linsitinib", "ibudilast", "dynarrestin", "atp"]

START_X = 150.0
FINISH_X = 858.0
LANES = (150.0, 285.0, 420.0)
PACE = 46.0          # px/s at wild-type speed


class Racer:
    """One swimmer. Chlamydomonas swims in bursts, so speed is not steady."""

    def __init__(self, label, speed, sprint, colour):
        self.label = label
        self.speed = speed
        self.sprint = max(0.15, sprint)
        self.colour = colour
        self.reset()

    def reset(self):
        self.x = 0.0
        self.t_state = 0.0
        self.sprinting = True
        self.phase = random.uniform(0.0, 6.28)
        self.finished = None

    def step(self, dt, clock):
        if self.finished is not None:
            return
        self.t_state -= dt
        if self.t_state <= 0.0:
            self.sprinting = not self.sprinting
            self.t_state = (random.uniform(0.7, 1.5) * self.sprint
                            if self.sprinting else random.uniform(0.25, 0.6))
        v = self.speed * (1.0 if self.sprinting else 0.35)
        self.x += PACE * v * dt


class Sim:
    name = "Motility racer"
    blurb = "Pick a mutant and a drug, then race your own untreated control."
    cite = ("Bell A, Essock-Burns T, Hochstrasser ML, Lane R, MacQuarrie CD, Mets DG. "
            "Rescuing Chlamydomonas motility in mutants modeling spermatogenic failure. "
            "Arcadia Science (2024).")

    def __init__(self, width, height):
        self.w = float(width)
        self.h = float(height)
        self.strain_key = "cpc1"
        self.drug_key = "torin2"
        self.params = {"speed": 1.0}
        self.wins = 0
        self.races = 0
        self.reset()

    # ---- interface -------------------------------------------------
    def controls(self):
        return [
            {"id": "strain", "type": "select", "label": "Strain", "value": self.strain_key,
             "options": [{"value": k, "label": STRAINS[k]["label"], "hint": STRAINS[k]["note"]}
                         for k in ("wt", "ida4", "cpc1")]},
            {"id": "drug", "type": "select", "label": "Compound (50 \u00b5M)", "value": self.drug_key,
             "options": [{"value": k,
                          "label": DRUGS[k]["label"],
                          "hint": self._drug_hint(k)} for k in DRUG_ORDER]},
            {"id": "speed", "label": "Playback speed", "min": 0.25, "max": 3.0,
             "step": 0.05, "value": self.params["speed"],
             "hint": "How fast the race runs, not how fast the cells swim."},
        ]

    def _drug_hint(self, key):
        d = DRUGS[key]
        m = d[self.strain_key]
        if key == "dmso":
            return "%s. The untreated comparison." % d["mech"]
        if m > 1.02:
            verdict = "improves this strain (%+d%%)" % round((m - 1) * 100)
        elif m < 0.98:
            verdict = "makes this strain worse (%+d%%)" % round((m - 1) * 100)
        else:
            verdict = "no measurable effect on this strain"
        return "%s \u2014 %s." % (d["mech"], verdict)

    def set_param(self, key, value):
        if key in self.params:
            self.params[key] = float(value)

    def set_choice(self, key, value):
        if key == "strain" and value in STRAINS:
            self.strain_key = value
        elif key == "drug" and value in DRUGS:
            self.drug_key = value
        else:
            return
        self.reset()

    def set_pointer(self, x, y, down):
        pass

    def reset(self):
        s = STRAINS[self.strain_key]
        mult = DRUGS[self.drug_key][self.strain_key]
        self.wt = Racer("wild type", 1.00, 1.00, "dim")
        self.control = Racer("%s, untreated" % s["label"].split()[-1],
                             s["speed"], s["sprint"], "accent2")
        self.treated = Racer("%s + %s" % (s["label"].split()[-1], DRUGS[self.drug_key]["label"]),
                             s["speed"] * mult, s["sprint"], "accent")
        self.lanes = [self.wt, self.control, self.treated]
        self.clock = 0.0
        self.done_at = None
        self.result = ""
        self.mult = mult

    # ---- race ------------------------------------------------------
    def step(self, dt):
        dt = min(dt, 0.05) * self.params["speed"]
        self.clock += dt
        span = FINISH_X - START_X

        for r in self.lanes:
            r.step(dt, self.clock)
            if r.finished is None and r.x >= span:
                r.x = span
                r.finished = self.clock

        if self.done_at is None and all(r.finished is not None for r in self.lanes):
            self.done_at = self.clock
            self.races += 1
            beat_control = self.treated.finished < self.control.finished
            # A compound with no measured effect races its own control to a
            # coin flip, so report the published result rather than the toss.
            if abs(self.mult - 1.0) < 0.02:
                self.result = "no measured effect, as published"
            elif self.mult > 1.0:
                self.wins += 1
                self.result = ("caught wild type" if self.treated.finished <= self.wt.finished
                               else "rescued, still short of wild type")
            else:
                self.result = "worse than untreated"

        if self.done_at is not None and self.clock - self.done_at > 2.6:
            keep_w, keep_r = self.wins, self.races
            self.reset()
            self.wins, self.races = keep_w, keep_r

    # ---- rendering -------------------------------------------------
    def scene(self):
        shapes = []
        span = FINISH_X - START_X

        # Track: start and finish.
        for x, a in ((START_X, 0.35), (FINISH_X, 0.9)):
            shapes.append({"t": "line", "x1": x, "y1": 108, "x2": x, "y2": 462,
                           "c": "dim", "w": 1.6, "a": a})
        shapes.append({"t": "text", "x": FINISH_X - 34, "y": 96, "s": "finish", "c": "dim"})

        for i, r in enumerate(self.lanes):
            y = LANES[i]
            shapes.append({"t": "line", "x1": START_X, "y1": y, "x2": FINISH_X, "y2": y,
                           "c": "dim", "w": 1.0, "a": 0.16})
            shapes.append({"t": "text", "x": 14, "y": y - 14, "s": r.label, "c": r.colour})
            pct = round(r.speed * 100)
            shapes.append({"t": "text", "x": 14, "y": y + 4,
                           "s": "%d%% of WT speed" % pct, "c": "dim"})

            x = START_X + min(r.x, span)
            # Wake behind the cell.
            shapes.append({"t": "line", "x1": max(START_X, x - 34), "y1": y,
                           "x2": x - 9, "y2": y, "c": r.colour, "w": 1.2, "a": 0.28})
            # Two flagella, beating faster while sprinting.
            beat = math.sin(self.clock * (14.0 if r.sprinting else 5.0) + r.phase) * 6.0
            for s in (-1, 1):
                shapes.append({"t": "curve", "x1": x - 7, "y1": y + s * 3,
                               "cx": x - 19, "cy": y + s * 9 + beat * s,
                               "x2": x - 30, "y2": y + s * 4 + beat * s,
                               "c": r.colour, "w": 1.5, "a": 0.85})
            shapes.append({"t": "glow", "x": x, "y": y, "r": 20.0, "c": r.colour, "a": 0.16})
            shapes.append({"t": "dot", "x": x, "y": y, "r": 8.0, "c": r.colour, "a": 0.85})
            shapes.append({"t": "dot", "x": x + 3, "y": y - 2.5, "r": 2.4, "c": "accent2", "a": 0.7})

            if r.finished is not None:
                shapes.append({"t": "text", "x": x + 14, "y": y + 4,
                               "s": "%.1f s" % r.finished, "c": r.colour})

        if self.done_at is not None:
            shapes.append({"t": "band", "y": 488, "h": 34, "c": "accent", "a": 0.10})
            shapes.append({"t": "text", "x": 20, "y": 509, "s": self.result, "c": "accent"})

        pct = round(self.mult * 100)
        rows = [
            {"label": "Drug effect on this strain",
             "value": ("no change" if abs(self.mult - 1) < 0.02 else "%+d%%" % (pct - 100))},
            {"label": "Treated vs wild type",
             "value": "%d%% of WT" % round(self.treated.speed * 100)},
            {"label": "Rescues", "value": "%d of %d races" % (self.wins, self.races)},
        ]
        status = "racing\u2026" if self.done_at is None else self.result
        return {"shapes": shapes, "readout": rows,
                "status": "t = %.1f s  \u2014  %s" % (self.clock, status)}
