"""Data loading, derived columns, filtering, aggregation and driver ranking.

The cleaned CSV is converted once into a typed Parquet cache (``sba_cache.parquet``)
so the dashboard starts in a couple of seconds instead of re-parsing 90 MB of CSV.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
CSV_PATH = BASE / "cleaned_SBA.csv"
CACHE_PATH = BASE / "sba_cache.parquet"
CACHE_VERSION = "6"
MISSING_PATH = BASE / "sba_missing.json"

# ----------------------------------------------------------------------------
# Labels and band definitions
# ----------------------------------------------------------------------------
INDUSTRY_LABELS = {
    "Retail_trade": "Retail Trade",
    "Construction": "Construction",
    "Prof/Science/Tech": "Professional, Scientific & Tech",
    "Manufacturing": "Manufacturing",
    "Other_no_pub": "Other Services",
    "Wholesale_trade": "Wholesale Trade",
    "Healthcare/Social_assist": "Health Care & Social Assistance",
    "Accom/Food_serv": "Accommodation & Food Services",
    "Admin_sup/Waste_Mgmt_Rem": "Admin Support & Waste Mgmt",
    "Trans/Ware": "Transportation & Warehousing",
    "RE/Rental/Lease": "Real Estate & Rental",
    "Arts/Entertain/Rec": "Arts, Entertainment & Recreation",
    "Ag/For/Fish/Hunt": "Agriculture, Forestry & Fishing",
    "Information": "Information",
    "Finance/Insurance": "Finance & Insurance",
    "Educational": "Educational Services",
    "Min/Quar/Oil_Gas_ext": "Mining, Quarrying, Oil & Gas",
    "Utilities": "Utilities",
    "Public_Admin": "Public Administration",
    "Mgmt_comp": "Management of Companies",
}

STATE_NAMES = {
    "AK": "Alaska", "AL": "Alabama", "AR": "Arkansas", "AZ": "Arizona", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DC": "District of Columbia", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "IA": "Iowa", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "MA": "Massachusetts", "MD": "Maryland", "ME": "Maine", "MI": "Michigan", "MN": "Minnesota",
    "MO": "Missouri", "MS": "Mississippi", "MT": "Montana", "NC": "North Carolina",
    "ND": "North Dakota", "NE": "Nebraska", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NV": "Nevada", "NY": "New York", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VA": "Virginia",
    "VT": "Vermont", "WA": "Washington", "WI": "Wisconsin", "WV": "West Virginia", "WY": "Wyoming",
}

# US Census regions
REGIONS = {
    "Northeast": ["CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"],
    "Midwest": ["IL", "IN", "MI", "OH", "WI", "IA", "KS", "MN", "MO", "NE", "ND", "SD"],
    "South": ["DE", "DC", "FL", "GA", "MD", "NC", "SC", "VA", "WV", "AL", "KY", "MS", "TN", "AR", "LA", "OK", "TX"],
    "West": ["AZ", "CO", "ID", "MT", "NV", "NM", "UT", "WY", "AK", "CA", "HI", "OR", "WA"],
}
STATE_REGION = {s: r for r, states in REGIONS.items() for s in states}
REGION_LABELS = list(REGIONS)

# Credit-cycle eras used throughout the dashboard
ERA_BINS = [0, 1990, 2001, 2004, 2008, 2010, 2100]
ERA_LABELS = ["1987–90", "1991–2001", "2002–04", "2005–08", "2009–10", "2011–14"]
ERA_NOTES = {
    "1987–90": "early, small cohorts",
    "1991–2001": "long expansion",
    "2002–04": "post dot-com",
    "2005–08": "pre-crisis boom",
    "2009–10": "crisis & recovery",
    "2011–14": "recent, less time to default",
}

SIZE_BINS = [-1, 50_000, 100_000, 250_000, 500_000, 1_000_000, np.inf]
SIZE_LABELS = ["≤ $50k", "$50k–100k", "$100k–250k", "$250k–500k", "$500k–1M", "> $1M"]

TERM_BINS = [-1, 60, 120, 180, 240, np.inf]
TERM_LABELS = ["≤ 5 yrs", "5–10 yrs", "10–15 yrs", "15–20 yrs", "> 20 yrs"]
STANDARD_TERMS = [12, 24, 36, 48, 60, 72, 84, 96, 108, 120, 144, 180, 240, 300]

EMP_BINS = [-1, 0, 5, 10, 20, 50, 100, np.inf]
EMP_LABELS = ["0", "1–5", "6–10", "11–20", "21–50", "51–100", "> 100"]

JOB_BINS = [-1, 0, 2, 5, 10, np.inf]
JOB_LABELS = ["0", "1–2", "3–5", "6–10", "> 10"]

# Guarantee bands follow the SBA programme rules (50% SBAExpress, 75/85% standard 7(a), …)
GUAR_BINS = [-1, 50.05, 74.95, 79.95, 84.95, 89.95, 101]
GUAR_LABELS = ["≤ 50%", "51–74%", "75–79%", "80–84%", "85–89%", "≥ 90%"]

DAYS_BINS = [-np.inf, 30, 60, 120, 365, np.inf]
DAYS_LABELS = ["≤ 1 mo", "1–2 mo", "2–4 mo", "4–12 mo", "> 1 yr"]

OUTCOMES = ["Paid in Full", "Charged Off"]
N_TOP_LENDERS = 25
OTHER_LENDERS = "All other lenders"

LENDER_NAMES = {
    "BANK OF AMERICA NATL ASSOC": "Bank of America",
    "JPMORGAN CHASE BANK NATL ASSOC": "JPMorgan Chase",
    "WELLS FARGO BANK NATL ASSOC": "Wells Fargo",
    "CITIZENS BANK NATL ASSOC": "Citizens Bank",
    "U.S. BANK NATIONAL ASSOCIATION": "U.S. Bank",
    "CAPITAL ONE NATL ASSOC": "Capital One",
    "PNC BANK, NATIONAL ASSOCIATION": "PNC Bank",
    "BBCN BANK": "BBCN Bank",
    "MANUFACTURERS & TRADERS TR CO": "M&T Bank",
    "THE HUNTINGTON NATIONAL BANK": "Huntington",
    "ZIONS FIRST NATIONAL BANK": "Zions Bank",
    "CITIBANK, N.A.": "Citibank",
    "TD BANK, NATIONAL ASSOCIATION": "TD Bank",
    "KEYBANK NATIONAL ASSOCIATION": "KeyBank",
    "BRANCH BK. & TR CO": "BB&T",
    "CALIFORNIA BANK & TRUST": "California Bank & Trust",
    "BANCO POPULAR NORTH AMERICA": "Banco Popular",
    "HSBC BK USA NATL ASSOC": "HSBC",
    "SUPERIOR FINANCIAL GROUP, LLC": "Superior Financial Group",
    "COMPASS BANK": "Compass Bank",
    "UMPQUA BANK": "Umpqua Bank",
    "REGIONS BANK": "Regions Bank",
    "BUSINESS LOAN CENTER, LLC": "Business Loan Center",
    "FIRST NIAGARA BANK NATL ASSOC": "First Niagara",
    "SUNTRUST BANK": "SunTrust",
}

TABLE_COLUMNS = [
    "LoanNr_ChkDgt", "Name", "City", "State", "Bank", "Industry", "ApprovalFY", "Era", "Term",
    "NoEmp", "BizType", "Area", "DisbursementGross", "GrAppv", "SBA_Appv", "GuarPct",
    "CreateJob", "RetainedJob", "RevLineCr", "LowDoc", "IsFranchise", "Outcome", "ChgOffPrinGr",
    "MonthsToCO",
]


def pretty_lender(name: str) -> str:
    if name in LENDER_NAMES:
        return LENDER_NAMES[name]
    s = str(name).title()
    for a, b in ((" Natl Assoc", ""), (" National Association", ""), (", N.A.", ""), (" Nat'L", ""),
                 (", Llc", ""), (" Llc", ""), ("Bk.", "Bank"), (" Bk ", " Bank "), ("Tr Co", "Trust"),
                 (" Of ", " of "), (" And ", " & "), (" The ", " the ")):
        s = s.replace(a, b)
    return s.strip(" ,")


def _build_cache() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH, low_memory=False)
    miss = df.isna().sum()
    MISSING_PATH.write_text(json.dumps({"rows": len(df), "missing": {k: int(v) for k, v in miss.items() if v}}))
    df = df[df["ApprovalFY"] >= 1987].copy()  # one stray 1984 record

    df["Outcome"] = np.where(df["Default"] == 1, "Charged Off", "Paid in Full")
    df["Industry"] = df["Industry"].map(INDUSTRY_LABELS).fillna(df["Industry"])
    df["BizType"] = np.where(df["NewExist"] == 2, "New", "Existing")
    df["Area"] = df["UrbanRural"].map({1: "Urban", 2: "Rural", 0: "Undefined"})
    df["StateName"] = df["State"].map(STATE_NAMES)
    df["Region"] = df["State"].map(STATE_REGION)
    df["CityST"] = df["City"].astype(str).str.strip().str.title() + ", " + df["State"].astype(str)
    df["Era"] = pd.cut(df["ApprovalFY"], ERA_BINS, labels=ERA_LABELS)

    df["SBA_Appv"] = df["SBA_Appv"].fillna(df["GrAppv"] * df["SBA_AppvPct"].median())
    df["GuarPct"] = (df["SBA_AppvPct"].fillna(df["SBA_AppvPct"].median()) * 100).round(1)
    df["Unguaranteed"] = (df["GrAppv"] - df["SBA_Appv"]).clip(lower=0)

    # Lenders: keep the largest by volume, fold the long tail into one group
    top = df["Bank"].value_counts().index[:N_TOP_LENDERS]
    df["Lender"] = np.where(df["Bank"].isin(top), df["Bank"].map(pretty_lender), OTHER_LENDERS)

    # Timing of failure and size of the loss
    disb = pd.to_datetime(df["DisbursementDate"], format="%m/%d/%Y", errors="coerce")
    chg = pd.to_datetime(df["ChgOffDate"], format="%d-%b-%y", errors="coerce")
    chg = chg.where(df["Default"] == 1)
    df["MonthsToCO"] = ((chg - disb).dt.days / 30.44).clip(lower=0).round(1)
    df["ChgOffYear"] = chg.dt.year.astype("Int64")
    df["LossShare"] = np.where(df["Default"] == 1,
                               (df["ChgOffPrinGr"] / df["DisbursementGross"].replace(0, np.nan)).clip(upper=1.5), np.nan)
    df["SBALoss"] = df["ChgOffPrinGr"] * df["GuarPct"] / 100
    df["StdTerm"] = df["Term"].isin(STANDARD_TERMS)

    df["SizeBand"] = pd.cut(df["DisbursementGross"], SIZE_BINS, labels=SIZE_LABELS)
    df["TermBand"] = pd.cut(df["Term"], TERM_BINS, labels=TERM_LABELS)
    df["EmpBand"] = pd.cut(df["NoEmp"], EMP_BINS, labels=EMP_LABELS)
    df["CreateBand"] = pd.cut(df["CreateJob"], JOB_BINS, labels=JOB_LABELS)
    df["RetainBand"] = pd.cut(df["RetainedJob"], JOB_BINS, labels=JOB_LABELS)
    df["GuarBand"] = pd.cut(df["GuarPct"], GUAR_BINS, labels=GUAR_LABELS)
    df["DaysBand"] = pd.cut(df["DaysToDisbursement"], DAYS_BINS, labels=DAYS_LABELS)
    df["TermFine"] = pd.cut(df["Term"], [-1, 12, 24, 36, 48, 60, 72, 84, 96, 120, 180, 240, np.inf])

    for col in ["State", "StateName", "Region", "CityST", "Industry", "BizType", "Area", "Outcome", "BankState", "Lender"]:
        df[col] = df[col].astype("category")
    df["TermFine"] = df["TermFine"].astype(str).astype("category")
    for col in ["Name", "City", "Bank"]:
        df[col] = df[col].astype("string")
    df = df.reset_index(drop=True)
    df.to_parquet(CACHE_PATH, index=False)
    (BASE / ".cache_version").write_text(CACHE_VERSION)
    return df


def load() -> pd.DataFrame:
    version_file = BASE / ".cache_version"
    fresh = (
        CACHE_PATH.exists()
        and version_file.exists()
        and version_file.read_text().strip() == CACHE_VERSION
        and CACHE_PATH.stat().st_mtime >= CSV_PATH.stat().st_mtime
        and MISSING_PATH.exists()
    )
    if fresh:
        return pd.read_parquet(CACHE_PATH)
    print("Building Parquet cache from cleaned_SBA.csv (first run only)...")
    return _build_cache()


DF = load()
N_ALL = len(DF)
BASE_RATE = float(DF["Default"].mean())
YEAR_MIN, YEAR_MAX = int(DF["ApprovalFY"].min()), int(DF["ApprovalFY"].max())
STATES = sorted(DF["State"].cat.categories.tolist())
INDUSTRIES = DF["Industry"].value_counts().index.tolist()
LENDERS = DF.loc[DF["Lender"] != OTHER_LENDERS, "Lender"].value_counts().index.tolist() + [OTHER_LENDERS]

_YEAR = DF["ApprovalFY"].to_numpy()


# ----------------------------------------------------------------------------
# Filtering
# ----------------------------------------------------------------------------
DEFAULT_FILTERS = {
    "years": [YEAR_MIN, YEAR_MAX],
    "states": [],
    "industries": [],
    "biz": "All",
    "area": ["Urban", "Rural", "Undefined"],
    "sizes": [],
}


def filter_key(filters: dict | None) -> str:
    return json.dumps(filters or DEFAULT_FILTERS, sort_keys=True)


@lru_cache(maxsize=64)
def _mask_from_key(key: str) -> np.ndarray:
    f = {**DEFAULT_FILTERS, **json.loads(key)}
    m = np.ones(N_ALL, dtype=bool)
    y0, y1 = f["years"]
    m &= (_YEAR >= y0) & (_YEAR <= y1)
    if f["states"]:
        m &= DF["State"].isin(f["states"]).to_numpy()
    if f["industries"]:
        m &= DF["Industry"].isin(f["industries"]).to_numpy()
    if f["biz"] in ("New", "Existing"):
        m &= (DF["BizType"] == f["biz"]).to_numpy()
    if f["area"] and len(f["area"]) < 3:
        m &= DF["Area"].isin(f["area"]).to_numpy()
    if f["sizes"]:
        m &= DF["SizeBand"].isin(f["sizes"]).to_numpy()
    m.setflags(write=False)
    return m


def memo(maxsize: int = 48):
    """Cache a page callback's outputs by its (JSON-serialisable) inputs."""
    from collections import OrderedDict
    from functools import wraps

    def deco(fn):
        cache = OrderedDict()

        @wraps(fn)
        def wrapper(*args):
            key = json.dumps(args, sort_keys=True, default=str)
            if key in cache:
                cache.move_to_end(key)
                return cache[key]
            out = fn(*args)
            cache[key] = out
            if len(cache) > maxsize:
                cache.popitem(last=False)
            return out
        return wrapper
    return deco


