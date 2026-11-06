"""Geography — where borrowers were: states and the cities inside them. Has its own state filter."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html, no_update

import data as D
from charts import risk_bars
from components import chart_card, insight, kpi, legend_keys, money, num, page_header, pct, seg
from theme import (AXIS, COUNT, COUNT_SCALE, FONT, INK, LOSS_SCALE, MONEY_SCALE, MUTED, NEUTRAL, RISK,
                   RISK_SCALE, SAFE, SURFACE, TEXT_2, boom_band, empty_fig, line_area, rgba, risk_colorbar, risk_colors,
                   risk_pos, mix, style_timeseries, text_on)

MIN_OPTIONS = (1000, 5000, 10000, 20000)
DEFAULT_MIN = MIN_OPTIONS[0]
NATIONAL = D.BASE_RATE
YEAR_TICKS = dict(tick0=1988, dtick=4)
FADE = 0.8  # unselected states: their colour blended 80% toward white (looks like ~20% opacity)
# Tiny north-eastern states are too small to hold their code, so it sits in a column in the
# Atlantic with a leader line: state -> (centroid lon, lat, label lon, lat). Centroids are the ones
# Plotly uses for its USA-states map; label longitudes step west so the column stays vertical
# on the Albers projection.
CALLOUTS = {"RI": (-71.56, 41.70, -70.90, 40.9), "CT": (-72.73, 41.63, -71.15, 39.9),
            "NJ": (-74.67, 40.21, -71.40, 38.9), "DE": (-75.51, 38.99, -71.65, 37.9),
            "MD": (-76.79, 39.04, -71.90, 36.9), "DC": (-77.02, 38.90, -72.15, 35.9)}
NUDGED = {"VT": (-72.75, 44.25), "NH": (-71.50, 43.45)}  # narrow neighbours: keep both codes apart
STATE_LABEL_FONT = dict(family=FONT, size=9, weight=600)


def layout():
    return html.Div([
        page_header("Geography", "Where the borrowers were, and where loans failed most",
                    "Charge-off rates by state and by the cities inside each state. Colours compare each place with the "
                    f"national average ({NATIONAL:.1%}): teal is safer, grey is about average, rose is riskier. Pick a "
                    "state below, or click one on the map, to see its cities, loan sizes, trend and lenders."),
        html.Div(className="filter-bar", children=[
            html.Span("Filter this page", className="filter-title"),
            html.Div(className="field grow", children=[
                html.Label("State", className="field-label"),
                dcc.Dropdown(id="geo-state", options=[{"label": f"{D.STATE_NAMES[s]} ({s})", "value": s} for s in D.STATES],
                             placeholder="All states (pick one, or click the map)", className="dd"),
            ]),
            html.Div(className="field", children=[
                html.Label("Min. loans per state", className="field-label"),
                dcc.Dropdown(id="geo-min", options=[{"label": f"{v:,}", "value": v} for v in MIN_OPTIONS],
                             value=DEFAULT_MIN, clearable=False, searchable=False, className="mini-dd"),
            ]),
        ]),
        html.Div(id="geo-kpis", className="kpi-row"),
        html.Div(className="grid grid-3", children=[
            chart_card("geo-map", "…", "The selected state is outlined in black and the others fade · click a state to "
                                       "select it, click it again to clear", height=430, className="span-2",
                       controls=seg("geo-map-metric", [
                           {"label": "Risk", "value": "rate"}, {"label": "Loans", "value": "n"},
                           {"label": "$ lost", "value": "loss"}, {"label": "Avg loan", "value": "avg"},
                       ], "rate"),
                       note="States with fewer loans than the minimum set above are faded here and left out of "
                            "every other chart and figure on this page."),
            chart_card("geo-rank", "…", "Charge-off rate minus the national average, in percentage points", height=430),
        ]),
        html.Div(id="geo-prompt", children=insight(
            [html.B("Pick a state to look inside it. "),
             "Choose one in the filter above or click it on the map to see its top cities, how its loan sizes compare "
             "with the rest of the country, its charge-off trend and which lenders served it."])),
        html.Div(id="geo-state-section", style={"display": "none"}, children=[
            html.Div(className="grid grid-2", children=[
                chart_card("geo-cities", "…", "Loans in the state's 10 busiest cities, split by outcome", height=420,
                           controls=legend_keys([("Paid in full", "safe"), ("Charged off", "risk")])),
                chart_card("geo-amount", "…", "Share of loans in each loan-amount band (log scale): the selected state vs "
                                              "the lowest charge-off state that meets the minimum loans set above",
                           height=420,
                           controls=legend_keys([("Selected state", "count"), ("Lowest charge-off state", "safe")],
                                                line=True)),
            ]),
            html.Div(className="grid grid-2", children=[
                chart_card("geo-trend", "…", "Charge-off rate by approval year: the selected state vs the national rate",
                           height=360, controls=legend_keys([("Selected state", "count"), ("National", "neutral")],
                                                            line=True)),
                chart_card("geo-local", "…", "Charge-off rate by location type and by where the lender is based, vs the "
                                             "national average", height=360),
            ]),
        ]),
        html.Div(id="geo-insights", className="grid grid-2"),
    ])


def _included(min_n):
    """States with at least ``min_n`` loans: the only ones analysed on this page."""
    n = D.DF["State"].value_counts()
    return set(n[n >= min_n].index.astype(str))


@callback(
    Output("geo-state", "value"),
    Input("geo-map", "clickData"), State("geo-state", "value"), State("geo-min", "value"),
    prevent_initial_call=True,
)
def map_click(click, current, min_n):
    if not click:
        return no_update
    s = click["points"][0].get("location")
    if s not in D.STATE_NAMES or s not in _included(min_n or DEFAULT_MIN):
        return no_update  # faded (left-out) states can't be selected
    return None if s == current else s


@callback(Output("geo-state", "options"), Input("geo-min", "value"))
def state_options(min_n):
    inc = _included(min_n or DEFAULT_MIN)
    return [{"label": f"{D.STATE_NAMES[s]} ({s})" + ("" if s in inc else " · too few loans"), "value": s,
             "disabled": s not in inc} for s in D.STATES]


def _map(metric, state, min_n):
    s = D.rate_by(D.DF, "State")
    s["avg"] = s["disb"] / s["n"]
    s["name"] = s["State"].map(D.STATE_NAMES)
    ok = s[s["n"] >= min_n]
    s["note"] = np.where(s["n"] >= min_n, "", f"<br><i>Left out: fewer than {min_n:,} loans</i>")
    if metric == "rate":
        z, cs, zr, cb = risk_pos(s["rate"], NATIONAL), RISK_SCALE, (0, 1), risk_colorbar(NATIONAL)
    else:
        col, cs, title, fmt = {"n": ("n", COUNT_SCALE, "Loans", "~s"), "loss": ("loss", LOSS_SCALE, "$ lost", "$~s"),
                               "avg": ("avg", MONEY_SCALE, "Avg loan", "$~s")}[metric]
        z = s[col].astype(float)
        zr = (float(ok[col].min()), float(ok[col].max()))
        cb = dict(title=dict(text=title, font=dict(color=TEXT_2, size=11)), tickformat=fmt, thickness=10, len=0.75,
                  outlinewidth=0, tickfont=dict(color=MUTED, size=11))
    hover = ("<b>%{customdata[0]}</b><br>Charge-off rate <b>%{customdata[3]:.1%}</b>"
             "<br>%{customdata[2]:,} of %{customdata[1]:,} loans<br>Avg loan %{customdata[4]:$,.0f}"
             "<br>Principal lost %{customdata[5]:$,.0f}%{customdata[6]}<extra></extra>")
    custom = np.stack([s["name"], s["n"], s["co"], s["rate"], s["avg"], s["loss"], s["note"]], axis=-1)
    zv_all = np.asarray(z, dtype=float)
    included = (s["n"] >= min_n).to_numpy()
    keep = included & np.array([(not state) or st_ == state for st_ in s["State"]])
    mp = go.Figure()
    # Plotly ignores per-state opacity on choropleths, so faded states (left out by the minimum, or not
    # the selected state) are a second layer drawn with the same scale blended toward white.
    if (~keep).any():
        mp.add_choropleth(
            locations=s["State"][~keep], z=zv_all[~keep], zmin=zr[0], zmax=zr[1], locationmode="USA-states",
            colorscale=[[p_, mix(c_, SURFACE, FADE)] for p_, c_ in cs], showscale=False,
            marker_line_color=SURFACE, marker_line_width=1, customdata=custom[~keep], hovertemplate=hover)
    mp.add_choropleth(
        locations=s["State"][keep], z=zv_all[keep], zmin=zr[0], zmax=zr[1], locationmode="USA-states", colorscale=cs,
        marker_line_color=SURFACE, marker_line_width=1, customdata=custom[keep], colorbar=cb, hovertemplate=hover)
    if state:
        mp.add_choropleth(locations=[state], z=[0], locationmode="USA-states", showscale=False,
                          colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
                          marker_line_color=INK, marker_line_width=2.6, hoverinfo="skip")
    # state codes on every state (white on dark fills, ink on light); full names are in the hover label
    zv = np.asarray(z, dtype=float)
    if metric == "rate":
        on_fill = [text_on(p) for p in zv]
    else:
        lo_z, span = np.nanmin(zv), (np.nanmax(zv) - np.nanmin(zv)) or 1.0
        on_fill = ["#FFFFFF" if (v - lo_z) / span > 0.62 else INK for v in zv]
    full = {str(c) for c, k_ in zip(s["State"], keep) if k_}  # faded states keep only a faint code
    label_color = {str(c): (col if str(c) in full else rgba(INK, 0.3)) for c, col in zip(s["State"], on_fill)}
    inside = [c for c in label_color if c not in CALLOUTS and c not in NUDGED]
    mp.add_scattergeo(locations=inside, locationmode="USA-states", text=inside, mode="text",
                      textfont=dict(**STATE_LABEL_FONT, color=[label_color[c] for c in inside]),
                      hoverinfo="skip", showlegend=False)
    nudged = [c for c in NUDGED if c in label_color]
    mp.add_scattergeo(lon=[NUDGED[c][0] for c in nudged], lat=[NUDGED[c][1] for c in nudged], text=nudged,
                      mode="text", textfont=dict(**STATE_LABEL_FONT, color=[label_color[c] for c in nudged]),
                      hoverinfo="skip", showlegend=False)
    out = [c for c in CALLOUTS if c in label_color]
    mp.add_scattergeo(lon=sum(([CALLOUTS[c][0], CALLOUTS[c][2] - 0.2, None] for c in out), []),
                      lat=sum(([CALLOUTS[c][1], CALLOUTS[c][3], None] for c in out), []),
                      mode="lines", line=dict(color=MUTED, width=0.8), hoverinfo="skip", showlegend=False)
    mp.add_scattergeo(lon=[CALLOUTS[c][2] for c in out], lat=[CALLOUTS[c][3] for c in out], text=out, mode="text",
                      textposition="middle right",
                      textfont=dict(**STATE_LABEL_FONT, color=[INK if c in full else rgba(INK, 0.3) for c in out]),
                      hoverinfo="skip", showlegend=False)
    mp.update_geos(scope="usa", bgcolor="rgba(0,0,0,0)", showlakes=False, landcolor="#EEF0F3",
                   subunitcolor=SURFACE, showframe=False)
    mp.update_layout(margin=dict(l=0, r=0, t=0, b=0), dragmode=False)

    sel = ok[ok["State"] == state] if state else pd.DataFrame()
    if len(sel):
        one = sel.iloc[0]
        map_title = (f"{one['name']}: {one['rate']:.1%} charged off, {(one['rate'] - NATIONAL) * 100:+.1f} pts vs national, "
                     f"{int(one['n']):,} loans")
    else:
        w, bst = ok.loc[ok["rate"].idxmax()], ok.loc[ok["rate"].idxmin()]
        map_title = (f"Of {len(ok)} states with {min_n:,}+ loans, {w['name']} failed most often ({w['rate']:.0%}) "
                     f"and {bst['name']} least ({bst['rate']:.0%})"
                     if metric == "rate" else
                     {"n": f"{ok.loc[ok['n'].idxmax(), 'name']} had the most loans ({int(ok['n'].max()):,})",
                      "loss": f"{ok.loc[ok['loss'].idxmax(), 'name']} lost the most money ({money(ok['loss'].max())})",
                      "avg": f"{ok.loc[ok['avg'].idxmax(), 'name']} had the largest average loan ({money(ok['avg'].max())})"}[metric])
    return mp, map_title, ok


def _rank(ok, min_n):
    srt = ok.sort_values("rate", ascending=False)
    k = 8
    sel = pd.concat([srt.head(k), srt.tail(k)]).drop_duplicates("State") if len(srt) > 2 * k else srt
    dev = (sel["rate"] - NATIONAL) * 100
    rk = go.Figure(go.Bar(
        x=dev, y=sel["name"], orientation="h", marker=dict(color=risk_colors(sel["rate"], NATIONAL), cornerradius=4),
        text=[f"{v:.0%}" for v in sel["rate"]], textposition="outside", textfont=dict(color=TEXT_2, size=11),
        cliponaxis=False, customdata=np.stack([sel["rate"], sel["n"]], axis=-1),
        hovertemplate="<b>%{y}</b><br>%{customdata[0]:.1%} charged off (%{x:+.1f} pts)<br>%{customdata[1]:,} loans<extra></extra>",
    ))
    rk.add_vline(x=0, line=dict(color=TEXT_2, width=1))
    span = max(abs(dev).max(), 1) * 1.35
    rk.update_xaxes(range=[-span, span], ticksuffix=" pts", zeroline=False)
    rk.update_yaxes(autorange="reversed", showgrid=False)
    rk.update_layout(margin=dict(l=10, r=14, t=10, b=10), bargap=0.3)
    title = (f"The 8 riskiest and 8 safest of the {len(srt)} states with {min_n:,}+ loans" if len(srt) > 2 * k
             else f"All {len(srt)} states with {min_n:,}+ loans, riskiest first")
    return rk, title


def _cities(d, name):
    c = D.rate_by(d, "CityST").nlargest(10, "n").iloc[::-1]  # largest at the top of a horizontal chart
    labels = c["CityST"].astype(str).str.rsplit(",", n=1).str[0]
    fig = go.Figure()
    fig.add_bar(y=labels, x=c["pif"], orientation="h", name="Paid in full",
                marker=dict(color=SAFE, line=dict(color=SURFACE, width=1)),
                customdata=np.stack([c["n"], 1 - c["rate"]], axis=-1),
                hovertemplate="<b>%{y}</b><br>Paid in full: %{x:,} (%{customdata[1]:.0%})<extra></extra>")
    fig.add_bar(y=labels, x=c["co"], orientation="h", name="Charged off",
                marker=dict(color=RISK, line=dict(color=SURFACE, width=1)),
                text=[f"{int(n_):,} · {r:.0%} failed" for n_, r in zip(c["n"], c["rate"])], textposition="outside",
                textfont=dict(color=TEXT_2, size=11), cliponaxis=False,
                customdata=np.stack([c["n"], c["rate"]], axis=-1),
                hovertemplate="<b>%{y}</b><br>Charged off: %{x:,} (%{customdata[1]:.0%})"
                              "<br>%{customdata[0]:,} loans in total<extra></extra>")
    fig.update_layout(barmode="stack", bargap=0.3, showlegend=False, margin=dict(l=10, r=14, t=10, b=10))
    fig.update_xaxes(showgrid=True, tickformat="~s", title_text="Loans", range=[0, c["n"].max() * 1.35])
    fig.update_yaxes(showgrid=False)
    top = c.iloc[-1]
    share = c["n"].sum() / len(d)
    title = (f"{labels.iloc[-1]} led {name} with {int(top['n']):,} loans, {top['rate']:.0%} of them charged off; "
             f"the top 10 cities made {share:.0%} of the state's loans")
    return fig, title


def _amounts(d, state, name, min_n):
    # benchmark: the state with the lowest charge-off rate (enough loans to be stable); if the selected
    # state is that state, compare it with the next safest instead
    rates = D.rate_by(D.DF, "State")
    rates = rates[rates["n"] >= min_n].sort_values("rate")
    is_safest = str(rates.iloc[0]["State"]) == state
    rates = rates[rates["State"] != state]
    bench = rates.iloc[0]
    b_code = str(bench["State"])
    b_name, b_rate = D.STATE_NAMES[b_code], float(bench["rate"])
    other = D.DF[D.DF["State"] == b_code]
    # wide log bands: many loans sit on round amounts ($50k, $100k), which makes fine bins spiky
    edges = np.logspace(np.log10(5e3), np.log10(5e6), 16)
    mids = np.sqrt(edges[:-1] * edges[1:])
    fig = go.Figure()
    meds = {}
    for frame, label, color, width, alpha in ((other, b_name, SAFE, 2, 0.14),
                                              (d, name, COUNT, 2.5, 0.22)):
        v = frame["DisbursementGross"].clip(edges[0], edges[-1] * 0.999)
        share = np.histogram(v, bins=edges)[0] / max(len(v), 1)
        line_area(fig, mids, share, color, label, width=width, fill_opacity=alpha,
                  customdata=np.stack([edges[:-1], edges[1:]], axis=-1),
                  hovertemplate=f"<b>{label}</b><br>%{{customdata[0]:$,.0f}}–%{{customdata[1]:$,.0f}}: "
                                f"%{{y:.1%}} of loans<extra></extra>")
        meds[label] = frame["DisbursementGross"].median()
    for label, color, ypos in ((b_name, SAFE, 0.84), (name, COUNT, 0.96)):
        fig.add_vline(x=meds[label], line=dict(color=color, width=1, dash="4px,3px"))
        fig.add_annotation(x=np.log10(meds[label]), y=ypos, yref="paper", text=f"{label} median {money(meds[label])}",
                           showarrow=False, xanchor="left", xshift=4, font=dict(color=INK if label == name else SAFE,
                                                                                 size=11))
    fig.update_layout(showlegend=False, hovermode="x unified", margin=dict(l=10, r=10, t=14, b=10))
    ticks = [5e3, 1e4, 2.5e4, 5e4, 1e5, 2.5e5, 5e5, 1e6, 2.5e6, 5e6]
    fig.update_xaxes(type="log", title_text="Loan amount (disbursed)", tickvals=ticks,
                     ticktext=["$5k", "$10k", "$25k", "$50k", "$100k", "$250k", "$500k", "$1M", "$2.5M", "$5M"])
    fig.update_yaxes(tickformat=".0%", title_text="Share of loans", rangemode="tozero")
    a, b = meds[name], meds[b_name]
    sel_rate = d["Default"].mean()
    title = (f"{name}'s median loan was {money(a)} ({sel_rate:.0%} charged off) vs {money(b)} in {b_name}, "
             f"the {'next-' if is_safest else ''}safest state with {min_n:,}+ loans ({b_rate:.1%})")
    return fig, title


def _trend(d, name):
    nat = D.rate_by(D.DF, "ApprovalFY")
    q = D.rate_by(d, "ApprovalFY")
    q = q[q["n"] >= 30]
    fig = go.Figure()
    line_area(fig, nat["ApprovalFY"], nat["rate"], NEUTRAL, "National", width=2, fill_opacity=0.1,
              hovertemplate="National: %{y:.1%}<extra></extra>")
    line_area(fig, q["ApprovalFY"], q["rate"], COUNT, name, width=2.5, fill_opacity=0.2, customdata=q["n"],
              hovertemplate=f"{name}: %{{y:.1%}} (%{{customdata:,}} loans)<extra></extra>")
    boom_band(fig)
    style_timeseries(fig)
    fig.update_layout(showlegend=False, margin=dict(l=10, r=16, t=22, b=10))
    fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    fig.update_xaxes(**YEAR_TICKS)
    boom_s = d.loc[d["Era"] == "2005–08", "Default"].mean()
    boom_n = D.DF.loc[D.DF["Era"] == "2005–08", "Default"].mean()
    if np.isnan(boom_s):
        return fig, f"{name} vs the national charge-off rate"
    gap = (boom_s - boom_n) * 100
    return fig, (f"{name}'s 2005–08 loans failed at {boom_s:.0%}, {abs(gap):.0f} {'pt' if round(abs(gap)) == 1 else 'pts'} "
                 f"{'above' if gap > 0 else 'below'} the {boom_n:.0%} national rate for those years")


def _local(d, name):
    parts = []
    for col_, mapping in (("Area", {"Urban": "Urban", "Rural": "Rural"}),
                          ("StateSame", {1: "In-state lender", 0: "Out-of-state lender"})):
        g = D.rate_by(d[d[col_].isin(list(mapping))], col_)
        g["label"] = g[col_].map(mapping)
        parts.append(g)
    loc = pd.concat(parts, ignore_index=True).set_index("label") \
        .reindex(["Urban", "Rural", "In-state lender", "Out-of-state lender"]).dropna(subset=["n"]).reset_index()
    fig = risk_bars(loc, "label", NATIONAL, avg_label="National")
    fig.data[0].text = [f"{r:.1%}<br>{int(m):,} loans" for r, m in zip(loc["rate"], loc["n"])]
    if len(loc) == 4:
        fig.add_vline(x=1.5, line=dict(color=AXIS, width=1, dash="dot"))
    li = loc.set_index("label")
    own = (d["StateSame"] == 1).mean()
    if {"In-state lender", "Out-of-state lender"} <= set(li.index):
        ratio = li.loc["Out-of-state lender", "rate"] / max(li.loc["In-state lender", "rate"], 1e-9)
        title = (f"{own:.0%} of {name}'s loans came from in-state lenders; loans from out-of-state lenders failed "
                 f"{ratio:.1f}× as often")
    else:
        title = f"{name}: location type and lender base"
    return fig, title


@callback(
    Output("geo-kpis", "children"),
    Output("geo-map", "figure"), Output("geo-map-title", "children"),
    Output("geo-rank", "figure"), Output("geo-rank-title", "children"),
    Output("geo-prompt", "style"), Output("geo-prompt", "children"), Output("geo-state-section", "style"),
    Output("geo-cities", "figure"), Output("geo-cities-title", "children"),
    Output("geo-amount", "figure"), Output("geo-amount-title", "children"),
    Output("geo-trend", "figure"), Output("geo-trend-title", "children"),
    Output("geo-local", "figure"), Output("geo-local-title", "children"),
    Output("geo-insights", "children"),
    Input("geo-state", "value"), Input("geo-map-metric", "value"), Input("geo-min", "value"),
)
@D.memo()
def update(state, metric, min_n=DEFAULT_MIN):
    min_n = min_n or DEFAULT_MIN
    inc = _included(min_n)
    dropped = state if (state and state not in inc) else None
    if dropped:  # a state below the minimum is left out of the analysis
        state = None
    d = D.DF[D.DF["State"] == state] if state else D.DF[D.DF["State"].isin(inc)]
    name = D.STATE_NAMES.get(state, "All states") if state else "All states"
    n = len(d)
    co = int(d["Default"].sum())
    rate = co / n
    disb, lost = d["DisbursementGross"].sum(), d["ChgOffPrinGr"].sum()
    cities = d["CityST"].nunique()
    top10 = d["CityST"].value_counts().head(10).sum() / n
    kpis = [
        kpi("Loans", num(n), name if state else f"{len(inc)} states with {min_n:,}+ loans", tone="count"),
        kpi("Charge-off rate", pct(rate), f"national {NATIONAL:.1%} · {(rate - NATIONAL) * 100:+.1f} pts", tone="risk"),
        kpi("Money lent", money(disb), f"avg {money(d['DisbursementGross'].mean())} per loan", tone="money"),
        kpi("Principal charged off", money(lost), f"{lost / disb:.1%} of dollars lent", tone="risk"),
        kpi("Cities", num(cities), f"top 10 cities = {top10:.0%} of loans", tone="count"),
    ]
    mp, map_title, ok = _map(metric, state, min_n)
    rk, rank_title = _rank(ok, min_n)

    ins = [
        insight([html.B("Sun Belt boom states stand out. "),
                 "Florida, Arizona, Nevada and Georgia, the centre of the housing bubble, have the highest charge-off "
                 "rates; the Plains and Mountain states (the Dakotas, Montana, Wyoming) the lowest."], "warn"),
        insight([html.B("Local lending was safer. "),
                 "Borrowers who used a bank in their own state failed far less often; out-of-state lending was dominated "
                 "by large national banks running high-volume, small-ticket programmes."]),
    ]
    if not state:
        e = empty_fig("Select a state")
        if dropped:
            prompt = insight([html.B(f"{D.STATE_NAMES[dropped]} is left out. "),
                              f"It has fewer than {min_n:,} loans. Lower the minimum or pick another state."], "warn")
        else:
            prompt = insight([html.B("Pick a state to look inside it. "),
                              "Choose one in the filter above or click it on the map to see its top cities, how its "
                              "loan sizes compare with the safest state, its charge-off trend and which lenders served it."])
        return (kpis, mp, map_title, rk, rank_title, {}, prompt, {"display": "none"}, e, "", e, "", e, "", e, "", ins)

    cf, ct = _cities(d, name)
    af, at = _amounts(d, state, name, min_n)
    tf, tt = _trend(d, name)
    lf, lt = _local(d, name)
    return (kpis, mp, map_title, rk, rank_title, {"display": "none"}, no_update, {}, cf, ct, af, at, tf, tt, lf, lt, ins)
