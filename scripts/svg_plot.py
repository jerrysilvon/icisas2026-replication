"""Minimal publication-quality SVG plotting, pure Python.

matplotlib cannot load on this machine: Windows Application Control blocks its
compiled _backend_agg extension, and pyplot imports that unconditionally, so
every backend fails. This module writes SVG directly.

Vector SVG is the right output for IEEE anyway. Units are PostScript points
(1 in = 72 pt), so a figure declared 3.46 in wide is exactly one IEEE column.
"""
import math
from html import escape
from pathlib import Path

PT = 72.0
SERIF = "Times New Roman, Times, DejaVu Serif, serif"


def nice_ticks(lo, hi, target=5):
    """Ticks at 1/2/2.5/5 x 10^k covering [lo, hi]."""
    if hi <= lo:
        hi = lo + 1.0
    raw = (hi - lo) / max(target, 1)
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1.0
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            step = m * mag
            break
    else:
        step = 10 * mag
    start = math.floor(lo / step) * step
    out, v = [], start
    while v <= hi + step * 1e-9:
        if v >= lo - step * 1e-9:
            out.append(round(v, 12))
        v += step
    return out


def fmt(v):
    if v == 0:
        return "0"
    if abs(v - round(v)) < 1e-9 and abs(v) < 1e6:
        return f"{int(round(v))}"
    a = abs(v)
    if a >= 1000 or a < 0.001:
        return f"{v:.0e}".replace("e-0", "e-").replace("e+0", "e")
    if a >= 100:
        return f"{v:.0f}"
    if a >= 10:
        return f"{v:.0f}" if abs(v - round(v)) < 1e-9 else f"{v:.1f}"
    if a >= 1:
        return f"{v:.1f}" if abs(v * 10 - round(v * 10)) < 1e-9 else f"{v:.2f}"
    return f"{v:.3f}".rstrip("0").rstrip(".")


_AXES_SEQ = [0]


