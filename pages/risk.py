"""Risk Explorer — combine the five strongest application-time drivers and read how
similar loans performed historically."""
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, callback, ctx, dcc, html

import data as D
from components import chart_card, kpi, legend_keys, num, page_header, pct
from theme import (INK, MUTED, NEUTRAL, RISK, RISK_INK, SAFE, TEXT, empty_fig, line_area, risk_colors,
                   style_timeseries)

ANY = "__any__"
MONTHS = np.arange(0, 121, 3)  # failure-timing curve: 0–10 years after disbursement

# field id → (column, label, options); order = strength of the driver (see Risk Drivers page)
FIELDS = {
    "era": ("Era", "Approval era", [{"label": f"{e} · {D.ERA_NOTES[e]}", "value": e} for e in D.ERA_LABELS]),
    "lender": ("Lender", "Lender", [{"label": l, "value": l} for l in D.LENDERS]),
    "guar": ("GuarBand", "SBA guarantee share", [{"label": g, "value": g} for g in D.GUAR_LABELS]),
    "state": ("State", "Borrower state", [{"label": f"{D.STATE_NAMES[s]} ({s})", "value": s} for s in D.STATES]),
    "size": ("SizeBand", "Loan amount", [{"label": s, "value": s} for s in D.SIZE_LABELS]),
}
COL_TO_FIELD = {c: f for f, (c, _, _) in FIELDS.items()}

PRESETS = {
    "boom": dict(era="2005–08", guar="≤ 50%", size="≤ $50k"),
    "safe": dict(era="1991–2001", guar="80–84%", size="$250k–500k"),
    "lender": dict(era="2005–08", lender="Capital One"),
}


def _iv_lookup():
    dv = D.drivers(D.DEFAULT_FILTERS).set_index("col")
    return {f: float(dv.loc[c, "score"]) for f, (c, _, _) in FIELDS.items()}


def _control(fid, iv):
    col, label, options = FIELDS[fid]
    strength = D.iv_strength(iv)
    return html.Div(className="field", children=[
        html.Div(className="field-row", children=[
            html.Label(label, className="field-label"),
            html.Span(f"IV {iv:.2f} · {strength}", className=f"iv-chip iv-{strength.split()[-1].lower()}"),
        ]),
        dcc.Dropdown(id=f"rk-{fid}", options=[{"label": "Any", "value": ANY}] + options,
                     value=PRESETS["boom"].get(fid, ANY),
                     clearable=False, className="dd"),
    ])


def layout():
    ivs = _iv_lookup()
    return html.Div([
        page_header("Historical risk explorer", "How did loans like this one turn out?",
                    "Pick values for the five drivers that best separated failed from repaid loans and were known when "
                    "the loan was approved. The page shows what happened to every matching loan. It describes the past; "
                    "it is not a credit model."),
        html.Div(className="risk-layout", children=[
            html.Div(className="card profile-panel", children=[
                html.Div(className="card-head", children=[html.Div([
                    html.H3("Loan profile"),
                    html.P("Ranked by Information Value, a like-for-like measure of how well each one separated "
                           "failed loans from repaid ones."),
                ])]),
                html.Div(className="preset-row", children=[
                    html.Button("Boom-era SBAExpress", id="rk-p-boom", className="chip-btn"),
                    html.Button("Mid-size 1990s 7(a) loan", id="rk-p-safe", className="chip-btn"),
                    html.Button("Capital One, 2005–08", id="rk-p-lender", className="chip-btn"),
                    html.Button("Clear", id="rk-p-clear", className="chip-btn chip-ghost"),
                ]),
                *[_control(f, ivs[f]) for f in FIELDS],
                html.P(["Left out on purpose: loan term (likely recorded after default), lender's state "
                        "(repeats the lender), and borrower traits with little signal such as business age."],
                       className="field-hint panel-foot"),
            ]),
            html.Div(className="risk-main", children=[
                html.Div(id="rk-kpis", className="kpi-row kpi-row-4"),
                html.Div(className="grid grid-gauge", children=[
                    html.Div(className="card", children=[
                        html.Div(className="card-head", children=[html.Div([html.H3("Risk meter"),
                                                                            html.P("Profile charge-off rate · grey tick = all-loan average")])]),
                        dcc.Graph(id="rk-gauge", config={"displayModeBar": False}, style={"height": "230px"}),
                    ]),
                    html.Div(id="rk-summary", className="summary-card"),
                ]),
                html.Div(className="grid grid-2", children=[
                    chart_card("rk-waffle", "…", "100 typical loans: this profile vs all loans, each square one loan",
                               height=340, controls=legend_keys([("Paid in full", "safe"), ("Charged off", "risk")])),
                    chart_card("rk-curve", "…", "Share of loans already charged off by each year after the money was paid out",
                               height=340, controls=legend_keys([("This profile", "total"), ("All loans", "neutral")],
                                                                line=True)),
                ]),
            ]),
        ]),
    ])


