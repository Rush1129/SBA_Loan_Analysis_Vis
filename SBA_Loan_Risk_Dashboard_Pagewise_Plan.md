# SBA Loan Risk Dashboard — Page-by-Page Plan

## Project Goal

Build an interactive dashboard to explore historical SBA loan outcomes and identify loan, business, industry, and geographic characteristics associated with different observed outcomes.

The main outcome variable is `MIS_Status`:
- `P I F` — Paid in Full
- `CHGOFF` — Charged Off
also I have added Default columns in it which represents number 0,1

The dashboard should emphasize historical patterns and associations. It should not claim that a variable causes a charge-off or that a particular loan should definitively be approved or rejected.

---

# Page 1 — Overview

## Purpose
Give users a high-level summary of SBA loan outcomes, geographic distribution, and changes over time. Geographic analysis is included on this page rather than having a separate map tab.

## Suggested layout
1. **Title and subtitle:** “SBA Loan Risk Analysis” / “Explore historical SBA loan performance and characteristics.”
2. **KPI cards:** Total loans with known outcomes, Paid-in-Full loans, Charged-Off loans, overall charge-off rate, total gross approved amount (optional), and average loan amount or average SBA guarantee percentage (optional).
3. **Middle row:** Loan outcome distribution (bar or donut chart) beside an interactive US state map showing charge-off rate.
4. **Bottom row:** Charge-off rate by approval year (line chart), with an optional horizontal bar chart of states with the highest rates.

## Analyses and visualizations

### A. Overall loan outcomes
- Variable: `MIS_Status`
- Chart: bar chart or donut chart
- Question: How many loans were Paid in Full versus Charged Off?
- Show counts and percentages where useful.

### B. Geographic variation
- Variables: `State`, `MIS_Status`
- Metric: charged-off loans divided by loans with known outcomes
- Chart: US choropleth map
- Hover details: state, total loans, paid-in-full loans, charged-off loans, and charge-off rate.
- Consider a minimum-loan threshold per state to reduce unstable rates from small samples.

### C. Historical trend
- Variables: `ApprovalFY`, `MIS_Status`
- Chart: line chart of charge-off rate by approval year
- Question: How has the observed charge-off rate varied across approval years?
- More recent loan cohorts may have had less time to experience charge-offs, so interpret year-to-year differences cautiously.

## Recommended filters
- Approval year range
- State (optional)
- Loan status (optional; default to all)

---

# Page 2 — Loan Analysis

## Purpose
Explore how loan characteristics are associated with historical loan outcomes.

## Suggested layout
- **KPI cards:** Number of loans in the current selection, average loan amount, median loan amount, and charge-off rate.
- **Four main charts:** Loan amount distribution; charge-off rate by loan-size category; loan amount by outcome; charge-off rate by loan-term category.
- **Optional lower section:** SBA guarantee percentage by outcome and amount not guaranteed by outcome.

## Analyses and visualizations

### A. Loan amount distribution
- Variable: `DisbursementGross`
- Chart: histogram
- Question: How are disbursed loan amounts distributed?
- Loan amounts may be highly skewed; consider a log scale or a clearly labelled display range if extreme values dominate.

### B. Charge-off rate by loan size
- Variable: `DisbursementGross`, grouped into bands such as up to $50k, $50k–$100k, $100k–$250k, $250k–$500k, and above $500k
- Chart: bar chart
- Question: Does the observed charge-off rate vary across loan-size categories?

### C. Loan amount by loan outcome
- Variables: `DisbursementGross`, `MIS_Status`
- Chart: boxplot
- Question: How do loan-amount distributions differ between Paid-in-Full and Charged-Off loans?

### D. Loan term and outcome
- Variables: `Term`, `MIS_Status`
- Metric: charge-off rate by term group
- Chart: bar chart
- Example groups: up to 60, 61–120, 121–180, 181–240, and above 240 months
- Question: Does observed loan performance vary with loan duration?