class Axes:
    def __init__(self, fig, x0, y0, w, h):
        self.f, self.x0, self.y0, self.w, self.h = fig, x0, y0, w, h
        _AXES_SEQ[0] += 1
        self.uid = f"clip{_AXES_SEQ[0]}"
        self.items, self.legend_items = [], []
        self.xlim = self.ylim = None
        self.xlabel = self.ylabel = self.title = None
        self.xticks = self.yticks = None
        self._xdata, self._ydata = [], []
        self.grid_axis = None
        self.ytick_labels = None
        self.xtick_labels = None
        self.legend_loc = "upper left"

    # ---- data registration
    def _reg(self, xs, ys):
        self._xdata += [v for v in xs if v is not None and math.isfinite(v)]
        self._ydata += [v for v in ys if v is not None and math.isfinite(v)]

    def _lims(self):
        if self.xlim is None:
            lo, hi = (min(self._xdata), max(self._xdata)) if self._xdata else (0, 1)
            pad = (hi - lo) * .05 or .5
            self.xlim = (lo - pad, hi + pad)
        if self.ylim is None:
            lo, hi = (min(self._ydata), max(self._ydata)) if self._ydata else (0, 1)
            pad = (hi - lo) * .08 or .5
            self.ylim = (lo - pad, hi + pad)
        return self.xlim, self.ylim

    def px(self, x):
        (a, b), _ = self._lims()
        return self.x0 + (x - a) / (b - a) * self.w

    def py(self, y):
        _, (a, b) = self._lims()
        return self.y0 + self.h - (y - a) / (b - a) * self.h

    # ---- plotting
    def plot(self, xs, ys, color="#0b6fa4", lw=1.0, dash=None, marker=None,
             ms=3.0, label=None):
        self._reg(xs, ys)
        self.items.append(("plot", xs, ys, color, lw, dash, marker, ms))
        if label:
            self.legend_items.append((label, color, marker or "line", dash))

    def hist(self, values, bins=30, color="#0b6fa4", alpha=.85):
        vals = [v for v in values if v is not None and math.isfinite(v)]
        lo, hi = min(vals), max(vals)
        if hi <= lo:
            hi = lo + 1
        w = (hi - lo) / bins
        counts = [0] * bins
        for v in vals:
            i = min(int((v - lo) / w), bins - 1)
            counts[i] += 1
        self._reg([lo, hi], [0, max(counts)])
        self.ylim = (0, max(counts) * 1.12)
        self.items.append(("hist", lo, w, counts, color, alpha))
        return counts

    def errorbar(self, x, y, xerr, color="#0b6fa4", marker="o", ms=4, label=None):
        self._reg([x - xerr, x + xerr], [y])
        self.items.append(("errorbar", x, y, xerr, color, marker, ms))
        if label:
            self.legend_items.append((label, color, marker, None))

    def axvline(self, x, color="#1a1a1a", lw=.8, dash="3,2"):
        self._reg([x], [])
        self.items.append(("vline", x, color, lw, dash))

    def axhline(self, y, color="#1a1a1a", lw=.8, dash=None):
        self._reg([], [y])
        self.items.append(("hline", y, color, lw, dash))

    def annotate(self, text, x, y, dx=4, dy=-3, size=7, color="#1a1a1a", anchor="start"):
        self.items.append(("text", x, y, dx, dy, text, size, color, anchor))

    # ---- rendering
    def render(self):
        (xa, xb), (ya, yb) = self._lims()
        o = []
        xt = self.xticks if self.xticks is not None else nice_ticks(xa, xb)
        yt = self.yticks if self.yticks is not None else nice_ticks(ya, yb)
        # grid
        if self.grid_axis in ("y", "both"):
            for t in yt:
                if ya <= t <= yb:
                    o.append(f'<line x1="{self.x0:.1f}" y1="{self.py(t):.1f}" '
                             f'x2="{self.x0+self.w:.1f}" y2="{self.py(t):.1f}" '
                             f'stroke="#9aa0a6" stroke-width="0.4" opacity="0.35"/>')
        if self.grid_axis in ("x", "both"):
            for t in xt:
                if xa <= t <= xb:
                    o.append(f'<line x1="{self.px(t):.1f}" y1="{self.y0:.1f}" '
                             f'x2="{self.px(t):.1f}" y2="{self.y0+self.h:.1f}" '
                             f'stroke="#9aa0a6" stroke-width="0.4" opacity="0.35"/>')
        o.append(f'<clipPath id="{self.uid}"><rect x="{self.x0:.1f}" '
                 f'y="{self.y0:.1f}" width="{self.w:.1f}" height="{self.h:.1f}"/>'
                 f'</clipPath>')
        o.append(f'<g clip-path="url(#{self.uid})">')
        for it in self.items:
            o.append(self._render_item(it))
        o.append('</g>')
        # axis spines (left + bottom only)
        o.append(f'<line x1="{self.x0:.1f}" y1="{self.y0+self.h:.1f}" '
                 f'x2="{self.x0+self.w:.1f}" y2="{self.y0+self.h:.1f}" '
                 f'stroke="#1a1a1a" stroke-width="0.6"/>')
        o.append(f'<line x1="{self.x0:.1f}" y1="{self.y0:.1f}" '
                 f'x2="{self.x0:.1f}" y2="{self.y0+self.h:.1f}" '
                 f'stroke="#1a1a1a" stroke-width="0.6"/>')
        for t in xt:
            if not (xa <= t <= xb):
                continue
            X = self.px(t)
            o.append(f'<line x1="{X:.1f}" y1="{self.y0+self.h:.1f}" x2="{X:.1f}" '
                     f'y2="{self.y0+self.h+2.5:.1f}" stroke="#1a1a1a" stroke-width="0.6"/>')
            xl = (self.xtick_labels[xt.index(t)]
                  if self.xtick_labels and t in xt and xt.index(t) < len(self.xtick_labels)
                  else fmt(t))
            o.append(f'<text x="{X:.1f}" y="{self.y0+self.h+10:.1f}" font-size="7" '
                     f'text-anchor="middle" font-family="{SERIF}" '
                     f'fill="#1a1a1a">{escape(str(xl))}</text>')
        labels = self.ytick_labels
        for i, t in enumerate(yt):
            if not (ya <= t <= yb):
                continue
            Y = self.py(t)
            lab = labels[i] if labels and i < len(labels) else fmt(t)
            o.append(f'<line x1="{self.x0-2.5:.1f}" y1="{Y:.1f}" x2="{self.x0:.1f}" '
                     f'y2="{Y:.1f}" stroke="#1a1a1a" stroke-width="0.6"/>')
            for k, part in enumerate(str(lab).split("\n")):
                o.append(f'<text x="{self.x0-5:.1f}" y="{Y+2.4+k*7.4:.1f}" font-size="7" '
                         f'text-anchor="end" font-family="{SERIF}" fill="#1a1a1a">{escape(part)}</text>')
        if self.xlabel:
            o.append(f'<text x="{self.x0+self.w/2:.1f}" y="{self.y0+self.h+21:.1f}" '
                     f'font-size="8" text-anchor="middle" font-family="{SERIF}" '
                     f'fill="#1a1a1a">{escape(self.xlabel)}</text>')
        if self.ylabel:
            cx, cy = self.x0 - 30, self.y0 + self.h / 2
            o.append(f'<text transform="rotate(-90 {cx:.1f} {cy:.1f})" x="{cx:.1f}" '
                     f'y="{cy:.1f}" font-size="8" text-anchor="middle" '
                     f'font-family="{SERIF}" fill="#1a1a1a">{escape(self.ylabel)}</text>')
        if self.title:
            o.append(f'<text x="{self.x0:.1f}" y="{self.y0-6:.1f}" font-size="8" '
                     f'font-weight="bold" font-family="{SERIF}" fill="#1a1a1a">'
                     f'{escape(self.title)}</text>')
        o.append(self._render_legend())
        return "\n".join(x for x in o if x)

    def _marker(self, X, Y, marker, color, ms):
        if marker == "s":
            return (f'<rect x="{X-ms/2:.1f}" y="{Y-ms/2:.1f}" width="{ms:.1f}" '
                    f'height="{ms:.1f}" fill="{color}"/>')
        if marker == "^":
            return (f'<polygon points="{X:.1f},{Y-ms/1.6:.1f} {X-ms/1.7:.1f},'
                    f'{Y+ms/2.4:.1f} {X+ms/1.7:.1f},{Y+ms/2.4:.1f}" fill="{color}"/>')
        return f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="{ms/2:.1f}" fill="{color}"/>'

    def _render_item(self, it):
        k = it[0]
        if k == "plot":
            _, xs, ys, color, lw, dash, marker, ms = it
            pts = " ".join(f"{self.px(x):.1f},{self.py(y):.1f}"
                           for x, y in zip(xs, ys)
                           if x is not None and y is not None
                           and math.isfinite(x) and math.isfinite(y))
            o = ""
            if lw and len(xs) > 1:
                d = f' stroke-dasharray="{dash}"' if dash else ""
                o += (f'<polyline points="{pts}" fill="none" stroke="{color}" '
                      f'stroke-width="{lw}"{d} stroke-linejoin="round"/>')
            if marker:
                for x, y in zip(xs, ys):
                    if x is None or y is None or not (math.isfinite(x) and math.isfinite(y)):
                        continue
                    o += self._marker(self.px(x), self.py(y), marker, color, ms)
            return o
        if k == "hist":
            _, lo, w, counts, color, alpha = it
            o = ""
            for i, c in enumerate(counts):
                if c <= 0:
                    continue
                X0, X1 = self.px(lo + i * w), self.px(lo + (i + 1) * w)
                Y0, Y1 = self.py(c), self.py(0)
                o += (f'<rect x="{X0:.1f}" y="{Y0:.1f}" width="{max(X1-X0-0.4,0.3):.1f}" '
                      f'height="{max(Y1-Y0,0):.1f}" fill="{color}" opacity="{alpha}"/>')
            return o
        if k == "errorbar":
            _, x, y, xe, color, marker, ms = it
            X0, X1, Y = self.px(x - xe), self.px(x + xe), self.py(y)
            o = (f'<line x1="{X0:.1f}" y1="{Y:.1f}" x2="{X1:.1f}" y2="{Y:.1f}" '
                 f'stroke="{color}" stroke-width="0.9"/>')
            for XX in (X0, X1):
                o += (f'<line x1="{XX:.1f}" y1="{Y-2.2:.1f}" x2="{XX:.1f}" '
                      f'y2="{Y+2.2:.1f}" stroke="{color}" stroke-width="0.9"/>')
            return o + self._marker(self.px(x), Y, marker, color, ms)
        if k == "vline":
            _, x, color, lw, dash = it
            d = f' stroke-dasharray="{dash}"' if dash else ""
            return (f'<line x1="{self.px(x):.1f}" y1="{self.y0:.1f}" x2="{self.px(x):.1f}" '
                    f'y2="{self.y0+self.h:.1f}" stroke="{color}" stroke-width="{lw}"{d}/>')
        if k == "hline":
            _, y, color, lw, dash = it
            d = f' stroke-dasharray="{dash}"' if dash else ""
            return (f'<line x1="{self.x0:.1f}" y1="{self.py(y):.1f}" '
                    f'x2="{self.x0+self.w:.1f}" y2="{self.py(y):.1f}" '
                    f'stroke="{color}" stroke-width="{lw}"{d}/>')
        if k == "text":
            _, x, y, dx, dy, text, size, color, anchor = it
            return (f'<text x="{self.px(x)+dx:.1f}" y="{self.py(y)+dy:.1f}" '
                    f'font-size="{size}" text-anchor="{anchor}" font-family="{SERIF}" '
                    f'fill="{color}">{escape(text)}</text>')
        return ""

    def _render_legend(self):
        if not self.legend_items:
            return ""
        n = len(self.legend_items)
        wide = max(len(l) for l, *_ in self.legend_items) * 3.35 + 20
        if self.legend_loc == "lower left":
            x, y = self.x0 + 6, self.y0 + self.h - 9.5 * n
        elif self.legend_loc == "lower right":
            x, y = self.x0 + self.w - wide, self.y0 + self.h - 9.5 * n
        elif self.legend_loc == "upper right":
            x, y = self.x0 + self.w - wide, self.y0 + 9
        else:
            x, y = self.x0 + 6, self.y0 + 9
        o = []
        for lab, color, marker, dash in self.legend_items:
            if marker in ("line", None):
                d = f' stroke-dasharray="{dash}"' if dash else ""
                o.append(f'<line x1="{x:.1f}" y1="{y-2:.1f}" x2="{x+11:.1f}" '
                         f'y2="{y-2:.1f}" stroke="{color}" stroke-width="1.1"{d}/>')
            else:
                o.append(self._marker(x + 5.5, y - 2, marker, color, 4))
            o.append(f'<text x="{x+15:.1f}" y="{y:.1f}" font-size="6.8" '
                     f'font-family="{SERIF}" fill="#1a1a1a">{escape(lab)}</text>')
            y += 9.5
        return "\n".join(o)


