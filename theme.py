"""Design tokens and the shared Plotly template ("Risk Atlas" minimal light theme).

Read DESIGN.md before adding a chart. The short version:

* Colour always carries meaning and comes from the tokens below, never a new hex.
  SAFE (teal) = paid in full / safer than average · RISK (rose) = charged off / riskier
  · MONEY (slate) = dollars lent · COUNT (blue) = loan counts / a neutral comparison group.
* Ink, not colour, for text: values and labels use TEXT / TEXT_2 / MUTED; rose text uses RISK_INK.
* Risk scale = diverging teal → grey → rose centred on the average charge-off rate,
  so "about average" reads as neutral grey.
* Lines get a faded gradient fill (``line_area``), the 2005–08 boom gets an ink band
  (``boom_band``), the average gets a dashed reference line (``base_rate_line``).

Palette validated with the dataviz validator on a white surface (light mode):
SAFE↔RISK CVD ΔE 10.5 (protan, ≥8 target); CATEGORICAL passes every adjacent check
(worst CVD ΔE 16.0, normal-vision 24.6). RISK and AMBER sit under 3:1 contrast on
white, so charts using them as thin marks carry direct labels or hover text.
"""
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
from plotly.colors import sample_colorscale

# ---- surfaces & ink ---------------------------------------------------------
SURFACE = "#FFFFFF"      # cards
PAGE = "#F6F7F9"         # page ground
SUBTLE = "#F1F3F6"       # hover wash, segmented-control track
LINE = "#E6E8EC"         # card borders
INK = "#0E1116"          # primary text, "Total" series, reference marks
TEXT = INK
TEXT_2 = "#4A5261"       # secondary text
MUTED = "#646B78"        # captions, axis ticks (4.5:1 on PAGE)
GRID = "#DCE0E6"         # dashed horizontal gridlines
AXIS = "#D5D9E0"         # baseline
NAVY = INK               # legacy alias: older code used NAVY for "ink"

# ---- semantic data colours --------------------------------------------------
SAFE = "#00705F"         # paid in full / safer
SAFE_SOFT = "#BFE0D9"
SAFE_INK = SAFE          # 6:1 on white, safe as text
RISK = "#F06A8A"         # charged off / riskier
RISK_SOFT = "#FBD5DE"
RISK_MID = "#F494AB"     # second step of RISK (e.g. the tail after a median)
RISK_INK = "#B02A4E"     # rose text (6.5:1 on white)
MONEY = "#8A93A3"        # dollars lent (dots, lines)
MONEY_SOFT = "#D3D8E1"   # dollars lent (bars, areas)
NEUTRAL = "#9AA3B2"      # "national" / "regular" comparison series

# ---- identity colours (categories with no good/bad meaning), fixed order ----
COUNT = "#3D5CC4"        # blue: loan counts / first comparison group
AMBER = "#D98A0B"        # second comparison group
VIOLET = "#8A5CD6"
SEA = "#2A9D8F"
CATEGORICAL = [COUNT, AMBER, VIOLET, SEA]

OUTCOME_COLORS = {"Paid in Full": SAFE, "Charged Off": RISK}

# ---- scales -----------------------------------------------------------------
# Diverging risk scale: far below average → average → far above average
RISK_SCALE = [
    [0.0, "#004F44"], [0.25, "#1E8A78"], [0.44, "#A9D6CD"],
    [0.5, "#E8E9EE"],
    [0.56, "#F8BFCC"], [0.75, "#EC5F82"], [1.0, "#A3244A"],
]
# Sequential scales for magnitudes (one hue, light → dark)
MONEY_SCALE = [[0, "#F1F3F6"], [0.35, "#C9CFD9"], [0.7, "#8A93A3"], [1, "#3B4250"]]
COUNT_SCALE = [[0, "#EEF1FB"], [0.35, "#B9C5EE"], [0.7, "#6F86D6"], [1, "#2A3F8F"]]
LOSS_SCALE = [[0, "#FDEEF2"], [0.4, "#F8BFCC"], [0.75, "#EC5F82"], [1, "#8E1F3F"]]

BOOM = (2004.5, 2008.5)                  # FY2005–08 on a fiscal-year axis
BOOM_FILL = "rgba(14,17,22,0.035)"       # ink wash, never red

FONT = "Geist, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif"
MONO = "'Geist Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

