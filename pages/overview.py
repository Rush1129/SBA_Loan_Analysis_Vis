"""Overview — the headline numbers, outcome split, volume and the timing of failures."""
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import Input, Output, callback, html

import data as D
from components import (chart_card, insight, kpi, legend_keys, meter, money, num, page_header, pct, scale_key,
                        spark, splitbar)
from theme import (INK, MONEY_SOFT, MUTED, RISK, RISK_INK, RISK_MID, SAFE, SURFACE, TEXT, TEXT_2, base_rate_line,
                   boom_band, empty_fig, line_area, rgba, risk_colors, style_timeseries)

YEAR_TICKS = dict(tick0=1988, dtick=4)


def layout():
    return html.Div([
        page_header(
            f"Overview · SBA 7(a) loans, FY{D.YEAR_MIN}–{D.YEAR_MAX}",
            "One in five SBA loans failed, and most of the losses came from four boom years",
            "Every loan in the dataset was either paid in full or charged off. Teal marks repaid loans, rose marks "
            "charged-off loans and slate marks dollars lent.",
        ),
        html.Div(id="ov-kpis", className="kpi-row"),
        html.Div(className="grid grid-2-1", children=[
            chart_card("ov-pie", "…", "Share of all loans by final outcome · hover a slice for details", height=340),
            chart_card("ov-volume", "…", "Loans approved each fiscal year: total, paid in full and charged off", height=340,
                       controls=legend_keys([("Total", "total"), ("Paid in full", "safe"), ("Charged off", "risk")],
                                            line=True)),
        ]),
        html.Div(className="grid grid-1", children=[
            chart_card("ov-trend", "…", "Charge-off rate by approval year, each dot shaded by how far that year sits "
                                        "from the average (top) · loans approved each year, by outcome (bottom)",
                       height=500, controls=[legend_keys([("Paid in full", "safe"), ("Charged off", "risk")]), scale_key()],
                       note="Loans from the most recent years had less time to fail, so their rates are understated."),
        ]),
        html.Div(className="grid grid-2", children=[
            chart_card("ov-flow", "…", "Dollars disbursed, by approval year · principal charged off, by the year it was written off",
                       height=330, controls=legend_keys([("Disbursed", "money"), ("Charged off", "risk")])),
            chart_card("ov-ttd", "…", "Charged-off loans by months between disbursement and charge-off · darker bars = "
                                      "the first half of failures", height=330),
        ]),
        html.Div(id="ov-insights", className="grid grid-2"),
    ])


