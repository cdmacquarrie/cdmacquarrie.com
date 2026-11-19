#!/usr/bin/env python3
"""Generate the summary-data SVG figures under figures/.

All charts use the theme-aware --viz-* CSS custom properties defined in
css/style.css and include visible value labels on every bar/cell so they
remain legible in both light and dark themes.
"""

from __future__ import annotations

import html
import os
from typing import Iterable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG_DIR = os.path.join(ROOT, "figures")
FONT = "Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif"


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def svg_wrap(width: int, height: int, body: Iterable[str]) -> str:
    inner = "\n".join(body)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="100%" font-family="{FONT}" role="img" class="viz">\n'
        f"{inner}\n"
        "</svg>\n"
    )


def x_grid(
    x0: float,
    scale: float,
    ticks: list[tuple[float, str]],
    y_top: float,
    y_bottom: float,
    y_label: float,
) -> list[str]:
    """Render subtle vertical gridlines, a stronger zero baseline, and tick labels."""
    out: list[str] = []
    for val, label in ticks:
        x = x0 + val * scale
        is_zero = val == 0
        stroke = "var(--viz-muted)" if is_zero else "var(--viz-grid)"
        extra = ' opacity="0.45"' if is_zero else ""
        out.append(
            f'<line x1="{x:.1f}" y1="{y_top:.1f}" x2="{x:.1f}" y2="{y_bottom:.1f}" '
            f'stroke="{stroke}" stroke-width="1"{extra}/>'
        )
        out.append(
            f'<text x="{x:.1f}" y="{y_label:.1f}" fill="var(--viz-muted)" '
            f'font-size="10" text-anchor="middle">{esc(label)}</text>'
        )
    return out


def build_spgf_deficits() -> str:
    x0 = 195.0
    scale = 5.0  # 60% -> 300px (x=495)
    groups = [
        (
            "ida4 (DNALI1 / SPGF83)",
            [
                ("mean linear speed", 44, "44% below WT", "var(--viz-1)"),
                ("longest sprint", 45, "45% below WT", "var(--viz-2)"),
            ],
        ),
        (
            "cpc1-1 (SPEF2 / SPGF43)",
            [
                ("mean linear speed", 56, "56% below WT", "var(--viz-1)"),
                ("longest sprint", 30, "30% below WT", "var(--viz-2)"),
            ],
        ),
    ]

    lines = x_grid(
        x0,
        scale,
        [(0, "0%"), (20, "20%"), (40, "40%"), (60, "60%")],
        y_top=12,
        y_bottom=102,
        y_label=114,
    )

    y = 16.0
    for name, bars in groups:
        lines.append(
            f'<text x="{x0 - 12:.0f}" y="{y + 16:.1f}" fill="var(--viz-muted)" '
            f'font-size="12" text-anchor="end">{esc(name)}</text>'
        )
        for metric, val, label, color in bars:
            w = val * scale
            tip = f"{name} {metric}: {label}"
            lines.append(
                f'<g><title>{esc(tip)}</title>'
                f'<rect x="{x0:.1f}" y="{y:.1f}" width="{w:.1f}" height="13" rx="4" fill="{color}"/>'
                f"</g>"
            )
            lines.append(
                f'<text x="{x0 + w + 8:.1f}" y="{y + 10.5:.1f}" fill="var(--viz-ink)" '
                f'font-size="11" font-weight="500">{esc(label)}</text>'
            )
            y += 17.0
        y += 12.0

    # Legend
    lines.extend(
        [
            f'<rect x="{x0:.0f}" y="127" width="10" height="10" rx="3" fill="var(--viz-1)"/>',
            f'<text x="{x0 + 16:.0f}" y="136" fill="var(--viz-muted)" font-size="11">mean linear speed</text>',
            f'<rect x="{x0 + 132:.0f}" y="127" width="10" height="10" rx="3" fill="var(--viz-2)"/>',
            f'<text x="{x0 + 148:.0f}" y="136" fill="var(--viz-muted)" font-size="11">longest sprint</text>',
        ]
    )
    return svg_wrap(620, 146, lines)