_ids = [f"rk-{f}" for f in FIELDS]


@callback(
    [Output(i, "value") for i in _ids],
    Input("rk-p-boom", "n_clicks"), Input("rk-p-safe", "n_clicks"),
    Input("rk-p-lender", "n_clicks"), Input("rk-p-clear", "n_clicks"),
    prevent_initial_call=True,
)
def preset(*_):
    p = PRESETS.get(ctx.triggered_id.replace("rk-p-", ""), {})
    return [p.get(f, ANY) for f in FIELDS]


def _mask(profile, skip=None, only=None):
    m = np.ones(D.N_ALL, dtype=bool)
    for f, v in profile.items():
        if v == ANY or f == skip or (only is not None and f not in only):
            continue
        m &= (D.DF[FIELDS[f][0]] == v).to_numpy()
    return m


def _label(fid, v):
    if fid == "state":
        return D.STATE_NAMES.get(v, v)
    return str(v)


def _gauge(rate, base, n):
    top = max(0.8, min(1.0, rate * 1.3))
    steps = []
    edges = np.linspace(0, top, 25)
    cols = risk_colors((edges[:-1] + edges[1:]) / 2, base)
    for a, b, c in zip(edges[:-1], edges[1:], cols):
        steps.append(dict(range=[a * 100, b * 100], color=c))
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta", value=rate * 100 if n else 0,
        number=dict(suffix="%", valueformat=".1f", font=dict(size=40, color=TEXT)),
        delta=dict(reference=base * 100, valueformat=".1f", suffix=" pts vs avg",
                   increasing=dict(color=RISK_INK), decreasing=dict(color=SAFE), font=dict(size=13)),
        gauge=dict(
            axis=dict(range=[0, top * 100], ticksuffix="%", tickcolor=MUTED, tickfont=dict(color=MUTED, size=10)),
            bar=dict(color=INK, thickness=0.22),
            bgcolor="rgba(0,0,0,0)", borderwidth=0, steps=steps,
            threshold=dict(line=dict(color=MUTED, width=3), thickness=0.95, value=base * 100),
        ),
    ))
    fig.update_layout(margin=dict(l=34, r=40, t=18, b=0))
    return fig


def _waffle(rate, base):
    """Two 10×10 grids: out of 100 loans, how many were charged off (profile vs all loans)."""
    fig = go.Figure()
    shapes, hx, hy, htxt = [], [], [], []
    for g, (label, r) in enumerate((("This profile", rate), ("All loans", base))):
        k = int(round(r * 100))
        for i in range(100):
            x, y = (i % 10) + g * 12, 9 - i // 10  # fill from the top-left, row by row
            shapes.append(dict(type="rect", x0=x + 0.08, x1=x + 0.92, y0=y + 0.08, y1=y + 0.92, line=dict(width=0),
                               fillcolor=RISK if i < k else SAFE, layer="below"))
            hx.append(x + 0.5)
            hy.append(y + 0.5)
            htxt.append(f"<b>{label}</b><br>{k} of 100 charged off<br>{100 - k} of 100 paid in full")
        fig.add_annotation(x=g * 12 + 5, y=-0.35, yanchor="top", showarrow=False,
                           text=f"<b>{label}</b><br>{k} of 100 charged off",
                           font=dict(size=12, color=RISK_INK if (g == 0 and r > base) else TEXT))
    fig.add_scatter(x=hx, y=hy, mode="markers", marker=dict(size=14, opacity=0), text=htxt,
                    hovertemplate="%{text}<extra></extra>", showlegend=False)
    fig.update_layout(shapes=shapes, margin=dict(l=10, r=10, t=10, b=10), hovermode="closest")
    fig.update_xaxes(visible=False, range=[-0.5, 22.5], fixedrange=True)
    fig.update_yaxes(visible=False, range=[-2.4, 10.3], scaleanchor="x", scaleratio=1, fixedrange=True)
    kp, kb = int(round(rate * 100)), int(round(base * 100))
    title = (f"{kp} of every 100 loans like this were charged off, vs {kb} of 100 across all loans"
             if kp != kb else f"{kp} of every 100 loans like this were charged off, the same as across all loans")
    return fig, title


def _cum(frame):
    t = np.sort(frame["MonthsToCO"].dropna().to_numpy())
    return np.searchsorted(t, MONTHS, side="right") / max(len(frame), 1)


