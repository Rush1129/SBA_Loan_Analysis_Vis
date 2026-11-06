"""Borrowers — industry, location and business profile."""
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

import data as D
from charts import era_lines, risk_bars, risk_heatmap
from components import chart_card, insight, kpi, legend_keys, money, page_header
from theme import AMBER, COUNT, SURFACE, empty_fig, risk_colors, risk_pos, text_on

URBAN, RURAL = COUNT, AMBER
NEW, EXISTING = COUNT, AMBER  # two-series charts take identity slots 1 and 2
MIN_OPTIONS = (1000, 5000, 10000, 20000)
DEFAULT_MIN = MIN_OPTIONS[0]


def layout():
    return html.Div([
        page_header("Borrowers", "Industry and location matter; business age barely does",
                    "What kind of business borrowed, where it was and how big it was. Most borrower traits turn out "
                    "to be weaker signals than timing, lender or guarantee."),
        html.Div(className="filter-bar", children=[
            html.Span("Filter this page", className="filter-title"),
            html.Div(className="field", children=[
                html.Label("Min. loans per industry", className="field-label"),
                dcc.Dropdown(id="bo-min", options=[{"label": f"{v:,}", "value": v} for v in MIN_OPTIONS],
                             value=DEFAULT_MIN, clearable=False, searchable=False, className="mini-dd"),
            ]),
            html.Span(id="bo-min-note", className="field-hint"),
        ]),
        html.Div(id="bo-kpis", className="kpi-row kpi-row-4"),
        html.Div(className="grid grid-2", children=[
            chart_card("bo-ind", "…", "Charge-off rate by industry (NAICS sector) · whiskers = 95% CI", height=560),
            chart_card("bo-indera", "…", "Charge-off rate for each industry in each approval era · blank = fewer than 100 loans",
                       height=560),
        ]),
        html.Div(className="grid grid-3", children=[
            chart_card("bo-area", "…", "Charge-off rate by era, urban vs rural borrowers", height=320,
                       controls=legend_keys([("Urban", "count"), ("Rural", "rural")]),
                       note="Before 2002 most loans have no urban/rural code, so the comparison starts in the 1990s."),
            chart_card("bo-age", "…", "Charge-off rate by era, new vs existing businesses", height=320,
                       controls=legend_keys([("New", "count"), ("Existing", "amber")])),
            chart_card("bo-emp", "…", "Charge-off rate by number of employees at approval", height=320),
        ]),
        html.Div(className="grid grid-1", children=[
            chart_card("bo-tree", "…", "Box area = principal charged off · colour = industry charge-off rate vs average",
                       height=380),
        ]),
        html.Div(id="bo-insights", className="grid grid-2"),
    ])


