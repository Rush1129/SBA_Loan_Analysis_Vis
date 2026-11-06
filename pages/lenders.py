"""Lenders — who made the loan turns out to matter almost as much as what the loan was.
Has its own minimum-loans filter: lenders below it are faded on the bubble chart and left out
of every other figure on the page."""
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

import data as D
from charts import era_lines, risk_bars, risk_heatmap
from components import chart_card, insight, kpi, legend_keys, num, page_header
from theme import (AMBER, AXIS, COUNT, MUTED, RISK_SCALE, SURFACE, TEXT, TEXT_2, empty_fig,
                   risk_colorbar, risk_pos)

MIN_OPTIONS = (1000, 5000, 10000, 20000)
DEFAULT_MIN = MIN_OPTIONS[0]
BUBBLE_FLOOR = 500   # lenders smaller than this are not drawn at all on the bubble chart
FADED = 0.16


def layout():
    return html.Div([
        page_header("Lenders", "Who made the loan mattered almost as much as what the loan was",
                    "Banks make SBA loans and the SBA guarantees part of them. A handful of national banks made most of the loans, "
                    "and their outcomes differed widely, even for loans made in the same years."),
        html.Div(className="filter-bar", children=[
            html.Span("Filter this page", className="filter-title"),
            html.Div(className="field", children=[
                html.Label("Min. loans per lender", className="field-label"),
                dcc.Dropdown(id="le-min", options=[{"label": f"{v:,}", "value": v} for v in MIN_OPTIONS],
                             value=DEFAULT_MIN, clearable=False, searchable=False, className="mini-dd"),
            ]),
            html.Span("Lenders with fewer loans are faded on the bubble chart and left out of everything else.",
                      className="field-hint"),
        ]),
        html.Div(id="le-kpis", className="kpi-row kpi-row-4"),
        html.Div(className="grid grid-1", children=[
            chart_card("le-bubble", "…", f"Lenders with {BUBBLE_FLOOR}+ loans · bubble size = dollars lent · colour = risk vs "
                                         "average · faded = below the minimum", height=500),
        ]),
        html.Div(className="grid grid-2", children=[
            chart_card("le-top", "…", "The largest lenders that meet the minimum, by number of loans · whiskers = 95% CI",
                       height=480),
            chart_card("le-heat", "…", "Charge-off rate for the 12 largest lenders in each approval era · blank = fewer than 100 loans",
                       height=480),
        ]),
        html.Div(className="grid grid-2", children=[
            chart_card("le-state", "…", "Charge-off rate by era, for lenders based in vs outside the borrower's state",
                       height=330, controls=legend_keys([("Same state", "count"), ("Out of state", "amber")])),
            html.Div(id="le-insights", className="stack"),
        ]),
    ])