class Fig:
    def __init__(self, w_in, h_in):
        self.W, self.H = w_in * PT, h_in * PT
        self.axes_list, self.texts = [], []

    def add_axes(self, left, bottom, width, height):
        """Fractions of figure size, matplotlib-style (bottom-left origin)."""
        x0 = left * self.W
        w, h = width * self.W, height * self.H
        y0 = self.H - (bottom * self.H) - h
        a = Axes(self, x0, y0, w, h)
        self.axes_list.append(a)
        return a

    def text(self, x, y, s, size=8, weight="normal", anchor="start"):
        self.texts.append((x * self.W, y * self.H, s, size, weight, anchor))

    def save(self, path):
        body = "\n".join(a.render() for a in self.axes_list)
        for x, y, s, size, weight, anchor in self.texts:
            body += (f'\n<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" '
                     f'font-weight="{weight}" text-anchor="{anchor}" '
                     f'font-family="{SERIF}" fill="#1a1a1a">{escape(s)}</text>')
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.W:.1f}pt" '
               f'height="{self.H:.1f}pt" viewBox="0 0 {self.W:.1f} {self.H:.1f}">\n'
               f'<rect width="100%" height="100%" fill="white"/>\n{body}\n</svg>\n')
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(svg, encoding="utf-8")
        return p