### E. Gross approval versus SBA-guaranteed amount
- Variables: `GrAppv`, `SBA_Appv`
- Chart: interactive scatter plot, optionally coloured by `MIS_Status`
- X-axis: gross approved amount (`GrAppv`)
- Y-axis: SBA-guaranteed amount (`SBA_Appv`)
- Add a reference line where `GrAppv = SBA_Appv`.
- Hover details may show approval amount, guaranteed amount, status, and guarantee percentage.
- Question: How does the guaranteed amount relate to the gross approved amount, and does the pattern differ by outcome?

### F. SBA guarantee percentage by outcome
- Derived metric: `SBA_Appv / GrAppv * 100`, when `GrAppv > 0`
- Chart: boxplot by loan status
- Question: Does the guarantee percentage differ between Paid-in-Full and Charged-Off loans?

### G. Amount not guaranteed by the SBA
- Derived metric: `GrAppv - SBA_Appv`
- Chart: boxplot by loan status, or charge-off rate across bands of this derived amount
- Question: Do outcomes differ across loans with different amounts not covered by the SBA guarantee?
- Note: this is not necessarily the lender’s realized loss; repayments, recoveries, and other factors affect actual losses.

## Recommended filters
- Approval year
- Loan amount range
- Loan term range
- Loan status
- New/existing business type (if included as a comparison)

---

# Page 3 — Business Analysis

## Purpose
Examine whether business characteristics and employment measures vary with historical loan outcomes.

## Suggested layout
- First row: charge-off rate for new versus existing businesses and employee count by outcome.
- Second row: jobs created and jobs retained by outcome.
- Optional: business size versus loan amount scatter plot.

## Analyses and visualizations

### A. New versus existing businesses
- Variables: `NewExist`, `MIS_Status`
- Chart: bar chart of charge-off rate by business type
- Question: Do new and existing businesses have different observed charge-off rates?
- Check category-code meanings and handle unknown or invalid values.

### B. Number of employees by outcome
- Variables: `NoEmp`, `MIS_Status`
- Chart: boxplot
- Question: Does the employee-count distribution differ by loan outcome?

### C. Jobs created by outcome
- Variables: `CreateJob`, `MIS_Status`
- Chart: boxplot or grouped summary chart
- Question: Does the number of jobs created vary by loan outcome?

### D. Jobs retained by outcome
- Variables: `RetainedJob`, `MIS_Status`
- Chart: boxplot or grouped summary chart
- Question: Does the number of jobs retained vary by loan outcome?

### E. Business size versus loan amount (optional)
- Variables: `NoEmp`, `DisbursementGross`, `MIS_Status`
- Chart: scatter plot coloured by outcome
- Question: How do employee count and loan amount relate, and how do patterns look across outcomes?
- With a large dataset, use transparency, sampling for display, or binning to reduce overplotting.

## Recommended filters
- Business type (`NewExist`)
- Loan status
- Employee-count range
- Approval year

---

# Page 4 — Industry Analysis

## Purpose
Compare historical loan performance across industries.

## Data preparation
Use `NAICS` to create broad industry groups instead of displaying hundreds of detailed codes. Confirm the dataset's coding and handle missing or special values before mapping codes to labels.

## Suggested layout
1. Horizontal bar chart: charge-off rate by industry.
2. 100% stacked bar chart: Paid-in-Full versus Charged-Off share by industry.
3. Optional: average/median loan amount by industry or charge-off rate by industry and loan-size band.

## Analyses and visualizations

### A. Charge-off rate by industry
- Variables: industry group derived from `NAICS`, `MIS_Status`
- Chart: horizontal bar chart
- Question: Which industry groups have higher or lower observed charge-off rates?
- Consider a minimum-loan threshold and show each industry's loan count alongside its rate.