@callback(
    Output("le-kpis", "children"),
    Output("le-bubble", "figure"), Output("le-bubble-title", "children"),
    Output("le-top", "figure"), Output("le-top-title", "children"),
    Output("le-heat", "figure"), Output("le-heat-title", "children"),
    Output("le-state", "figure"), Output("le-state-title", "children"),
    Output("le-insights", "children"),
    Input("filters", "data"), Input("le-min", "value"),
)
@D.memo()
def update(filters, min_n=DEFAULT_MIN):
    min_n = min_n or DEFAULT_MIN
    d = D.filtered(filters)
    base = d["Default"].mean()
    b = D.rate_by(d, "Bank").sort_values("n", ascending=False).reset_index(drop=True)
    b["name"] = b["Bank"].map(D.pretty_lender)
    inc = b[b["n"] >= min_n]
    if len(inc) < 2:
        e = empty_fig("Fewer than two lenders meet this minimum")
        return [kpi("Lenders", f"{len(inc):,}")], e, "", e, "", e, "", e, "", []
    d_inc = d[d["Bank"].isin(inc["Bank"])]
    worst, best = inc.loc[inc["rate"].idxmax()], inc.loc[inc["rate"].idxmin()]
    kpis = [
        kpi("Lenders included", num(len(inc)), f"of {len(b):,} · {len(d_inc) / len(d):.0%} of all loans", tone="count"),
        kpi("Riskiest lender", worst["name"], f"{worst['rate']:.0%} of {num(worst['n'])} loans failed", tone="risk"),
        kpi("Safest lender", best["name"], f"{best['rate']:.0%} of {num(best['n'])} loans failed", tone="safe"),
        kpi("Gap between them", f"{(worst['rate'] - best['rate']) * 100:.0f} pts",
            f"charge-off rate · lenders with {min_n:,}+ loans"),
    ]

    # ---- bubble: every sizeable lender, the ones below the minimum faded ----
    t = b[b["n"] >= min(BUBBLE_FLOOR, min_n)].copy()
    keep = (t["n"] >= min_n).to_numpy()
    size = np.sqrt(t["disb"] / t["disb"].max()) * 58 + 6
    bub = go.Figure(go.Scatter(
        x=t["n"], y=t["rate"], mode="markers",
        marker=dict(size=size, color=risk_pos(t["rate"], base), colorscale=RISK_SCALE, cmin=0, cmax=1,
                    line=dict(color=SURFACE, width=1.5), opacity=np.where(keep, 0.92, FADED),
                    colorbar=risk_colorbar(base)),
        customdata=np.stack([t["name"], t["co"], t["disb"], t["loss"], t["disb"] / t["n"],
                             np.where(keep, "", f"<br><i>Left out: fewer than {min_n:,} loans</i>")], axis=-1),
        hovertemplate="<b>%{customdata[0]}</b><br>%{x:,} loans · %{y:.1%} charged off"
                      "<br>Lent %{customdata[2]:$,.3s} · avg %{customdata[4]:$,.0f}<br>Lost %{customdata[3]:$,.3s}"
                      "%{customdata[5]}<extra></extra>",
    ))
    bub.add_hline(y=base, line=dict(color=TEXT_2, width=1, dash="4px,3px"), opacity=0.7,
                  annotation_text=f"Average {base:.1%}", annotation_position="bottom right",
                  annotation_font=dict(color=TEXT_2, size=11))
    ti = t[keep]
    label_idx = set(ti.head(6).index) | set(ti.nlargest(3, "rate").index) | {ti["rate"].idxmin()}
    for i in label_idx:
        r = t.loc[i]
        below = r["rate"] > 0.12
        bub.add_annotation(x=np.log10(r["n"]), y=r["rate"], text=r["name"], showarrow=False,
                           yshift=-(size[i] / 2 + 8) if below else (size[i] / 2 + 8), font=dict(color=TEXT, size=11))
    bub.add_vline(x=min_n, line=dict(color=AXIS, width=1, dash="4px,3px"),
                  annotation_text=f"minimum {min_n:,}", annotation_position="top right",
                  annotation_font=dict(color=MUTED, size=11))
    bub.update_xaxes(type="log", title_text="Loans made (log scale)",
                     tickvals=[500, 1000, 2000, 5000, 10000, 20000, 50000],
                     ticktext=["500", "1k", "2k", "5k", "10k", "20k", "50k"])
    bub.update_yaxes(tickformat=".0%", title_text="Charge-off rate", rangemode="tozero")
    bub.update_layout(margin=dict(l=10, r=10, t=14, b=10))
    bubble_title = (f"Same programme, very different results: among {len(inc)} lenders with {min_n:,}+ loans, "
                    f"{worst['name']} lost {worst['rate']:.0%} of its loans and {best['name']} {best['rate']:.0%}")

    # ---- top lenders (bars) -------------------------------------------------
    t15 = inc.head(15).copy()
    t15["Lender name"] = t15["name"]
    top = risk_bars(t15, "Lender name", base, horizontal=True)
    above = int((t15["rate"] > base).sum())
    top_title = (f"{above} of the {len(t15)} biggest lenders with {min_n:,}+ loans failed more often than average; "
                 f"{t15.iloc[0]['name']} made the most loans")

    # ---- lender × era -------------------------------------------------------
    names12 = inc.head(12)["Bank"].tolist()
    sub = d[d["Bank"].isin(names12)].copy()
    sub["LenderName"] = sub["Bank"].map(D.pretty_lender)
    order = [D.pretty_lender(n) for n in names12]
    hm = risk_heatmap(sub, "LenderName", "Era", base, min_n=100, row_order=order, col_order=D.ERA_LABELS)
    boom = sub[sub["Era"] == "2005–08"]
    br = boom.groupby("LenderName")["Default"].agg(["size", "mean"]) if len(boom) else boom
    br = br[br["size"] >= 100] if len(boom) else br
    heat_title = (f"In the boom, {br['mean'].idxmax()} lost {br['mean'].max():.0%} of its loans while "
                  f"{br['mean'].idxmin()} lost {br['mean'].min():.0%}") if len(br) >= 2 else "Large lenders by era"

    # ---- same-state vs out-of-state (included lenders only) ----------------
    st = era_lines(d_inc, "StateSame", [1, 0], [COUNT, AMBER], names={1: "Same state", 0: "Out of state"})
    s1, s0 = d_inc[d_inc["StateSame"] == 1]["Default"].mean(), d_inc[d_inc["StateSame"] == 0]["Default"].mean()
    pe = d_inc.groupby(["Era", "StateSame"], observed=True)["Default"].agg(["size", "mean"]).reset_index()
    pe = pe[pe["size"] >= 100].pivot(index="Era", columns="StateSame", values="mean").dropna()
    held = int((pe[0] > pe[1]).sum()) if {0, 1} <= set(pe.columns) else 0
    state_title = (f"Loans from out-of-state lenders failed at {s0:.0%} vs {s1:.0%} for local lenders, "
                   f"higher in {held} of {len(pe)} eras")

    ins = [
        insight([html.B("Why lenders differ. "),
                 "Under SBAExpress, lenders did their own underwriting and the SBA guaranteed 50%. National banks that "
                 "used it for high-volume, small-ticket lending show some of the highest failure rates."], "warn"),
        insight([html.B("Local knowledge helps. "),
                 "Lenders based in the borrower's own state saw fewer failures, consistent with better knowledge of local "
                 "borrowers. Lender identity is one of the five drivers in the Risk Explorer."]),
        insight([html.B("Read with care. "),
                 "Lender results also reflect which borrowers each bank targeted. This is an association, not a ranking "
                 "of lender quality."]),
    ]
    return kpis, bub, bubble_title, top, top_title, hm, heat_title, st, state_title, ins
