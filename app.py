"""SBA Loan Risk Atlas — interactive Dash dashboard.

Run:  python app.py   then open http://127.0.0.1:8050
Design rules (colours, chart style, components) live in DESIGN.md.
"""
from dash import Dash, Input, Output, dcc, html

import data as D
import theme  # noqa: F401  (registers the Plotly template)
from pages import borrowers, explorer, geography, lenders, loans, overview, risk

# (path, tab label, module). The divider in the tab bar sits before the first tool page.
PAGES = [
    ("/", "Overview", overview),
    ("/geography", "Geography", geography),
    ("/loans", "Loans", loans),
    ("/lenders", "Lenders", lenders),
    ("/borrowers", "Borrowers", borrowers),
    ("/risk", "Risk explorer", risk),
    ("/data", "Data", explorer),
]
TOOLS_START = "/risk"

app = Dash(
    __name__, title="SBA Loan Risk Atlas", suppress_callback_exceptions=True,
    external_stylesheets=["https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700"
                          "&family=Geist+Mono:wght@400;500&display=swap"],
)
server = app.server


def _nav_id(path):
    return "nav-" + (path.strip("/") or "overview")


def topbar():
    return html.Header(className="topbar", children=html.Div(className="topbar-inner topbar-row", children=[
        html.Div(className="brand", children=[
            html.Div(className="brand-mark", children=[html.Span(), html.Span(), html.Span()]),
            html.Div([html.Div("Risk Atlas", className="brand-name"),
                      html.Div("SBA 7(a) loans", className="brand-sub")]),
        ]),
        html.Div(className="topbar-meta", children=[
            html.Span(className="pill pill-data", children=[
                html.Span([html.B(f"{D.N_ALL:,}"), f" loans with a known outcome · FY{D.YEAR_MIN}–{D.YEAR_MAX}"])]),
            html.Span(className="pill", children=[
                html.Span(className="live-dot"), html.Span(["All-loan charge-off rate ", html.B(f"{D.BASE_RATE:.1%}")])]),
        ]),
    ]))


def tabs():
    links = []
    for path, label, _ in PAGES:
        if path == TOOLS_START:
            links.append(html.Span(className="nav-divider", **{"aria-hidden": "true"}))
        links.append(dcc.Link(label, href=path, id=_nav_id(path), className="nav-link"))
    return html.Nav(className="tabs", **{"aria-label": "Pages"},
                    children=html.Div(className="topbar-inner nav", children=links))


app.layout = html.Div(className="app", children=[
    dcc.Location(id="url"),
    # Pages read their data through this store; it always holds the full dataset (no global filters).
    dcc.Store(id="filters", data=D.DEFAULT_FILTERS),
    topbar(),
    tabs(),
    html.Div(id="shell", className="shell", children=[html.Main(id="page", className="page")]),
])


@app.callback(
    Output("page", "children"),
    *[Output(_nav_id(p), "className") for p, _, _ in PAGES],
    Input("url", "pathname"),
)
def route(path):
    path = path if path in {p for p, _, _ in PAGES} else "/"
    mod = next(m for p, _, m in PAGES if p == path)
    nav = ["nav-link active" if p == path else "nav-link" for p, _, _ in PAGES]
    return mod.layout(), *nav


def warm_up():
    """Pre-compute every page's default view in the background so first visits are fast."""
    f = D.DEFAULT_FILTERS
    jobs = [lambda: overview.update(f), lambda: geography.update(None, "rate", 1000),
            lambda: loans.update(f), lambda: lenders.update(f, 1000),
            lambda: borrowers.update(f, 1000),
            lambda: risk.update(*[risk.PRESETS["boom"].get(k, risk.ANY) for k in risk.FIELDS])]
    for job in jobs:
        try:
            job()
        except Exception as exc:  # warm-up must never stop the app
            print("warm-up skipped:", exc)


if __name__ == "__main__":
    import threading
    threading.Thread(target=warm_up, daemon=True).start()
    import os
    app.run(debug=False, port=int(os.environ.get("PORT", 8050)))