@callback(
    Output("ov-kpis", "children"),
    Output("ov-pie", "figure"), Output("ov-pie-title", "children"),
    Output("ov-volume", "figure"), Output("ov-volume-title", "children"),
    Output("ov-trend", "figure"), Output("ov-trend-title", "children"),
    Output("ov-flow", "figure"), Output("ov-flow-title", "children"),
    Output("ov-ttd", "figure"), Output("ov-ttd-title", "children"),
    Output("ov-insights", "children"),
    Input("filters", "data"),
)
@D.memo()
def update(filters):
    d = D.filtered(filters)
    n = len(d)
    if n == 0:
        e = empty_fig()
        return [kpi("Loans", "0")], e, "", e, "", e, "", e, "", e, "", []
    co = int(d["Default"].sum())
    rate = co / n
    disb = d["DisbursementGross"].sum()
    lost = d["ChgOffPrinGr"].sum()
    sba_lost = d["SBALoss"].sum()
    ttd = d["MonthsToCO"].dropna()
    y = D.rate_by(d, "ApprovalFY")
    lent_by_year = d.groupby("ApprovalFY")["DisbursementGross"].sum()

    kpis = [
        kpi("Loans with a known outcome", num(n), f"FY{D.YEAR_MIN}–{D.YEAR_MAX}",
            foot=splitbar([(1 - rate, "safe"), (rate, "risk")])),
        kpi("Charge-off rate", pct(rate), f"{num(co)} loans failed", tone="risk", foot=spark(y["rate"], RISK)),
        kpi("Money lent", money(disb), f"avg {money(d['DisbursementGross'].mean())} per loan", tone="money",
            foot=spark(lent_by_year.values, "#C9CFD9", kind="bars")),
        kpi("Principal charged off", money(lost), f"{lost / disb:.1%} of every dollar lent", tone="risk",
            foot=meter(lost / disb, "risk")),
        kpi("SBA's share of losses", money(sba_lost), f"about {sba_lost / max(lost, 1):.0%} of the principal lost",
            tone="risk", foot=meter(sba_lost / max(lost, 1), "risk-soft")),
    ]

    # ---- outcome donut (slices grow on hover via style.css) ------------------
    paid_disb = d.loc[d["Default"] == 0, "DisbursementGross"].sum()
    pie = go.Figure(go.Pie(
        labels=[f"Paid in full · {1 - rate:.1%}", f"Charged off · {rate:.1%}"], values=[n - co, co],
        direction="clockwise", rotation=360 * rate, textinfo="none",
        marker=dict(colors=[SAFE, RISK]),
        customdata=[money(paid_disb), money(disb - paid_disb)],
        hovertemplate="<b>%{label}</b><br>%{value:,} loans<br>%{customdata} disbursed<extra></extra>",
    ))
    pie.add_annotation(text=f"<b>{n / 1000:,.0f}k</b><br><span style='font-size:12px;color:{MUTED}'>loans</span>",
                       x=0.5, y=0.5, showarrow=False, font=dict(size=26, color=INK),
                       name="center")  # hover.js swaps this for the hovered slice
    pie.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.04, x=0.5, xanchor="center", yanchor="top"),
                      margin=dict(l=10, r=10, t=10, b=36))
    pie_title = f"{num(n - co)} loans were repaid; {num(co)} ({rate:.1%}) were charged off"

    # ---- loan volume by year: three lines with faded fills ------------------
    vol = go.Figure()
    boom_band(vol)
    for col, name, color, width, alpha in (("n", "Total", INK, 2.5, 0.06), ("pif", "Paid in full", SAFE, 2, 0.2),
                                           ("co", "Charged off", RISK, 2, 0.22)):
        line_area(vol, y["ApprovalFY"], y[col], color, name, width=width, fill_opacity=alpha,
                  hovertemplate=f"{name}: %{{y:,}}<extra></extra>")
    pk = y.loc[y["n"].idxmax()]
    vol.add_annotation(x=pk["ApprovalFY"], y=pk["n"], text=f"<b>{int(pk['n']):,}</b> loans in FY{int(pk['ApprovalFY'])}",
                       showarrow=True, arrowhead=0, ax=-88, ay=22, xanchor="right", font=dict(color=INK, size=11))
    pkc = y.loc[y["co"].idxmax()]
    vol.add_annotation(x=pkc["ApprovalFY"], y=pkc["co"], text=f"{int(pkc['co']):,} of FY{int(pkc['ApprovalFY'])} loans<br>later charged off",
                       showarrow=True, arrowhead=0, ax=150, ay=-70, align="left", bgcolor="rgba(255,255,255,0.9)",
                       font=dict(color=RISK_INK, size=11))
    style_timeseries(vol)
    vol.update_layout(showlegend=False, margin=dict(l=10, r=16, t=22, b=10))
    vol.update_yaxes(tickformat="~s", title_text="Loans approved", rangemode="tozero")
    vol.update_xaxes(**YEAR_TICKS)
    vol_title = f"Approvals peaked at {int(pk['n']):,} loans in FY{int(pk['ApprovalFY'])}" + \
        (", the year before the crash" if int(pk["ApprovalFY"]) == 2007 else "")

    # ---- approval-year charge-off rate: faded area + risk-shaded dots --------
    tr = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.58, 0.42], vertical_spacing=0.08)
    line_area(tr, y["ApprovalFY"], y["rate"], RISK, "Charge-off rate", hoverinfo="skip", showlegend=False, row=1, col=1)
    tr.add_scatter(x=y["ApprovalFY"], y=y["rate"], mode="markers", name="Charge-off rate", showlegend=False,
                   marker=dict(size=9, color=risk_colors(y["rate"], rate), line=dict(color=SURFACE, width=2)),
                   customdata=np.stack([y["n"], y["co"], y["rate"] / rate], axis=-1),
                   hovertemplate="<b>%{y:.1%}</b> charged off<br>%{customdata[1]:,} of %{customdata[0]:,} loans"
                                 "<br>%{customdata[2]:.1f}× the average<extra></extra>", row=1, col=1)
    base_rate_line(tr, rate, "h", "Average", row=1, col=1)
    # bottom panel: loans approved per year, stacked by outcome
    for col_, name, color in (("pif", "Paid in full", SAFE), ("co", "Charged off", RISK)):
        tr.add_bar(x=y["ApprovalFY"], y=y[col_], name=name, marker=dict(color=color, line=dict(color=SURFACE, width=1)),
                   showlegend=False, hovertemplate=f"{name}: %{{y:,}}<extra></extra>", row=2, col=1)
    # after the traces: Plotly skips row/col shapes on subplots that are still empty
    boom_band(tr, row=1, col=1)
    boom_band(tr, label=None, row=2, col=1)
    big = y[y["n"] >= max(1000, 0.02 * y["n"].max())]
    if len(big) >= 2:
        pkr = y.loc[big["rate"].idxmax()]
        tr.add_annotation(x=pkr["ApprovalFY"], y=pkr["rate"], text=f"<b>{pkr['rate']:.1%}</b> of FY{int(pkr['ApprovalFY'])} loans",
                          showarrow=True, arrowhead=0, ax=46, ay=-6, xanchor="left", font=dict(color=TEXT, size=12),
                          row=1, col=1)
        lowp = y.loc[big["rate"].idxmin()]
        tr.add_annotation(x=lowp["ApprovalFY"], y=lowp["rate"], text=f"{lowp['rate']:.1%} in FY{int(lowp['ApprovalFY'])}",
                          showarrow=True, arrowhead=0, ax=0, ay=-34, font=dict(color=SAFE, size=11), row=1, col=1)
    early = y[(y["ApprovalFY"] <= 1988) & (y["n"] < 1000)]
    if len(early):
        tr.add_annotation(x=early["ApprovalFY"].max(), y=early["rate"].max(), text="tiny early cohorts",
                          showarrow=True, arrowhead=0, ax=52, ay=0, xanchor="left", font=dict(color=MUTED, size=10),
                          row=1, col=1)
    style_timeseries(tr)
    tr.update_layout(barmode="stack", bargap=0.18, margin=dict(l=10, r=16, t=22, b=10))
    tr.update_yaxes(tickformat=".0%", rangemode="tozero", title_text="Charged off", row=1, col=1)
    tr.update_yaxes(tickformat="~s", rangemode="tozero", title_text="Loans approved", row=2, col=1)
    tr.update_xaxes(**YEAR_TICKS)
    boom = d[d["Era"] == "2005–08"]
    rest = d[d["Era"] != "2005–08"]
    if len(boom) >= 100 and len(rest) >= 100:
        b, r_ = boom["Default"].mean(), rest["Default"].mean()
        trend_title = f"Loans approved in 2005–08 failed at {b:.0%}, {b / r_:.1f}× the rate of all other years"
    else:
        trend_title = f"{rate:.1%} of loans were charged off"

    # ---- money out vs money lost -------------------------------------------
    lossy = d.dropna(subset=["ChgOffYear"]).groupby("ChgOffYear")["ChgOffPrinGr"].sum()
    lossy = lossy[lossy.index >= D.YEAR_MIN]
    fl = go.Figure()
    fl.add_bar(x=lent_by_year.index, y=lent_by_year.values, name="Disbursed", marker_color=MONEY_SOFT,
               customdata=[money(v) for v in lent_by_year.values],
               hovertemplate="FY%{x} approvals: %{customdata} disbursed<extra></extra>")
    fl.add_bar(x=lossy.index.astype(int), y=lossy.values, name="Charged off", marker_color=RISK, width=0.5,
               customdata=[money(v) for v in lossy.values],
               hovertemplate="Charged off in %{x}: %{customdata}<extra></extra>")
    fl.update_layout(barmode="overlay", bargap=0.18, showlegend=False, hovermode="x unified",
                     margin=dict(l=10, r=10, t=22, b=10))
    fl.update_yaxes(tickprefix="$", exponentformat="B")
    fl.update_xaxes(**YEAR_TICKS)
    if len(lossy):
        pky, pk_out = int(lossy.idxmax()), int(lent_by_year.idxmax())
        fl.add_annotation(x=pky, y=lossy.max(), text=f"{money(lossy.max())} lost in {pky}", showarrow=True,
                          arrowhead=0, ax=-20, ay=-46, font=dict(color=RISK_INK, size=11))
        fl.add_annotation(x=pk_out, y=lent_by_year.max(), text=f"{money(lent_by_year.max())} lent", showarrow=True,
                          arrowhead=0, ax=-40, ay=-14, font=dict(color=INK, size=11))
        flow_title = f"Lending peaked in FY{pk_out}; the losses landed {pky - pk_out} years later, peaking in {pky}"
    else:
        flow_title = "No charge-offs in this selection"

    # ---- time to failure ----------------------------------------------------
    if len(ttd) >= 20:
        bins = np.arange(0, min(ttd.max(), 180) + 6, 6)
        cnt, edges = np.histogram(ttd.clip(upper=bins[-1] - 0.1), bins=bins)
        mids = (edges[:-1] + edges[1:]) / 2
        cum = np.cumsum(cnt) / cnt.sum()
        med, q90 = ttd.median(), ttd.quantile(0.9)
        tt = go.Figure(go.Bar(x=mids, y=cnt, width=5.2, marker=dict(color=[RISK if m < med else RISK_MID for m in mids]),
                              customdata=np.stack([edges[:-1], edges[1:], cum], axis=-1),
                              hovertemplate="%{customdata[0]:.0f}–%{customdata[1]:.0f} months: %{y:,} loans"
                                            "<br>%{customdata[2]:.0%} of failures by then<extra></extra>"))
        tt.add_vline(x=med, line=dict(color=INK, width=1.5), annotation_text=f"median {med:.0f} mo",
                     annotation_position="top right", annotation_font=dict(color=INK, size=11))
        tt.add_vline(x=q90, line=dict(color=rgba(INK, 0.45), width=1, dash="4px,3px"), annotation_text=f"90% by {q90:.0f} mo",
                     annotation_position="top right", annotation_font=dict(color=TEXT_2, size=11))
        tt.update_xaxes(title_text="Months from disbursement to charge-off", dtick=24)
        tt.update_yaxes(title_text="Loans", tickformat="~s")
        tt.update_layout(margin=dict(l=10, r=10, t=22, b=10))
        ttd_title = (f"Half of all failures came within {med / 12:.1f} years of the money going out, "
                     f"and {(ttd <= 36).mean():.0%} within 3 years")
    else:
        tt, ttd_title = empty_fig("Too few charge-offs"), "Too few charge-offs to chart"

    cards = []
    if len(boom) >= 100:
        cards.append(insight([html.B("The boom drove the losses. "),
                              f"2005–08 approvals were {len(boom) / n:.0%} of all loans but produced "
                              f"{boom['ChgOffPrinGr'].sum() / max(lost, 1):.0%} of the dollars charged off."], "warn"))
    if len(ttd):
        cards.append(insight([html.B("Failures come early and cost a lot. "),
                              f"A failed loan was typically written off {ttd.median():.0f} months after disbursement, "
                              f"with {d['LossShare'].median():.0%} of the amount lent never recovered."]))
    return kpis, pie, pie_title, vol, vol_title, tr, trend_title, fl, flow_title, tt, ttd_title, cards
