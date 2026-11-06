"""Loans — how the size and the guarantee of a loan relate to failure and loss."""
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, callback, html

import data as D
from charts import risk_bars, risk_heatmap
from components import chart_card, insight, kpi, legend_keys, money, page_header, pct, section
from theme import INK, MUTED, OUTCOME_COLORS, RISK, SURFACE, TEXT, empty_fig, rgba

# ordinal ramp for guarantee bands (identity of an ordered category, not risk)
GUAR_RAMP = ["#9DB0EC", "#7F95E2", "#617BD6", "#4763C7", "#3550A8", "#253C82"]

# The loss-severity histogram ("When a loan failed, a median 61% of it was lost…") is hidden for now.
# Set this to True to show it again: it gets its own full-width row under the four main charts.
SHOW_LOSS_CHART = False


def layout():
    rows = [
        page_header("Loan structure", "Small loans with a thin government guarantee carried the most risk",
                    "Loan size and the share the SBA guaranteed are two of the strongest application-time drivers. "
                    "They are linked: the 50% guarantee mostly belongs to SBAExpress, a fast, low-paperwork programme for small loans."),
        html.Div(id="ln-kpis", className="kpi-row kpi-row-4"),
        section("Loan size"),
        html.Div(className="grid grid-2", children=[
            chart_card("ln-size", "…", "Charge-off rate by disbursed amount · whiskers = 95% confidence interval", height=330),
            chart_card("ln-hist", "…", "Number of loans by disbursed amount (log scale), split by outcome", height=330,
                       controls=legend_keys([("Paid in full", "safe"), ("Charged off", "risk")])),
        ]),
        section("Over time: the boom and the SBA guarantee"),
        html.Div(className="grid grid-2", children=[
            chart_card("ln-sizeera", "…", "Charge-off rate by approval era × loan size", height=330),
            chart_card("ln-mix", "…", "Share of loans approved each year by guarantee share", height=330,
                       controls=legend_keys([("≤ 50%", "g0"), ("75–79%", "g2"), ("85–89%", "g4"), ("≥ 90%", "g5")]),
                       note="50% guarantee: mostly SBAExpress. 75% and 85%: standard 7(a) loans above and below $150k. "
                            "90% and up: special programmes, mostly from the 1990s and the 2009–11 stimulus."),
        ]),
    ]
    if SHOW_LOSS_CHART:
        rows.append(html.Div(className="grid grid-1", children=[
            chart_card("ln-loss", "…", "Share of the disbursed amount never recovered, for charged-off loans", height=330),
        ]))
    rows.append(html.Div(id="ln-insights", className="grid grid-2"))
    return html.Div(rows)


def _loss_chart(d, ls):
    """Loss severity: principal charged off ÷ amount disbursed, for charged-off loans (hidden by default)."""
    if len(ls) < 30:
        return empty_fig("Too few charge-offs"), "Too few charge-offs to measure loss"
    bins = np.linspace(0, 1.0, 21)
    cnt, e2 = np.histogram(ls.clip(0, 0.999), bins=bins)
    lf = go.Figure(go.Bar(x=(e2[:-1] + e2[1:]) / 2, y=cnt, width=0.046, marker=dict(color=RISK, cornerradius=3),
                          customdata=np.stack([e2[:-1], e2[1:]], axis=-1),
                          hovertemplate="%{customdata[0]:.0%}–%{customdata[1]:.0%} lost: %{y:,} loans<extra></extra>"))
    med = ls.median()
    lf.add_vline(x=med, line=dict(color=TEXT, width=1), annotation_text=f"median {med:.0%}",
                 annotation_position="top left", annotation_font=dict(color=TEXT, size=11))
    lf.update_xaxes(tickformat=".0%", title_text="Principal charged off ÷ amount disbursed", range=[0, 1])
    lf.update_yaxes(title_text="Charged-off loans", tickformat="~s")
    lf.update_layout(margin=dict(l=10, r=10, t=22, b=10))
    bysize = d.groupby("SizeBand", observed=True)["LossShare"].median().dropna()
    title = (f"When a loan failed, a median {med:.0%} of it was lost; for loans of "
             f"{bysize.idxmax()} it was {bysize.max():.0%}") if len(bysize) else f"Median loss {med:.0%}"
    return lf, title


_outputs = [
    Output("ln-kpis", "children"),
    Output("ln-size", "figure"), Output("ln-size-title", "children"),
    Output("ln-hist", "figure"), Output("ln-hist-title", "children"),
    Output("ln-sizeera", "figure"), Output("ln-sizeera-title", "children"),
    Output("ln-mix", "figure"), Output("ln-mix-title", "children"),
    Output("ln-insights", "children"),
]
if SHOW_LOSS_CHART:
    _outputs += [Output("ln-loss", "figure"), Output("ln-loss-title", "children")]


