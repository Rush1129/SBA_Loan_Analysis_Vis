"""Chart builders shared across pages. All rate charts colour marks on the diverging
risk scale relative to the selection's average, so colour alone says 'safer' or 'riskier'."""
import numpy as np
import plotly.graph_objects as go

import data as D
from theme import (INK, RISK_SCALE, SURFACE, TEXT_2, base_rate_line, rgba, risk_colorbar, risk_colors, risk_pos,
                   text_on)

HOVER_RATE = ("<b>%{customdata[0]}</b><br>Charge-off rate <b>%{customdata[1]:.1%}</b>"
              "<br>%{customdata[2]:,} of %{customdata[3]:,} loans charged off"
              "<br>Principal lost %{customdata[4]:$,.0f}<extra></extra>")


def _custom(g, cat):
    return np.stack([g[cat].astype(str), g["rate"], g["co"], g["n"], g["loss"]], axis=-1)


def risk_bars(g, cat, base, horizontal=False, show_ci=True, label_fmt="{:.1%}", avg_label="Average"):
    """Bars of charge-off rate per category, coloured by risk relative to ``base``."""
    labels = g[cat].astype(str)
    colors = risk_colors(g["rate"], base)
    err = dict(type="data", symmetric=False, array=g["hi"] - g["rate"], arrayminus=g["rate"] - g["lo"],
               color=rgba(INK, 0.4), thickness=1, width=0, visible=show_ci)
    text = [label_fmt.format(v) for v in g["rate"]]
    common = dict(marker=dict(color=colors, cornerradius=4), text=text, textposition="outside",
                  textfont=dict(color=TEXT_2, size=11), cliponaxis=False,
                  customdata=_custom(g, cat), hovertemplate=HOVER_RATE)
    if horizontal:
        fig = go.Figure(go.Bar(x=g["rate"], y=labels, orientation="h", error_x=err, **common))
        base_rate_line(fig, base, "v", avg_label)
        fig.update_xaxes(tickformat=".0%", showgrid=True,
                         range=[0, max(g["hi"].max() if show_ci else g["rate"].max(), base) * 1.18])
        fig.update_yaxes(showgrid=False, autorange="reversed")
        fig.update_layout(margin=dict(l=10, r=14, t=30, b=10), bargap=0.32)
    else:
        fig = go.Figure(go.Bar(x=labels, y=g["rate"], error_y=err, **common))
        base_rate_line(fig, base, "h", avg_label)
        fig.update_yaxes(tickformat=".0%", range=[0, max(g["hi"].max() if show_ci else g["rate"].max(), base) * 1.2])
        fig.update_xaxes(showgrid=False, type="category")
        fig.update_layout(margin=dict(l=10, r=10, t=22, b=10), bargap=0.38)
    return fig


def risk_heatmap(d, row, col, base, min_n=50, row_order=None, col_order=None, row_labels=None):
    """Charge-off rate for every row × column cell on the diverging risk scale."""
    g = d.groupby([row, col], observed=True)["Default"].agg(["size", "mean"]).reset_index()
    z = g.pivot(index=row, columns=col, values="mean")
    n = g.pivot(index=row, columns=col, values="size")
    if row_order is not None:
        z, n = z.reindex(row_order), n.reindex(row_order)
    if col_order is not None:
        z, n = z.reindex(columns=col_order), n.reindex(columns=col_order)
    z = z.where(n >= min_n)
    pos = np.where(z.notna(), risk_pos(z.fillna(base).values, base), np.nan)
    ylab = [str(r) for r in (row_labels or z.index)]
    xlab = [str(c) for c in z.columns]
    fig = go.Figure(go.Heatmap(
        z=pos, x=xlab, y=ylab, zmin=0, zmax=1, colorscale=RISK_SCALE, xgap=3, ygap=3,
        customdata=np.dstack([z.values, n.fillna(0).values]), hoverongaps=False,
        hovertemplate="<b>%{y}</b> · %{x}<br>Charge-off rate <b>%{customdata[0]:.1%}</b>"
                      "<br>%{customdata[1]:,.0f} loans<extra></extra>",
        colorbar=risk_colorbar(base),
    ))
    for i, yl in enumerate(ylab):
        for j, xl in enumerate(xlab):
            v = z.values[i, j]
            if np.isnan(v):
                continue
            fig.add_annotation(x=xl, y=yl, text=f"{v:.0%}", showarrow=False,
                               font=dict(size=11, color=text_on(pos[i, j])))
    fig.update_xaxes(showgrid=False, side="top", type="category", tickangle=0)
    fig.update_yaxes(showgrid=False, autorange="reversed", type="category")
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
    return fig


def era_lines(d, col, levels, colors, names=None, min_n=200):
    """Charge-off rate across credit-cycle eras, one line per level of ``col``."""
    fig = go.Figure()
    for lvl, c in zip(levels, colors):
        q = D.rate_by(d[d[col] == lvl], "Era")
        q = q[q["n"] >= min_n]
        name = (names or {}).get(lvl, str(lvl))
        fig.add_scatter(x=q["Era"].astype(str), y=q["rate"], mode="lines+markers+text", name=name,
                        line=dict(color=c, width=2.5), marker=dict(size=9, color=c, line=dict(color=SURFACE, width=2)),
                        text=[""] * (len(q) - 1) + [name] if len(q) else [], textposition="middle right",
                        textfont=dict(color=c, size=11), cliponaxis=False, showlegend=False,
                        customdata=np.stack([q["n"]], axis=-1) if len(q) else None,
                        hovertemplate=f"<b>{name}</b> · %{{x}}<br>%{{y:.1%}} charged off<br>%{{customdata[0]:,}} loans<extra></extra>")
    fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    fig.update_xaxes(showgrid=False, type="category", categoryorder="array", categoryarray=D.ERA_LABELS,
                     tickangle=0, tickfont=dict(size=10))
    fig.update_layout(margin=dict(l=10, r=78, t=16, b=10), hovermode="x unified")
    return fig
