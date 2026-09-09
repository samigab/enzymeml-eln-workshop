"""Unit rendering, CSV and plotting helpers shared by both converters.

Both schemas model units the same way: a ``UnitDefinition`` with a ``name`` and
a list of ``BaseUnit`` (kind, exponent, multiplier, scale). We prefer the
human ``name`` when present and fall back to composing a symbolic label.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Iterable, Optional, Sequence

from .crate import fmt

# SI base-unit kinds → symbol. Covers the enumerations used by both schemas;
# unknown kinds fall through to the kind name itself.
_SYMBOL = {
    "ampere": "A", "amount_of_substance": "mol", "becquerel": "Bq", "candela": "cd",
    "celsius": "°C", "coulomb": "C", "dimensionless": "1", "farad": "F",
    "gram": "g", "gray": "Gy", "henry": "H", "hertz": "Hz", "item": "item",
    "joule": "J", "katal": "kat", "kelvin": "K", "kilogram": "kg", "length": "m",
    "litre": "l", "liter": "l", "lumen": "lm", "lux": "lx", "mass": "kg",
    "metre": "m", "meter": "m", "mole": "mol", "newton": "N", "ohm": "Ω",
    "pascal": "Pa", "radian": "rad", "second": "s", "siemens": "S",
    "sievert": "Sv", "steradian": "sr", "temperature": "K", "tesla": "T",
    "time": "s", "volt": "V", "watt": "W", "weber": "Wb",
    "amount": "mol", "current": "A", "luminosity": "cd", "substance": "mol",
}

# decimal scale exponent → SI prefix
_PREFIX = {24: "Y", 21: "Z", 18: "E", 15: "P", 12: "T", 9: "G", 6: "M", 3: "k",
           2: "h", 1: "da", 0: "", -1: "d", -2: "c", -3: "m", -6: "µ", -9: "n",
           -12: "p", -15: "f", -18: "a", -21: "z", -24: "y"}


def _base_unit_label(bu: dict) -> str:
    kind = (bu.get("kind") or "").strip()
    sym = _SYMBOL.get(kind.lower(), kind)
    scale = bu.get("scale")
    if scale not in (None, 0):
        try:
            sym = _PREFIX.get(int(scale), f"10^{int(scale)}·") + sym
        except (TypeError, ValueError):
            pass
    exp = bu.get("exponent")
    if exp not in (None, 1):
        sym += f"^{exp}"
    return sym


def unit_label(unit: Any) -> str:
    """Human/UCUM-ish label for a UnitDefinition dict. '' when unknown."""
    if not isinstance(unit, dict):
        return str(unit or "")
    name = unit.get("name")
    if name:
        return str(name)
    parts = [_base_unit_label(bu) for bu in unit.get("base_units") or []]
    return "·".join(p for p in parts if p)


def csv_bytes(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> bytes:
    """UTF-8 CSV with a BOM so Excel opens it correctly."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    for row in rows:
        w.writerow(["" if c is None else fmt(c) for c in row])
    return buf.getvalue().encode("utf-8-sig")


def plot_png(series: Sequence[tuple[str, Sequence[float], Sequence[float]]],
             *, xlabel: str, ylabel: str, title: str,
             scatter: bool = True) -> Optional[bytes]:
    """Render one or more (label, xs, ys) series to PNG bytes.

    Plotting is best-effort enrichment: any failure (matplotlib missing, bad
    data) returns None rather than aborting the export.
    """
    usable = [(lbl, xs, ys) for lbl, xs, ys in series
              if xs and ys and len(xs) == len(ys)]
    if not usable:
        return None
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(6, 4))
        for label, xs, ys in usable:
            order = sorted(range(len(xs)), key=lambda i: xs[i])
            sx = [xs[i] for i in order]
            sy = [ys[i] for i in order]
            if scatter:
                ax.plot(sx, sy, "o-", markersize=4, linewidth=1, label=label)
            else:
                ax.plot(sx, sy, linewidth=1.2, label=label)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.3)
        if len(usable) > 1:
            ax.legend(fontsize=7)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
        plt.close(fig)
        return buf.getvalue()
    except Exception:
        return None