@callback(*_outputs, Input("filters", "data"))
@D.memo()
def update(filters):
    d = D.filtered(filters)
    if len(d) == 0:
        e = empty_fig()
        return ([kpi("Loans", "0")], e, "", e, "", e, "", e, "", []) + ((e, "") if SHOW_LOSS_CHART else ())
    base = d["Default"].mean()
    amt = d["DisbursementGross"]
    small = (amt <= 50_000).mean()
    ls = d["LossShare"].dropna()
    kpis = [
        kpi("Median loan", money(amt.median()), f"average {money(amt.mean())}", tone="money"),
        kpi("Loans of $50k or less", pct(small, 0), "of loans in the selection", tone="count"),
        kpi("With a 50% guarantee", pct((d["GuarPct"] <= 50.05).mean(), 0), "mostly SBAExpress", tone="count"),
        kpi("Lost when a loan failed", pct(ls.median(), 0) if len(ls) else "—", "median share of the amount lent", tone="risk"),
    ]

    # size
    sb = D.rate_by(d, "SizeBand")
    size = risk_bars(sb, "SizeBand", base)
    if len(sb) >= 2:
        a, b = sb.iloc[0], sb.iloc[-1]
        size_title = (f"Loans {a['SizeBand']} failed at {a['rate']:.0%}, "
                      f"{a['rate'] / max(b['rate'], 1e-9):.1f}× the rate of loans {b['SizeBand']}")
    else:
        size_title = "Charge-off rate by loan size"

    # histogram (log bins, pre-aggregated)
    edges = np.logspace(3, 7, 41)
    mids = np.sqrt(edges[:-1] * edges[1:])
    h = go.Figure()
    for o in D.OUTCOMES:
        v = d.loc[d["Outcome"] == o, "DisbursementGross"].clip(edges[0], edges[-1] * 0.999)
        cnt, _ = np.histogram(v, bins=edges)
        h.add_bar(x=mids, y=cnt, width=np.diff(edges) * 0.9, name=o, marker_color=OUTCOME_COLORS[o],
                  customdata=np.stack([edges[:-1], edges[1:]], axis=-1),
                  hovertemplate=f"{o}<br>%{{customdata[0]:$,.0f}} – %{{customdata[1]:$,.0f}}: %{{y:,}} loans<extra></extra>")
    h.update_layout(barmode="stack", showlegend=False, bargap=0, margin=dict(l=10, r=10, t=14, b=10))
    h.update_xaxes(type="log", dtick=1, title_text="Disbursed amount", tickprefix="$", tickformat="~s")
    h.update_yaxes(title_text="Loans", tickformat="~s")
    q1, q3 = amt.quantile([0.25, 0.75])
    hist_title = f"Half of all loans were between {money(q1)} and {money(q3)}; failures cluster at the small end"

    # era × size
    hm = risk_heatmap(d, "Era", "SizeBand", base, min_n=100, row_order=D.ERA_LABELS, col_order=D.SIZE_LABELS)
    boom = d[d["Era"] == "2005–08"]
    if len(boom) > 500:
        bs = D.rate_by(boom, "SizeBand", min_n=100)
        sizeera_title = (f"The boom hit small loans hardest: in 2005–08, {bs['rate'].max():.0%} of the riskiest size group failed "
                         f"vs {bs['rate'].min():.0%} of the safest")
    else:
        sizeera_title = "Small loans are riskier in almost every era"

    # guarantee mix over time (100% stacked area)
    mix = d.groupby(["ApprovalFY", "GuarBand"], observed=False).size().unstack(fill_value=0)
    mix = mix[mix.sum(axis=1) >= 50]
    share = mix.div(mix.sum(axis=1), axis=0)
    mx = go.Figure()
    for i, band in enumerate(D.GUAR_LABELS):
        if band not in share:
            continue
        mx.add_scatter(x=share.index, y=share[band], name=band, mode="lines", stackgroup="g",
                       line=dict(width=1.2, color=SURFACE), fillcolor=GUAR_RAMP[i],
                       hovertemplate=f"{band}: %{{y:.0%}}<extra></extra>")
    mx.add_vrect(x0=2004.5, x1=2008.5, line=dict(color=rgba(INK, 0.55), width=1, dash="4px,3px"), fillcolor="rgba(0,0,0,0)")
    mx.add_annotation(x=2006.5, y=1, yref="y domain", text="2005–08 boom", showarrow=False, font=dict(color=MUTED, size=11),
                      yanchor="bottom")
    mx.update_layout(showlegend=False, hovermode="x unified", margin=dict(l=10, r=10, t=22, b=10))
    mx.update_yaxes(tickformat=".0%", range=[0, 1])
    mx.update_xaxes(dtick=4)
    if "≤ 50%" in share and len(share) > 3:
        early = share.loc[share.index <= 1998, "≤ 50%"].mean() if (share.index <= 1998).any() else share["≤ 50%"].iloc[0]
        peak_year = int(share["≤ 50%"].idxmax())
        mix_title = (f"50%-guarantee loans went from {early:.0%} of approvals in the 1990s "
                     f"to {share['≤ 50%'].max():.0%} in FY{peak_year}")
    else:
        mix_title = "Guarantee mix over time"

    ins = []
    if len(sb) >= 2 and len(ls) >= 30:
        ins.append(insight([html.B("Small loans fail more and lose more. "),
                            f"Loans of $50k or less were {small:.0%} of the selection. When they failed, the typical loss was "
                            f"{d.loc[d['SizeBand'] == '≤ $50k', 'LossShare'].median():.0%} of the amount lent, "
                            "likely because small loans are rarely backed by property."], "warn"))
    ins.append(insight([html.B("The boom was an SBAExpress boom. "),
                        "The surge in 2005–08 lending was mostly 50%-guarantee loans, one of the two highest-risk "
                        "guarantee bands. Size, guarantee and era tell the same story from three angles."]))
    out = (kpis, size, size_title, h, hist_title, hm, sizeera_title, mx, mix_title, ins)
    if SHOW_LOSS_CHART:
        out += _loss_chart(d, ls)
    return out