@callback(
    Output("bo-kpis", "children"), Output("bo-min-note", "children"),
    Output("bo-ind", "figure"), Output("bo-ind-title", "children"),
    Output("bo-indera", "figure"), Output("bo-indera-title", "children"),
    Output("bo-area", "figure"), Output("bo-area-title", "children"),
    Output("bo-age", "figure"), Output("bo-age-title", "children"),
    Output("bo-emp", "figure"), Output("bo-emp-title", "children"),
    Output("bo-tree", "figure"), Output("bo-tree-title", "children"),
    Output("bo-insights", "children"),
    Input("filters", "data"), Input("bo-min", "value"),
)
@D.memo()
def update(filters, min_n=DEFAULT_MIN):
    min_n = min_n or DEFAULT_MIN
    d_all = D.filtered(filters)
    base = d_all["Default"].mean()  # reference: every loan, so colours mean the same at any minimum
    counts = d_all["Industry"].value_counts()
    keep = counts[counts >= min_n].index
    d = d_all[d_all["Industry"].isin(keep)]  # industries below the minimum are left out of the whole page
    left_out = counts[counts < min_n]
    share = len(d) / len(d_all)
    note = (f"{len(keep)} of {len(counts)} industries included ({share:.1%} of loans). "
            + ("Left out: " + " · ".join(map(str, left_out.index[:4])) + (" …" if len(left_out) > 4 else "")
               if len(left_out) else "None left out."))
    if len(keep) < 2:
        e = empty_fig("Fewer than two industries meet this minimum")
        return [kpi("Industries", f"{len(keep)}")], note, e, "", e, "", e, "", e, "", e, "", e, "", []
    ind = D.rate_by(d, "Industry").sort_values("rate", ascending=False)
    worst, best = ind.iloc[0], ind.iloc[-1]
    urb = d[d["Area"] == "Urban"]["Default"].mean()
    rur = d[d["Area"] == "Rural"]["Default"].mean()
    new = d[d["BizType"] == "New"]["Default"].mean()
    old = d[d["BizType"] == "Existing"]["Default"].mean()
    kpis = [
        kpi("Riskiest industry", str(worst["Industry"]), f"{worst['rate']:.0%} charged off · {len(keep)} industries",
            tone="risk"),
        kpi("Safest industry", str(best["Industry"]), f"{best['rate']:.0%} charged off · {min_n:,}+ loans each", tone="safe"),
        kpi("Urban vs rural", f"{urb:.0%} / {rur:.0%}" if not np.isnan(rur) else "—", "charge-off rate", tone="count"),
        kpi("New vs existing", f"{new:.0%} / {old:.0%}" if not np.isnan(new) and not np.isnan(old) else "—",
            "charge-off rate", tone="count"),
    ]

    indf = risk_bars(ind, "Industry", base, horizontal=True)
    if len(ind) >= 2:
        ind_title = (f"{worst['Industry']} loans failed most ({worst['rate']:.0%}), "
                     f"{worst['rate'] / max(best['rate'], 1e-9):.1f}× the rate of {best['Industry']} ({best['rate']:.0%})")
    else:
        ind_title = f"{worst['Industry']}: {worst['rate']:.0%} of loans charged off"

    order = ind["Industry"].astype(str).tolist()
    hm = risk_heatmap(d[d["Industry"].isin(order)], "Industry", "Era", base, min_n=100,
                      row_order=order, col_order=D.ERA_LABELS)
    boom = d[(d["Era"] == "2005–08") & d["Industry"].isin(order)]
    early = d[d["Era"] == "1991–2001"]
    bi = D.rate_by(boom, "Industry", min_n=100) if len(boom) else boom
    if len(bi) >= 3 and len(early) >= 500:
        indera_title = (f"Every industry spiked in 2005–08: from {early['Default'].mean():.0%} overall in 1991–2001 "
                        f"to between {bi['rate'].min():.0%} and {bi['rate'].max():.0%} by sector")
    else:
        indera_title = "Industry risk by approval era"

    area = era_lines(d[d["Era"] != "1987–90"], "Area", ["Urban", "Rural"], [URBAN, RURAL])
    ar = d[d["Area"].isin(["Urban", "Rural"])].groupby(["Era", "Area"], observed=True)["Default"].agg(["size", "mean"]) \
        .reset_index().pivot(index="Era", columns="Area", values="mean").dropna()
    if len(ar):
        higher = (ar["Urban"] > ar["Rural"]).mean()
        area_title = (f"Urban loans failed more often than rural ones in {int(higher * len(ar))} of {len(ar)} eras"
                      if higher >= 0.5 else "Rural loans were riskier in most eras")
    else:
        area_title = "Urban vs rural"

    age = era_lines(d, "BizType", ["New", "Existing"], [NEW, EXISTING])
    gap = (new - old) * 100 if not (np.isnan(new) or np.isnan(old)) else 0
    age_title = (f"New and existing businesses failed at nearly the same rate ({new:.1%} vs {old:.1%})"
                 if abs(gap) < 2 else f"New businesses failed {'more' if gap > 0 else 'less'} often ({new:.1%} vs {old:.1%})")

    eb = D.rate_by(d, "EmpBand", min_n=100)
    emp = risk_bars(eb, "EmpBand", base)
    emp.update_xaxes(title_text="Employees")
    if len(eb) >= 2:
        h, l = eb.loc[eb["rate"].idxmax()], eb.loc[eb["rate"].idxmin()]
        emp_title = f"Firms with {h['EmpBand']} staff failed most ({h['rate']:.0%}); those with {l['EmpBand']} least ({l['rate']:.0%})"
    else:
        emp_title = "Workforce size"

    tr_ = D.rate_by(d, "Industry")
    tr_ = tr_[tr_["loss"] > 0].sort_values("loss", ascending=False)
    tree = go.Figure(go.Treemap(
        labels=tr_["Industry"].astype(str), parents=[""] * len(tr_), values=tr_["loss"],
        marker=dict(colors=risk_colors(tr_["rate"], base), line=dict(color=SURFACE, width=2)),
        customdata=np.stack([tr_["rate"], tr_["n"], tr_["loss"] / tr_["loss"].sum()], axis=-1),
        text=[f"{money(v)} lost<br>{r:.0%} failed" for v, r in zip(tr_["loss"], tr_["rate"])],
        texttemplate="<b>%{label}</b><br>%{text}",
        textfont=dict(color=[text_on(p) for p in risk_pos(tr_["rate"], base)], size=12),
        hovertemplate="<b>%{label}</b><br>%{value:$,.0f} principal charged off (%{customdata[2]:.0%} of all losses)"
                      "<br>Charge-off rate %{customdata[0]:.1%} of %{customdata[1]:,} loans<extra></extra>",
        tiling=dict(pad=2),
    ))
    tree.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    top3 = tr_.head(3)["loss"].sum() / tr_["loss"].sum()
    tree_title = (f"{tr_.iloc[0]['Industry']} alone lost {money(tr_.iloc[0]['loss'])}; "
                  f"the top 3 industries account for {top3:.0%} of the money lost")

    ins = [
        insight([html.B("Industry is a medium signal. "),
                 "Real estate, finance and transport loans failed most; agriculture, mining and health care least. "
                 "But the industry-by-era heatmap shows timing dominated: every sector's rate rose in the boom."]),
        insight([html.B("Business age is not a useful signal here. "),
                 f"New businesses failed at {new:.1%} vs {old:.1%} for existing ones. Its Information Value is close to zero, "
                 "so it is not used in the Risk Explorer."], "warn"),
    ]
    return (kpis, note, indf, ind_title, hm, indera_title, area, area_title, age, age_title, emp, emp_title,
            tree, tree_title, ins)