pio.templates["sba"] = go.layout.Template(
    layout=dict(
        font=dict(family=FONT, color=TEXT_2, size=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=[SAFE, RISK, COUNT, AMBER, VIOLET, SEA],
        margin=dict(l=10, r=16, t=12, b=10),
        hoverlabel=dict(bgcolor=INK, bordercolor=INK, align="left",
                        font=dict(family=FONT, color="#FFFFFF", size=12)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, traceorder="normal",
                    bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_2, size=12)),
        xaxis=dict(showgrid=False, gridcolor=GRID, griddash="3px,3px", showline=True, linecolor=AXIS,
                   zeroline=False, ticks="", tickfont=dict(color=MUTED, size=11),
                   title=dict(font=dict(color=TEXT_2, size=12)), automargin=True),
        yaxis=dict(showgrid=True, gridcolor=GRID, griddash="3px,3px", showline=False, linecolor=AXIS,
                   zeroline=False, ticks="", tickfont=dict(color=MUTED, size=11),
                   title=dict(font=dict(color=TEXT_2, size=12)), automargin=True),
        bargap=0.28,
        barcornerradius=4,
        hovermode="closest",
        annotationdefaults=dict(font=dict(color=TEXT_2, size=11), arrowcolor=MUTED, arrowwidth=1),
    ),
    data=dict(
        bar=[go.Bar(marker=dict(line=dict(width=0)))],
        pie=[go.Pie(hole=0.62, sort=False, marker=dict(line=dict(color=SURFACE, width=3)))],
        heatmap=[go.Heatmap(xgap=3, ygap=3)],
    ),
)
pio.templates.default = "sba"

GRAPH_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]}

RISK_SPAN = np.log(2.2)  # 2.2× the average = full rose, 1/2.2 of it = full teal


def rgba(hex_color, a):
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def mix(hex_color, other="#FFFFFF", t=0.5):
    """Blend ``hex_color`` toward ``other`` by ``t`` (0 = unchanged, 1 = other)."""
    a = [int(hex_color.lstrip("#")[k:k + 2], 16) for k in (0, 2, 4)]
    b = [int(other.lstrip("#")[k:k + 2], 16) for k in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))


def risk_pos(rate, base):
    """Position on RISK_SCALE (0..1) for a rate relative to the baseline, on a log-ratio axis."""
    r = np.clip(np.asarray(rate, dtype=float), 1e-4, None)
    return np.clip(0.5 + 0.5 * np.log(r / base) / RISK_SPAN, 0, 1)


def risk_colors(rates, base):
    pos = np.atleast_1d(risk_pos(rates, base))
    return sample_colorscale(RISK_SCALE, [float(p) for p in pos])


def text_on(pos):
    """Readable label colour for a cell at position ``pos`` on RISK_SCALE."""
    return "#FFFFFF" if (pos < 0.3 or pos > 0.72) else TEXT


def risk_colorbar(base, title="Charge-off"):
    mults = [1 / 2.2, 0.7, 1, 1.5, 2.2]
    return dict(title=dict(text=title, font=dict(color=TEXT_2, size=11)),
                tickvals=[float(risk_pos(base * m, base)) for m in mults],
                ticktext=[f"{base * m:.0%}" + (" avg" if m == 1 else "") for m in mults],
                thickness=10, len=0.75, outlinewidth=0, tickfont=dict(color=MUTED, size=11))


def base_rate_line(fig, rate, orientation="h", label="Average", row=None, col=None):
    """Reference line for the charge-off rate: 1px dashed ink, labelled in place."""
    kw = dict(line=dict(color=rgba(INK, 0.5), width=1, dash="4px,3px"),
              annotation_text=f"{label} {rate:.1%}", annotation_font=dict(color=TEXT_2, size=11))
    if row is not None:
        kw.update(row=row, col=col)
    if orientation == "h":
        fig.add_hline(y=rate, annotation_position="top right", **kw)
    else:
        kw["annotation"] = dict(y=1.0, yref="paper", yanchor="bottom", xanchor="left")
        fig.add_vline(x=rate, **kw)
    return fig


def boom_band(fig, label="2005–08 boom", row=None, col=None):
    """Shade FY2005–08 with a faint ink wash and label it at the top of the plot."""
    kw = {} if row is None else dict(row=row, col=col)
    fig.add_vrect(x0=BOOM[0], x1=BOOM[1], fillcolor=BOOM_FILL, line_width=0, layer="below", **kw)
    if label:
        fig.add_annotation(x=sum(BOOM) / 2, y=1, yref="y domain" if row in (None, 1) else f"y{row} domain",
                           text=label, showarrow=False, yanchor="bottom", font=dict(color=MUTED, size=11))
    return fig


def line_area(fig, x, y, color, name, width=2, fill=True, fill_opacity=0.2, row=None, col=None, **kw):
    """A line with the house faded gradient fill (colour at the top fading to clear at zero)."""
    trace = dict(x=x, y=y, mode="lines", name=name, line=dict(color=color, width=width), **kw)
    if fill:
        ys = np.asarray(y, dtype=float)
        trace.update(fill="tozeroy", fillcolor=rgba(color, 0),
                     fillgradient=dict(type="vertical", start=0, stop=float(np.nanmax(ys)) if len(ys) else 1,
                                       colorscale=[[0, rgba(color, 0)], [1, rgba(color, fill_opacity)]]))
    if row is not None:
        fig.add_scatter(**trace, row=row, col=col)
    else:
        fig.add_scatter(**trace)
    return fig


def style_timeseries(fig):
    """Hover a year to read every series: unified label plus a thin ink crosshair."""
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1,
                     spikecolor=rgba(INK, 0.3), spikedash="solid")
    return fig


def empty_fig(msg="No loans match this selection"):
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False, font=dict(color=MUTED, size=14),
                       xref="paper", yref="paper", x=0.5, y=0.5)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig
