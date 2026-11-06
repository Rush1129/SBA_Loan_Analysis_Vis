"""Data Explorer — server-side paged table, summary statistics and CSV download."""
import pandas as pd
from dash import Input, Output, State, callback, dash_table, dcc, html

import data as D
from components import kpi, num, page_header, pct, seg
from theme import FONT, INK, LINE, PAGE, RISK_INK, SAFE, SUBTLE

PAGE_SIZE = 15
DOWNLOAD_CAP = 100_000
DEFAULT_COLS = ["Name", "City", "State", "Bank", "Industry", "ApprovalFY", "DisbursementGross", "GuarPct",
                "Outcome", "ChgOffPrinGr", "MonthsToCO"]
NUMERIC = ["DisbursementGross", "GrAppv", "SBA_Appv", "GuarPct", "Term", "NoEmp", "CreateJob", "RetainedJob",
           "ChgOffPrinGr", "MonthsToCO"]
_MISSING = None


def _missing():
    global _MISSING
    if _MISSING is None:
        rows, miss = D.missing_summary()
        _MISSING = pd.DataFrame({"Column": list(miss), "Missing": list(miss.values())})
        _MISSING["Share"] = (_MISSING["Missing"] / rows).map(lambda v: f"{v:.1%}")
        _MISSING["Missing"] = _MISSING["Missing"].map("{:,}".format)
        _MISSING["Note"] = _MISSING["Column"].map({
            "ChgOffDate": "Expected — only charged-off loans have a charge-off date",
            "SBA_Appv": "Imputed from GrAppv × median guarantee share",
            "SBA_AppvPct": "Imputed with the median",
        }).fillna("")
    return _MISSING


def layout():
    return html.Div([
        page_header("Data explorer", "Inspect the records",
                    "Search, sort and page through all loans, then download the matching records."),
        html.Div(className="card toolbar", children=[
            dcc.Input(id="dx-search", type="search", placeholder="Search business, city or bank…", debounce=True,
                      className="search"),
            seg("dx-outcome", [{"label": "All outcomes", "value": "All"},
                               {"label": "Paid in full", "value": "Paid in Full"},
                               {"label": "Charged off", "value": "Charged Off"}], "All"),
            dcc.Dropdown(id="dx-cols", options=D.TABLE_COLUMNS, value=DEFAULT_COLS, multi=True,
                         className="dd cols-dd", placeholder="Columns"),
            html.Button("Download CSV", id="dx-dl-btn", className="btn-primary"),
            dcc.Download(id="dx-download"),
        ]),
        html.Div(id="dx-kpis", className="kpi-row kpi-row-4"),
        html.Div(className="card table-card", children=[
            dash_table.DataTable(
                id="dx-table", page_current=0, page_size=PAGE_SIZE, page_action="custom",
                sort_action="custom", sort_mode="single", sort_by=[],
                style_as_list_view=True,
                style_table={"overflowX": "auto"},
                style_header={"backgroundColor": PAGE, "color": INK, "fontWeight": 600, "fontFamily": FONT,
                              "border": "none", "borderBottom": f"1px solid {LINE}", "padding": "10px 12px"},
                style_cell={"backgroundColor": "#FFFFFF", "color": INK, "border": "none",
                            "borderBottom": "1px solid #EEF0F3", "fontFamily": FONT,
                            "fontSize": 13, "padding": "9px 12px", "textAlign": "left",
                            "maxWidth": 260, "overflow": "hidden", "textOverflow": "ellipsis",
                            "fontVariantNumeric": "tabular-nums"},
                style_data_conditional=[
                    {"if": {"filter_query": '{Outcome} = "Charged Off"', "column_id": "Outcome"}, "color": RISK_INK, "fontWeight": 600},
                    {"if": {"filter_query": '{Outcome} = "Paid in Full"', "column_id": "Outcome"}, "color": SAFE, "fontWeight": 600},
                    {"if": {"row_index": "odd"}, "backgroundColor": "#FAFBFC"},
                    {"if": {"state": "active"}, "backgroundColor": SUBTLE, "border": f"1px solid {INK}"},
                ],
            ),
        ]),
        html.Div(className="grid grid-2", children=[
            html.Div(className="card", children=[
                html.Div(className="card-head", children=[html.Div([html.H3("Summary statistics"),
                                                                    html.P("Numeric columns for the selection")])]),
                html.Div(id="dx-stats"),
            ]),
            html.Div(className="card", children=[
                html.Div(className="card-head", children=[html.Div([html.H3("Data quality"),
                                                                    html.P("Missing values in cleaned_SBA.csv")])]),
                html.Div(id="dx-quality"),
            ]),
        ]),
    ])


def _subset(filters, search, outcome):
    d = D.filtered(filters)
    if outcome in D.OUTCOMES:
        d = d[d["Outcome"] == outcome]
    if search:
        s = search.strip()
        m = (d["Name"].str.contains(s, case=False, na=False, regex=False)
             | d["City"].str.contains(s, case=False, na=False, regex=False)
             | d["Bank"].str.contains(s, case=False, na=False, regex=False))
        d = d[m]
    return d


def _mini_table(df):
    return dash_table.DataTable(
        data=df.to_dict("records"), columns=[{"name": c, "id": c} for c in df.columns],
        style_as_list_view=True,
        style_header={"backgroundColor": PAGE, "color": INK, "fontWeight": 600, "border": "none",
                      "borderBottom": f"1px solid {LINE}", "fontFamily": FONT},
        style_cell={"backgroundColor": "#FFFFFF", "color": INK, "border": "none", "borderBottom": "1px solid #EEF0F3",
                    "fontFamily": FONT, "fontSize": 12.5, "padding": "7px 10px",
                    "textAlign": "right", "fontVariantNumeric": "tabular-nums", "whiteSpace": "normal"},
        style_cell_conditional=[{"if": {"column_id": c}, "textAlign": "left"} for c in ("Column", "Note")],
    )


@callback(
    Output("dx-table", "data"), Output("dx-table", "columns"), Output("dx-table", "page_count"),
    Output("dx-kpis", "children"), Output("dx-stats", "children"), Output("dx-quality", "children"),
    Input("filters", "data"), Input("dx-search", "value"), Input("dx-outcome", "value"),
    Input("dx-cols", "value"), Input("dx-table", "page_current"), Input("dx-table", "sort_by"),
)
def update(filters, search, outcome, cols, page, sort_by):
    d = _subset(filters, search, outcome)
    cols = cols or DEFAULT_COLS
    if sort_by:
        col = sort_by[0]["column_id"]
        d = d.sort_values(col, ascending=sort_by[0]["direction"] == "asc", kind="stable")
    page = page or 0
    view = d.iloc[page * PAGE_SIZE:(page + 1) * PAGE_SIZE][cols].copy()
    for c in view.columns:
        if str(view[c].dtype) in ("category", "string"):
            view[c] = view[c].astype(str)
    columns = []
    for c in cols:
        spec = {"name": c, "id": c}
        if c in ("DisbursementGross", "GrAppv", "SBA_Appv", "ChgOffPrinGr"):
            spec.update(type="numeric", format=dash_table.FormatTemplate.money(0))
        columns.append(spec)

    n = len(d)
    rate = d["Default"].mean() if n else 0
    kpis = [
        kpi("Matching records", num(n), tone="count"),
        kpi("Charge-off rate", pct(rate) if n else "—", tone="risk"),
        kpi("Median loan", f"${d['DisbursementGross'].median():,.0f}" if n else "—", tone="money"),
        kpi("Download", f"{min(n, DOWNLOAD_CAP):,} rows", "capped at 100k" if n > DOWNLOAD_CAP else "all rows"),
    ]
    if n:
        st = d[NUMERIC].describe(percentiles=[0.5]).T[["mean", "50%", "min", "max", "std"]]
        st.columns = ["Mean", "Median", "Min", "Max", "Std"]
        st = st.map(lambda v: f"{v:,.1f}" if abs(v) < 100 else f"{v:,.0f}").reset_index().rename(columns={"index": "Column"})
        stats = _mini_table(st)
    else:
        stats = html.P("No rows.", className="muted")
    return view.to_dict("records"), columns, max(1, -(-n // PAGE_SIZE)), kpis, stats, _mini_table(_missing())


@callback(
    Output("dx-download", "data"), Input("dx-dl-btn", "n_clicks"),
    State("filters", "data"), State("dx-search", "value"), State("dx-outcome", "value"), State("dx-cols", "value"),
    prevent_initial_call=True,
)
def download(_, filters, search, outcome, cols):
    d = _subset(filters, search, outcome).head(DOWNLOAD_CAP)
    return dcc.send_data_frame(d[cols or DEFAULT_COLS].to_csv, "sba_filtered.csv", index=False)
