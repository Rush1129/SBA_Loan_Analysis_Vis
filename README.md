# SBA Loan Risk Atlas

An interactive Plotly Dash dashboard that tells the story of 456,939 historical SBA loans (FY1987–2014):
which ones failed, when, how much was lost, and which characteristics actually separated failed loans
from repaid ones.

## Run it

```bash
pip install -r requirements.txt
python app.py
```

Then open <http://127.0.0.1:8050>. The first launch converts `cleaned_SBA.csv` into a typed Parquet cache
(`sba_cache.parquet`, about 10 s). After that the app starts in about 2 s. The cache rebuilds itself if the CSV changes.

## The story in five findings

1. **Timing dominated everything.** Loans approved in 2005–08 charged off at 38%, 4× the rate of all other years.
   Lending peaked in FY2006; the losses landed about four years later, peaking in 2010.
2. **Who lent the money mattered.** Ten lenders made half of all loans. Among large lenders, charge-off rates ranged
   from 6% (First Niagara) to 73% (Superior Financial Group). Out-of-state lenders did worse than local ones in every era.
3. **Small loans with a thin guarantee were riskiest.** The boom was an SBAExpress boom: 50%-guarantee loans went from
   about 2% of approvals in the 1990s to 86% in FY2005. Loans of $50k or less failed 3.3× as often as loans over $1M,
   and lost 74% of the money when they did.
4. **Some "drivers" are illusions.** LowDoc loans look 4.6× safer overall but are no safer within the same era
   (Simpson's paradox). Urban/rural and jobs retained mostly reflect when the loan was recorded. Business age carries
   almost no signal (21.5% vs 21.6%).
5. **The term field is a trap.** 92% of charged-off loans have an odd term length (26, 54 months …) versus 14% of repaid
   loans, so term was very likely updated after default. It is flagged and excluded from the Risk Explorer.

## Pages

| Page | Question | Key visuals |
|---|---|---|
| **Overview** | How many loans failed, when, and what did it cost? | 5 KPIs ($ lent, $ lost, SBA share), outcome pie, loan volume by year (total / paid in full / charged off), approval-year charge-off trend with CI band, money lent vs money lost by year, time-to-failure histogram |
| **Geography** | Where were the borrowers, and where did loans fail? | State filter (or click the map), state map with metric toggle, 8 riskiest / 8 safest states. With a state selected: its top 10 cities by loans (paid vs charged off), its loan-amount distribution vs other states, its charge-off trend vs national, and urban/rural and in-state vs out-of-state lenders |
| **Loans** | How do size and guarantee relate to failure and loss? | Rate by size, size × era heatmap, guarantee mix over time (a loss-severity histogram is built but hidden; set `SHOW_LOSS_CHART = True` in `pages/loans.py`) |
| **Lenders** | Did the lender matter? | Min.-loans filter (1k/5k/10k/20k): full-width bubble chart of lenders (below the minimum faded), largest-lender bars, lender × era heatmap, same-state vs out-of-state lenders |
| **Borrowers** | Industry and business profile | Min.-loans filter (1k/5k/10k/20k) that drops smaller industries from the page; industry rates, industry × era heatmap, urban vs rural and new vs existing across eras, workforce size, treemap of dollars lost by industry |
| **Risk Explorer** | How did loans like this one turn out? | Profile builder on the 5 strongest drivers, risk gauge, plain-language verdict with 95% CI, "100 loans like this" waffle vs all loans, cumulative failure curve by years since disbursement |
| **Data** | What do the records look like? | Search, outcome filter, column picker, server-side paging/sorting, summary stats, data-quality table, CSV download (≤ 100k rows) |

There are no dashboard-wide filters. Pages that need filtering have their own controls: the Geography page
(state, minimum loans per state), Lenders (minimum loans per lender), the Risk Explorer (loan profile), Borrowers (minimum loans per industry)
and Data (search, outcome, columns). Each page's results are cached and pre-computed at start-up, so switching pages is
fast.

## How the Risk Explorer inputs were chosen

Each candidate variable is scored with **Information Value (IV)**, the standard screening measure in credit scoring
(< 0.02 none, 0.02–0.1 weak, 0.1–0.3 medium, 0.3–0.5 strong, > 0.5 very strong). Because the 2005–08 boom raised
every group's rate, each variable is also scored **within each approval era** and averaged (the like-for-like score).
The Risk Explorer uses the five strongest drivers that are known at approval and not suspect:

| Driver | Like-for-like IV |
|---|---|
| Approval era | 0.88 (pooled) |
| Lender (25 largest + all others) | 0.28 |
| SBA guarantee share | 0.27 |
| Borrower state | 0.13 |
| Loan amount | 0.10 |

Left out on purpose: loan term (likely updated after default), days to disbursement (only known after approval),
lender's state (repeats the lender), and weak borrower traits such as business age or franchise status.

## Look and colour system

A minimal light theme ("Risk Atlas"): quiet grey ground, white cards with hairline borders, ink text in Geist, a
brand row plus a sticky tab bar with icons. Lines carry a faded gradient fill. Colour carries meaning, the same way on
every page:

- **Teal**: paid in full / safer than average
- **Rose**: charged off / riskier than average
- **Slate**: dollars lent
- **Blue**: loan counts and neutral comparison groups (then amber, violet, sea for other groups)
- **Risk scale**: diverging teal → light grey → rose, centred on the average charge-off rate (log ratio, so 2.2× the
  average is full rose and 1/2.2 is full teal). "About average" reads as neutral grey.

Teal and rose were checked for colour-vision-deficiency separation on the white surface. Every chart title states the
finding, computed live from the current filters. The full rules for adding pages and charts are in
[DESIGN.md](DESIGN.md).

## Caveats

- Recent cohorts (2011–14) had less time to default, so their rates are understated.
- FY1987–88 have fewer than 1,000 loans each.
- "SBA's share of losses" is an estimate: principal charged off × guarantee share.
- All patterns are historical associations, not causes, and the Risk Explorer is not a credit model.

## Files

```
app.py            layout, navigation, global filters, routing
data.py           loading + Parquet cache, derived fields, filtering, Wilson CI, Information Value
theme.py          design tokens, risk scale, Plotly template, chart helpers (line_area, boom_band, …)
charts.py         shared builders (risk bars, risk heatmap, era lines)
components.py     KPI tiles (+ mini bars/sparklines), chart cards with live headline titles, keys, insights
pages/            overview, geography, loans, lenders, borrowers, risk, explorer
assets/style.css  "Risk Atlas" minimal light theme
DESIGN.md         design system: tokens, components, chart rules, recipe for new charts
SBA_EDA.ipynb     exploratory notebook with ~70 static graphs (matplotlib/seaborn)
```