def is_default_filters(filters: dict | None) -> bool:
    return filter_key(filters) == filter_key(DEFAULT_FILTERS)


def filtered(filters: dict | None) -> pd.DataFrame:
    if is_default_filters(filters):
        return DF
    return DF[_mask_from_key(filter_key(filters))]


# ----------------------------------------------------------------------------
# Aggregation helpers
# ----------------------------------------------------------------------------
def rate_by(d: pd.DataFrame, col, min_n: int = 0) -> pd.DataFrame:
    """Charge-off rate, counts, money and Wilson 95% interval for each level of ``col``."""
    g = d.groupby(col, observed=True).agg(
        n=("Default", "size"), co=("Default", "sum"),
        disb=("DisbursementGross", "sum"), loss=("ChgOffPrinGr", "sum"),
    ).reset_index()
    g["pif"] = g["n"] - g["co"]
    g["rate"] = g["co"] / g["n"]
    g["lossrate"] = g["loss"] / g["disb"].replace(0, np.nan)
    lo, hi = wilson(g["co"].to_numpy(), g["n"].to_numpy())
    g["lo"], g["hi"] = lo, hi
    if min_n:
        g = g[g["n"] >= min_n]
    return g


def wilson(k, n, z: float = 1.96):
    k = np.asarray(k, dtype=float)
    n = np.asarray(n, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = np.where(n > 0, k / n, 0)
        denom = 1 + z**2 / n
        centre = (p + z**2 / (2 * n)) / denom
        half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return np.nan_to_num(centre - half), np.nan_to_num(centre + half)


def sample(d: pd.DataFrame, n: int = 6000, seed: int = 7) -> pd.DataFrame:
    return d if len(d) <= n else d.sample(n, random_state=seed)


def missing_summary() -> tuple[int, dict]:
    info = json.loads(MISSING_PATH.read_text())
    return info["rows"], info["missing"]


# ----------------------------------------------------------------------------
# Driver ranking — Information Value (the standard credit-scoring screen)
# ----------------------------------------------------------------------------
# (column, label, group, known when the loan is approved?, caveat)
DRIVERS = [
    ("TermFine", "Loan term", "Loan", True, "Suspect — likely updated after default"),
    ("Era", "Approval era", "Timing", True, ""),
    ("Lender", "Lender", "Lender", True, ""),
    ("BankState", "Lender's state", "Lender", True, ""),
    ("GuarBand", "SBA guarantee share", "Loan", True, ""),
    ("DaysBand", "Days to disbursement", "Loan", False, "Only known after approval"),
    ("Area", "Urban / rural", "Borrower", True, ""),
    ("SizeBand", "Loan amount", "Loan", True, ""),
    ("StateSame", "Lender in same state", "Lender", True, ""),
    ("State", "Borrower state", "Borrower", True, ""),
    ("RetainBand", "Jobs retained", "Borrower", True, ""),
    ("Industry", "Industry", "Borrower", True, ""),
    ("EmpBand", "Employees", "Borrower", True, ""),
    ("CreateBand", "Jobs created", "Borrower", True, ""),
    ("LowDoc", "LowDoc programme", "Loan", True, ""),
    ("RevLineCr", "Revolving line of credit", "Loan", True, ""),
    ("IsFranchise", "Franchise", "Borrower", True, ""),
    ("BizType", "New vs existing business", "Borrower", True, ""),
]

# Inputs offered by the Risk Explorer: the five strongest drivers that are known
# when a loan is approved (Term is excluded as suspect; see Risk Drivers page).
EXPLORER_DRIVERS = ["Era", "Lender", "GuarBand", "State", "SizeBand"]


def information_value(d: pd.DataFrame, col: str, min_n: int = 30) -> float:
    g = d.groupby(col, observed=True)["Default"].agg(["size", "sum"])
    g = g[g["size"] >= min_n]
    if len(g) < 2:
        return 0.0
    bad = g["sum"].to_numpy(float)
    good = (g["size"] - g["sum"]).to_numpy(float)
    db = (bad + 0.5) / (bad.sum() + 0.5)
    dg = (good + 0.5) / (good.sum() + 0.5)
    return float(((dg - db) * np.log(dg / db)).sum())


@lru_cache(maxsize=16)
def _drivers_from_key(key: str) -> pd.DataFrame:
    d = DF[_mask_from_key(key)] if key != filter_key(DEFAULT_FILTERS) else DF
    eras = [(len(g), g) for _, g in d.groupby("Era", observed=True) if len(g) >= 500]
    rows = []
    for col, label, group, at_app, note in DRIVERS:
        iv_all = information_value(d, col)
        if col == "Era" or not eras:
            iv_within = np.nan
        else:
            iv_within = sum(n * information_value(g, col) for n, g in eras) / sum(n for n, _ in eras)
        rows.append(dict(col=col, label=label, group=group, at_app=at_app, note=note,
                         iv_all=iv_all, iv_within=iv_within))
    out = pd.DataFrame(rows)
    out["score"] = out["iv_within"].fillna(out["iv_all"])
    return out.sort_values("score", ascending=False).reset_index(drop=True)


def drivers(filters: dict | None) -> pd.DataFrame:
    return _drivers_from_key(filter_key(filters))


def iv_strength(v: float) -> str:
    if v >= 0.5:
        return "Very strong"
    if v >= 0.3:
        return "Strong"
    if v >= 0.1:
        return "Medium"
    if v >= 0.02:
        return "Weak"
    return "None"