def build_spgf_drugs() -> str:
    cols = [("ida4", 147.0), ("cpc1-1", 376.5)]
    col_w = 225.5
    rows = [
        ("Torin2", ("recovered", "recovered")),
        ("TAK-063", ("no change", "recovered")),
        ("Linsitinib", ("worse", "recovered")),
        ("Ibudilast", ("worse", "recovered")),
        ("Dynarrestin", ("no change", "recovered")),
        ("ATP", ("no change", "recovered")),
    ]
    styles = {
        "recovered": ("var(--viz-1)", "#fff"),
        "no change": ("var(--viz-mid)", "var(--viz-on-mid)"),
        "worse": ("var(--viz-neg)", "#fff"),
    }

    lines: list[str] = []
    for col_name, cx in cols:
        lines.append(
            f'<text x="{cx + col_w / 2:.1f}" y="22" fill="var(--viz-ink)" '
            f'font-size="12" font-weight="600" text-anchor="middle">{esc(col_name)}</text>'
        )

    y = 34.0
    for drug, states in rows:
        lines.append(
            f'<text x="133" y="{y + 20:.1f}" fill="var(--viz-muted)" '
            f'font-size="12" text-anchor="end">{esc(drug)}</text>'
        )
        for (col_name, cx), state in zip(cols, states):
            bg, fg = styles[state]
            tip = f"{drug} on {col_name}: {state}"
            lines.append(
                f'<g><title>{esc(tip)}</title>'
                f'<rect x="{cx:.1f}" y="{y:.1f}" width="{col_w:.1f}" height="28" rx="5" fill="{bg}"/>'
                f'<text x="{cx + col_w / 2:.1f}" y="{y + 18.5:.1f}" fill="{fg}" '
                f'font-size="10.5" font-weight="600" text-anchor="middle">{esc(state)}</text></g>'
            )
        y += 34.0

    # Centered legend under the two columns (x=147..602, mid=374.5)
    legend = [
        ("recovered", "var(--viz-1)", 225.0),
        ("no change", "var(--viz-mid)", 327.0),
        ("worse", "var(--viz-neg)", 432.0),
    ]
    for label, fill, lx in legend:
        lines.append(f'<rect x="{lx:.1f}" y="245" width="10" height="10" rx="3" fill="{fill}"/>')
        lines.append(
            f'<text x="{lx + 16:.1f}" y="254" fill="var(--viz-muted)" font-size="11">{esc(label)}</text>'
        )

    return svg_wrap(620, 264, lines)


def build_protoplast_yield() -> str:
    x0 = 215.0
    scale = 5.0  # 60% -> 300px (x=515)
    bars = [
        ("(-)-Blebbistatin, trials 1-2", 50, "50% protoplasts", "var(--viz-4)", "~50% protoplast formation"),
        ("Alcalase 0.3-0.6 U/mL", 38, "38% protoplasts", "var(--viz-3)", "33-43% of cells formed protoplasts"),
        ("cytoskeletal drugs, later trials", 0, "0% protoplasts", "var(--viz-muted)", "0% on every replication attempt"),
    ]

    lines = x_grid(
        x0,
        scale,
        [(0, "0%"), (20, "20%"), (40, "40%"), (60, "60%")],
        y_top=10,
        y_bottom=96,
        y_label=109,
    )

    y = 14.0
    for label, val, val_text, color, tip in bars:
        w = max(2.5, val * scale)
        lines.append(
            f'<text x="{x0 - 12:.0f}" y="{y + 11:.1f}" fill="var(--viz-muted)" '
            f'font-size="12" text-anchor="end">{esc(label)}</text>'
        )
        lines.append(
            f'<g><title>{esc(tip)}</title>'
            f'<rect x="{x0:.1f}" y="{y:.1f}" width="{w:.1f}" height="15" rx="4" fill="{color}"/>'
            f"</g>"
        )
        lines.append(
            f'<text x="{x0 + w + 9:.1f}" y="{y + 11.5:.1f}" fill="var(--viz-ink)" '
            f'font-size="11.5" font-weight="500">{esc(val_text)}</text>'
        )
        y += 29.0

    return svg_wrap(620, 120, lines)