def _curve(d):
    """Cumulative share of loans charged off by months since disbursement."""
    prof, allc = _cum(d), _cum(D.DF)
    fig = go.Figure()
    line_area(fig, MONTHS, allc, NEUTRAL, "All loans", width=2, fill_opacity=0.1,
              hovertemplate="All loans: %{y:.1%}<extra></extra>")
    line_area(fig, MONTHS, prof, INK, "This profile", width=2.5, fill_opacity=0.12,
              hovertemplate="This profile: %{y:.1%}<extra></extra>")
    i3 = int(np.where(MONTHS == 36)[0][0])
    fig.add_vline(x=36, line=dict(color=MUTED, width=1, dash="4px,3px"))
    fig.add_annotation(x=36, y=prof[i3], text=f"<b>{prof[i3]:.1%}</b> by year 3", showarrow=True, arrowhead=0,
                       ax=44, ay=-22, xanchor="left", font=dict(color=INK, size=11))
    style_timeseries(fig)
    fig.update_layout(showlegend=False, margin=dict(l=10, r=16, t=14, b=10))
    fig.update_xaxes(title_text="Years after disbursement", tickvals=list(range(0, 121, 12)),
                     ticktext=[str(y) for y in range(11)], range=[0, 120])
    fig.update_yaxes(tickformat=".0%", rangemode="tozero", title_text="Charged off so far")
    final = prof[-1]
    early = prof[i3] / final if final > 0 else 0
    f_ = (lambda v: f"{v:.1%}" if v < 0.1 else f"{v:.0%}")
    title = (f"{f_(prof[i3])} of these loans had failed within 3 years, vs {f_(allc[i3])} of all loans; "
             f"that is {early:.0%} of all the failures this profile ever saw" if final > 0
             else "No loan with this profile was charged off")
    return fig, title


@callback(
    Output("rk-kpis", "children"), Output("rk-summary", "children"), Output("rk-gauge", "figure"),
    Output("rk-waffle", "figure"), Output("rk-waffle-title", "children"),
    Output("rk-curve", "figure"), Output("rk-curve-title", "children"),
    [Input(i, "value") for i in _ids],
)
@D.memo()
def update(*vals):
    profile = dict(zip(FIELDS, vals))
    base = D.BASE_RATE
    d = D.DF[_mask(profile)]
    n = len(d)
    co = int(d["Default"].sum()) if n else 0
    rate = co / n if n else 0.0
    lo, hi = D.wilson(co, n) if n else (0.0, 0.0)
    ls = d["LossShare"].dropna()
    ttd = d["MonthsToCO"].dropna()

    tone = "ok" if n >= 1000 else "warn" if n >= 100 else "bad"
    sample_note = {"ok": "large sample, reliable", "warn": "moderate sample, read the interval",
                   "bad": "small sample, unstable"}[tone]
    kpis = [
        kpi("Matching loans", num(n), sample_note, tone="count"),
        kpi("Charged off", pct(rate) if n else "—", f"95% CI {lo:.1%}–{hi:.1%}" if n else "", tone="risk"),
        kpi("Loss when a loan failed", pct(ls.median(), 0) if len(ls) else "—", "median share of the amount lent", tone="risk"),
        kpi("Time to failure", f"{ttd.median():.0f} months" if len(ttd) else "—", "median, among those that failed"),
    ]

    chosen = [(f, v) for f, v in profile.items() if v != ANY]
    if n == 0:
        e = empty_fig("No historical loans match this profile")
        summary = html.Div(className="summary summary-bad", children=[
            html.Span(className="summary-dot"),
            html.Div("No historical loans match this combination. Set one of the drivers back to 'Any'.")])
        return kpis, summary, _gauge(0, base, 0), e, "No matching loans", e, "No matching loans"

    who = " · ".join(f"{FIELDS[f][1]}: {_label(f, v)}" for f, v in chosen) if chosen else "All loans"
    if lo > base:
        verdict, cls = f"riskier than average: {rate / base:.1f}× the all-loan rate of {base:.1%}", "summary-risk"
    elif hi < base:
        verdict, cls = f"safer than average: {rate / base:.2f}× the all-loan rate of {base:.1%}", "summary-safe"
    else:
        verdict, cls = f"not clearly different from the all-loan rate of {base:.1%}", "summary-ok"
    summary = html.Div(className=f"summary {cls}", children=[
        html.Span(className="summary-dot"),
        html.Div([
            html.Div("Profile", className="summary-kicker"),
            html.P(who, className="summary-who"),
            html.P([html.B(f"{co:,} of {n:,}"), " matching loans were charged off, ", html.B(f"{rate:.1%}"),
                    ". That is ", html.B(verdict), "."]),
            html.P("Observed association in past data, not a prediction for any individual loan."
                   + (" The sample is small, so treat the rate as rough." if tone == "bad" else ""),
                   className="summary-sub"),
        ]),
    ])

    waffle, waffle_title = _waffle(rate, base)
    curve, curve_title = _curve(d)
    return kpis, summary, _gauge(rate, base, n), waffle, waffle_title, curve, curve_title
