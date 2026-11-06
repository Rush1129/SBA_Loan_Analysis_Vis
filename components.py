"""Reusable layout pieces: KPI tiles, chart cards, page headers, keys, number formatting.

Every page is built from these so the look stays consistent (see DESIGN.md)."""
from urllib.parse import quote

import numpy as np
from dash import dcc, html

from theme import GRAPH_CONFIG, INK, RISK


def money(v: float) -> str:
    v = float(v)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(v) >= div:
            return f"${v / div:,.1f}{suf}"
    return f"${v:,.0f}"


def num(v: float) -> str:
    return f"{v:,.0f}"


def pct(v: float, d: int = 1) -> str:
    return f"{v:.{d}%}"


def times(v: float) -> str:
    return f"{v:.1f}×"


# ---- KPI tiles ----------------------------------------------------------------

def kpi(label, value, sub=None, tone=None, foot=None):
    """A stat tile. ``tone`` ∈ {None, 'safe', 'risk', 'money', 'count'} sets the label dot
    (and colours the value for risk/safe). ``foot`` is an optional mini visual pinned to the
    bottom of the tile: ``splitbar``, ``meter`` or ``spark``."""
    return html.Div(
        className=f"kpi {('kpi-' + tone) if tone else ''}",
        children=[
            html.Div(label, className="kpi-label"),
            html.Div(value, className="kpi-value"),
            html.Div(sub, className="kpi-sub") if sub is not None else None,
            html.Div(foot, className="kpi-foot") if foot is not None else None,
        ],
    )


def splitbar(parts):
    """Proportion bar, e.g. [(0.785, 'safe'), (0.215, 'risk')]. Tones map to .fill-* classes."""
    return html.Div(className="splitbar", children=[
        html.Span(className=f"fill-{tone}", style={"width": f"{share * 100:.2f}%"}) for share, tone in parts
    ])


def meter(share, tone="risk"):
    """Share of a whole on a light track (0..1)."""
    return html.Div(className="meter", children=html.Span(className=f"fill-{tone}",
                                                          style={"width": f"{min(max(share, 0), 1) * 100:.2f}%"}))


def spark(values, color=RISK, kind="line"):
    """Tiny inline SVG trend for a KPI tile: a line with the house faded fill, or mini bars."""
    v = np.nan_to_num(np.asarray(values, dtype=float))
    n, top = len(v), (np.max(v) if len(v) and np.max(v) > 0 else 1.0)
    w, h = 280, 48
    if n == 0:
        body = ""
    elif kind == "bars":
        bw = w / n
        body = "".join(f"<rect x='{i * bw + 0.6:.1f}' y='{h - val / top * h:.1f}' width='{bw - 1.6:.1f}' "
                       f"height='{val / top * h:.1f}' rx='1.5' fill='{color}'/>" for i, val in enumerate(v))
    else:
        pts = [(i / max(n - 1, 1) * w, h - 2 - val / top * (h - 6)) for i, val in enumerate(v)]
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        body = (f"<defs><linearGradient id='g' x1='0' y1='0' x2='0' y2='1'>"
                f"<stop offset='0' stop-color='{color}' stop-opacity='0.24'/>"
                f"<stop offset='1' stop-color='{color}' stop-opacity='0'/></linearGradient></defs>"
                f"<path d='{d} L{w},{h} L0,{h} Z' fill='url(#g)'/>"
                f"<path d='{d}' fill='none' stroke='{color}' stroke-width='1.8' vector-effect='non-scaling-stroke' "
                f"stroke-linejoin='round' stroke-linecap='round'/>")
    svg = f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' preserveAspectRatio='none'>{body}</svg>"
    return html.Img(src="data:image/svg+xml;utf8," + quote(svg, safe=""), className="spark", alt="")


# ---- cards ------------------------------------------------------------------------

def chart_card(gid, title, subtitle=None, height=360, controls=None, className="", note=None):
    """A card around one graph. The title is an insight headline; callbacks may rewrite it
    through the ``{gid}-title`` element."""
    return html.Div(
        className=f"card {className}",
        children=[
            html.Div(
                className="card-head",
                children=[
                    html.Div([html.H3(title, id=f"{gid}-title"),
                              html.P(subtitle, id=f"{gid}-sub") if subtitle else None]),
                    html.Div(controls, className="card-controls") if controls is not None else None,
                ],
            ),
            dcc.Loading(
                dcc.Graph(id=gid, config=GRAPH_CONFIG, style={"height": f"{height}px"}),
                type="dot", color=INK, delay_show=250,
                overlay_style={"visibility": "visible", "opacity": 0.45},
            ),
            html.P(note, className="card-note") if note else None,
        ],
    )


def page_header(kicker, title, lede, right=None):
    return html.Div(
        className="page-header",
        children=[
            html.Div([
                html.Div(kicker, className="kicker"),
                html.H1(title),
                html.P(lede, className="lede"),
            ]),
            html.Div(right, className="page-header-right") if right is not None else None,
        ],
    )


def legend_keys(items, line=False):
    """Inline colour key, e.g. [("Paid in full", "safe"), ("Charged off", "risk")].
    ``line=True`` draws line swatches for line charts."""
    return html.Div(className="keys keys-line" if line else "keys", children=[
        html.Span(className="key", children=[html.Span(className=f"key-sw key-{tone}"), label])
        for label, tone in items
    ])


def scale_key(lo="Safer", hi="Riskier"):
    """Key for anything coloured on the diverging risk scale."""
    return html.Span(className="scale-key", children=[lo, html.I(), hi])


def insight(children, tone="info"):
    """Insight card: icon tile + bold lead + one plain sentence. tone ∈ {info, warn, safe}."""
    return html.Div(className=f"insight insight-{tone}", children=[
        html.Span(className="insight-ico", **{"aria-hidden": "true"}),
        html.Div(children, className="insight-body"),
    ])


def section(title, sub=None):
    return html.Div(className="section-title", children=[html.H2(title), html.P(sub) if sub else None])


def seg(id_, options, value):
    """Segmented control (styled RadioItems)."""
    return dcc.RadioItems(
        id=id_, options=options, value=value, inline=True,
        className="seg", inputClassName="seg-input", labelClassName="seg-label",
    )