def build_vrp1_loss() -> str:
    x0 = 190.0
    scale = 6.0  # 50% -> 300px (x=490)
    bars = [
        ("patch actin", 38, 33, 43, "38% lower (33–43%)"),
        ("End4 internalisation", 34, 28, 40, "34% lower (28–40%)"),
        ("Hob1 accumulation", 27, 25, 29, "27% lower (25–29%)"),
    ]

    lines = x_grid(
        x0,
        scale,
        [(0, "0%"), (25, "25%"), (50, "50%")],
        y_top=10,
        y_bottom=96,
        y_label=109,
    )

    y = 14.0
    for label, mid, lo, hi, val_text in bars:
        w = mid * scale
        x_lo = x0 + lo * scale
        x_hi = x0 + hi * scale
        ymid = y + 7.5
        lines.append(
            f'<text x="{x0 - 12:.0f}" y="{y + 11:.1f}" fill="var(--viz-muted)" '
            f'font-size="12" text-anchor="end">{esc(label)}</text>'
        )
        lines.append(
            f'<g><title>{esc(f"Reduced {lo}-{hi}%")}</title>'
            f'<rect x="{x0:.1f}" y="{y:.1f}" width="{w:.1f}" height="15" rx="4" fill="var(--viz-3)"/>'
            f'<line x1="{x_lo:.1f}" y1="{ymid:.1f}" x2="{x_hi:.1f}" y2="{ymid:.1f}" '
            f'stroke="var(--viz-ink)" stroke-width="1.5" opacity="0.75"/>'
            f'<line x1="{x_lo:.1f}" y1="{ymid - 3.5:.1f}" x2="{x_lo:.1f}" y2="{ymid + 3.5:.1f}" '
            f'stroke="var(--viz-ink)" stroke-width="1.5" opacity="0.75"/>'
            f'<line x1="{x_hi:.1f}" y1="{ymid - 3.5:.1f}" x2="{x_hi:.1f}" y2="{ymid + 3.5:.1f}" '
            f'stroke="var(--viz-ink)" stroke-width="1.5" opacity="0.75"/>'
            f"</g>"
        )
        lines.append(
            f'<text x="{x_hi + 9:.1f}" y="{y + 11.5:.1f}" fill="var(--viz-ink)" '
            f'font-size="11.5" font-weight="500">{esc(val_text)}</text>'
        )
        y += 29.0

    return svg_wrap(620, 120, lines)


def build_bbc1_internalisation() -> str:
    x0 = 190.0
    scale = 250.0  # 1.2 µm -> 300px (x=490)
    rows = [
        ("wild type", 0.5, "0.5 µm", "var(--viz-muted)", "Reference: 0.5 um"),
        ("bbc1Δ", 1.0, "1.0 µm", "var(--viz-1)", "Twice wild type"),
        ("bbc1Δ sla1Δ", 1.0, "1.0 µm", "var(--viz-1)", "Still twice"),
        ("sla1Δ", 0.5, "0.5 µm", "var(--viz-muted)", "Unchanged - Sla1 terminates, it does not position"),
        ("bbc1Δ myo1-SH3-LCA", 0.5, "0.5 µm", "var(--viz-2)", "Rescue: removing Wsp1 retention cancels bbc1Δ"),
    ]

    lines = x_grid(
        x0,
        scale,
        [(0, "0"), (0.5, "0.5 µm"), (1.0, "1.0 µm")],
        y_top=16,
        y_bottom=162,
        y_label=175,
    )

    # Highlighted WT reference line at 0.5 µm
    wt_x = x0 + 0.5 * scale
    lines.append(
        f'<line x1="{wt_x:.1f}" y1="16" x2="{wt_x:.1f}" y2="162" '
        f'stroke="var(--viz-muted)" stroke-width="1" stroke-dasharray="3 3" opacity="0.7"/>'
    )
    lines.append(
        f'<text x="{wt_x:.1f}" y="11" fill="var(--viz-muted)" font-size="10" '
        f'text-anchor="middle">WT</text>'
    )

    y = 20.0
    for label, val, val_text, color, tip in rows:
        w = val * scale
        lines.append(
            f'<text x="{x0 - 12:.0f}" y="{y + 11:.1f}" fill="var(--viz-muted)" '
            f'font-size="12" text-anchor="end">{esc(label)}</text>'
        )
        lines.append(
            f'<g><title>{esc(tip)}</title>'
            f'<rect x="{x0:.1f}" y="{y:.1f}" width="{w:.1f}" height="15" rx="4" fill="{color}"/>'
            f"</g>"
        )
        lines.append(
            f'<text x="{x0 + w + 9:.1f}" y="{y + 11.5:.1f}" fill="var(--viz-ink)" '
            f'font-size="11.5" font-weight="500">{esc(val_text)}</text>'
        )
        y += 29.0

    return svg_wrap(620, 186, lines)


FIGURES = {
    "spgf-deficits.svg": build_spgf_deficits,
    "spgf-drugs.svg": build_spgf_drugs,
    "protoplast-yield.svg": build_protoplast_yield,
    "vrp1-loss.svg": build_vrp1_loss,
    "bbc1-internalisation.svg": build_bbc1_internalisation,
}


def main() -> None:
    os.makedirs(FIG_DIR, exist_ok=True)
    for filename, builder in FIGURES.items():
        path = os.path.join(FIG_DIR, filename)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(builder())
        print(f"wrote {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    main()