### B. Outcome composition by industry
- Variables: industry group, `MIS_Status`
- Chart: 100% stacked bar chart
- Question: How does the outcome distribution vary across industries?
- This compares proportions rather than raw counts.

### C. Industry and loan size (optional)
- Variables: industry group, loan-size band, `MIS_Status`
- Chart: grouped bar chart, heatmap, or faceted plot of charge-off rates
- Question: Do loan-size patterns differ across industries?

## Recommended filters
- Industry group
- Approval year
- Loan-size range
- State (optional)
- Loan status

---

# Page 5 — Risk Explorer

## Purpose
Let users combine filters and inspect historical outcomes for the selected subset of loans. This is the dashboard's main interactive exploration feature.

## Suggested layout
1. **Filter panel:** state, industry, loan-size range, loan-term range, new/existing business, approval year, and optional employee-count range.
2. **Dynamic KPI cards:** number of matching loans, Paid-in-Full count, Charged-Off count, and historical charge-off rate.
3. **Dynamic visualizations:** outcome distribution, charge-off rate by loan-size band or loan term, and optional comparison with the overall dataset rate.
4. **Plain-language summary:** describe the selected filters, sample size, and observed rate. Distinguish a group's historical rate from a model-based prediction.

## Example workflow
A user selects Construction, Texas, loan size $50k–$100k, and Existing Business. The dashboard updates the number of matching loans, outcome counts, and historical charge-off rate. It can then show how the rate varies across loan terms or other characteristics within the selected group.

## Important interpretation note
Call this a historical risk exploration feature, not a definitive loan approval tool. A small subset may have an unstable rate, and a high historical charge-off rate does not prove that a particular loan would fail.

---

# Page 6 — Data Explorer

## Purpose
Let users inspect records, understand variable summaries, and download filtered data for further analysis.

## Suggested layout
1. Filter controls.
2. Summary statistics for the selected data.
3. Searchable, sortable, paginated table.
4. Download button for filtered records.

## Features
- Select columns such as state, industry, approval year, loan amount, term, employee count, and loan status.
- Search and sort table columns.
- Filter records by relevant variables.
- Download the filtered subset as CSV.
- Display missing-value counts or a compact data-quality summary.

## Implementation note
Use `DT` for searching, sorting, and pagination. Avoid rendering all 899k rows in the browser at once; filter and limit displayed records as needed.

---

# Optional Time Analysis

Keep time analysis on the Overview page initially. If it becomes a major part of the project, it could later become its own tab.

Possible analyses:
- Number of loans by `ApprovalFY`
- Charge-off rate by `ApprovalFY`
- Average `GrAppv` or `SBA_Appv` by approval year
- Loan outcomes by approval year

**Important:** Recent approval-year cohorts may have had less time to experience charge-offs. Interpret year-to-year comparisons with this limitation in mind.

---

# Suggested Navigation
 
Use a top horizontally with these pages:

1. **Overview** — KPIs, outcome distribution, state map, and yearly trend
2. **Loan Analysis** — loan amounts, terms, `GrAppv` versus `SBA_Appv`, guarantee percentage, and amount not guaranteed
3. **Business Analysis** — new/existing businesses, employees, jobs created, and jobs retained
4. **Industry Analysis** — industry-level rates and outcome composition
5. **Risk Explorer** — combined filters and dynamic historical summaries
6. **Data Explorer** — searchable table, summaries, and CSV download

This keeps geographic analysis on the Overview page and avoids creating too many tabs.


---

# Design Principles

Aim for a repeatable user experience:

**Filter → KPI summary → Visualization → Interpretation**

Keep each page focused on a small number of questions. Prefer charge-off **rates** when comparing groups of different sizes, and show sample counts alongside rates. Use clear titles, readable axis labels, and hover details where useful.

The dashboard should help users explore which historical characteristics are associated with loan outcomes. It should not imply causation or provide definitive approval/rejection recommendations without a separately developed and validated predictive model.
