import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(page_title="Client Success Dashboard", layout="wide")
st.title("Client Success Results Dashboard")

uploaded = st.file_uploader("Upload your CSV", type=["csv"])

if not uploaded:
    st.stop()

# ---------- Load CSV safely ----------
def make_unique_columns(cols):
    seen = {}
    out = []
    for c in cols:
        c = str(c).strip()
        if c in seen:
            seen[c] += 1
            out.append(f"{c} ({seen[c]})")
        else:
            seen[c] = 0
            out.append(c)
    return out

# Try common encodings
df = None
load_errors = []
for encoding in ["utf-8-sig", "utf-8", "latin-1"]:
    try:
        df = pd.read_csv(uploaded, encoding=encoding)
        break
    except Exception as e:
        load_errors.append(f"{encoding}: {e}")

if df is None:
    st.error("Could not read CSV. Here are the load errors:")
    for e in load_errors:
        st.write(e)
    st.stop()

df.columns = make_unique_columns(df.columns)

# ---------- Helpers ----------
def guess_col(options):
    # returns first match in df.columns, else None
    for opt in options:
        if opt in df.columns:
            return opt
    return None

def safe_series(col_name):
    # always returns a series of same length
    if col_name and col_name in df.columns:
        return df[col_name]
    return pd.Series([np.nan] * len(df))

def to_dt(series):
    return pd.to_datetime(series, errors="coerce")

def to_num(series):
    return pd.to_numeric(series, errors="coerce")

# ---------- Column mapping UI ----------
with st.sidebar:
    st.header("Column mapping")

    all_cols = ["(None)"] + list(df.columns)

    default_name = guess_col(["Client Name", "Name"])
    default_email = guess_col(["Client Email", "Email"])
    default_tier = guess_col(["Client Level", "Membership Level"])
    default_purchase = guess_col(["Purchase Date"])
    default_end = guess_col(["Contract End Date"])
    default_days = guess_col(["Days Remaining"])
    default_status = guess_col(["Status"])
    default_payment = guess_col(["Payment"])
    default_arr = guess_col(["ARR"])
    default_id = guess_col(["Member ID"])
    default_qtr = guess_col(["Quarter"])
    default_city = guess_col(["City / State"])
    default_country = guess_col(["Country"])
    default_tz = guess_col(["Time Zone"])
    default_linkedin = guess_col(["LinkedIn Profile"])
    default_kajabi = guess_col(["Member Profile Kajabi"])

    def sel(label, default):
        idx = all_cols.index(default) if default in all_cols else 0
        choice = st.selectbox(label, all_cols, index=idx)
        return None if choice == "(None)" else choice

    COL_NAME = sel("Client name", default_name)
    COL_EMAIL = sel("Client email", default_email)
    COL_TIER = sel("Membership level", default_tier)
    COL_PURCHASE = sel("Purchase date", default_purchase)
    COL_END = sel("Contract end date", default_end)
    COL_DAYS = sel("Days remaining", default_days)
    COL_STATUS = sel("Status", default_status)
    COL_PAYMENT = sel("Payment", default_payment)
    COL_ARR = sel("ARR", default_arr)
    COL_ID = sel("Member ID", default_id)
    COL_QTR = sel("Quarter", default_qtr)
    COL_CITY = sel("City / State", default_city)
    COL_COUNTRY = sel("Country", default_country)
    COL_TZ = sel("Time zone", default_tz)
    COL_LINKEDIN = sel("LinkedIn", default_linkedin)
    COL_KAJABI = sel("Kajabi profile", default_kajabi)

st.caption("If anything looks wrong, adjust the column mapping in the sidebar.")

# ---------- Build a working dataset regardless of missing columns ----------
out = pd.DataFrame()
out["Client Name"] = safe_series(COL_NAME).astype(str).replace("nan", "").str.strip()
out["Client Email"] = safe_series(COL_EMAIL).astype(str).replace("nan", "").str.strip()
out["Membership Level"] = safe_series(COL_TIER).astype(str).replace("nan", "").str.strip()
out["Status"] = safe_series(COL_STATUS).astype(str).replace("nan", "").str.strip()
out["Payment"] = safe_series(COL_PAYMENT).astype(str).replace("nan", "").str.strip()
out["Member ID"] = safe_series(COL_ID).astype(str).replace("nan", "").str.strip()
out["Quarter"] = safe_series(COL_QTR).astype(str).replace("nan", "").str.strip()
out["City / State"] = safe_series(COL_CITY).astype(str).replace("nan", "").str.strip()
out["Country"] = safe_series(COL_COUNTRY).astype(str).replace("nan", "").str.strip()
out["Time Zone"] = safe_series(COL_TZ).astype(str).replace("nan", "").str.strip()
out["LinkedIn Profile"] = safe_series(COL_LINKEDIN).astype(str).replace("nan", "").str.strip()
out["Kajabi Profile"] = safe_series(COL_KAJABI).astype(str).replace("nan", "").str.strip()

purchase = to_dt(safe_series(COL_PURCHASE))
end = to_dt(safe_series(COL_END))
out["Purchase Date"] = purchase
out["Contract End Date"] = end

arr = to_num(safe_series(COL_ARR)).fillna(0)
out["ARR"] = arr

# Days Remaining: prefer provided, otherwise calculate
provided_days = to_num(safe_series(COL_DAYS))
today = pd.Timestamp(datetime.utcnow().date())

calc_days = (end - today).dt.days if COL_END else pd.Series([np.nan] * len(out))
out["Days Remaining"] = provided_days.where(provided_days.notna(), calc_days)

# ---------- Risk logic (pipeline-focused) ----------
def risk_bucket(days_remaining, status, payment):
    status_l = str(status).lower()
    payment_l = str(payment).lower()

    if "cancel" in status_l or "churn" in status_l:
        return "At Risk"

    if pd.isna(days_remaining):
        return "Unknown"

    if days_remaining <= 30:
        return "At Risk"
    if days_remaining <= 60:
        return "Monitor"

    if "failed" in payment_l or "overdue" in payment_l or "past due" in payment_l:
        return "Monitor"

    return "Healthy"

out["Risk"] = [
    risk_bucket(d, s, p)
    for d, s, p in zip(out["Days Remaining"], out["Status"], out["Payment"])
]

# ---------- Filters ----------
with st.sidebar:
    st.header("Filters")

    tiers = sorted([t for t in out["Membership Level"].dropna().unique() if str(t).strip() and str(t).lower() != "nan"])
    risks = ["Healthy", "Monitor", "At Risk", "Unknown"]

    tier_sel = st.multiselect("Membership Level", tiers, default=tiers)
    risk_sel = st.multiselect("Risk", risks, default=risks)

    # Guard slider max
    max_days = out["Days Remaining"].dropna()
    max_days = int(max_days.max()) if len(max_days) else 365
    days_range = st.slider("Days Remaining range", min_value=-30, max_value=max(90, max_days), value=(-30, 90))

f = out.copy()

if tier_sel:
    f = f[f["Membership Level"].isin(tier_sel)]

f = f[f["Risk"].isin(risk_sel)]
f = f[(f["Days Remaining"] >= days_range[0]) & (f["Days Remaining"] <= days_range[1])]

# ---------- KPIs ----------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Accounts", int(f.shape[0]))
c2.metric("ARR", f"{float(f['ARR'].sum()):,.0f}")
c3.metric("Healthy", int((f["Risk"] == "Healthy").sum()))
c4.metric("Monitor", int((f["Risk"] == "Monitor").sum()))
c5.metric("At Risk", int((f["Risk"] == "At Risk").sum()))

# ---------- Charts ----------
left, right = st.columns(2)

with left:
    st.subheader("Risk counts")
    risk_counts = f["Risk"].value_counts().reindex(["Healthy", "Monitor", "At Risk", "Unknown"]).fillna(0)
    st.bar_chart(risk_counts)

with right:
    st.subheader("ARR by level")
    arr_by_level = f.groupby("Membership Level")["ARR"].sum().sort_values(ascending=False)
    st.bar_chart(arr_by_level)

# ---------- Table ----------
st.subheader("Accounts")
show_cols = [
    "Client Name",
    "Client Email",
    "Membership Level",
    "Risk",
    "Days Remaining",
    "Contract End Date",
    "ARR",
    "Status",
    "Payment",
    "Quarter",
    "City / State",
    "Country",
    "Time Zone",
    "LinkedIn Profile",
    "Kajabi Profile",
    "Member ID",
]
show_cols = [c for c in show_cols if c in f.columns]

# Sort: most urgent first
f_sorted = f.sort_values(by=["Risk", "Days Remaining"], ascending=[True, True]).copy()
st.dataframe(f_sorted[show_cols], use_container_width=True, hide_index=True)

# ---------- Debug section ----------
with st.expander("Debug: show detected columns and first rows"):
    st.write(list(df.columns))
    st.dataframe(df.head(10), use_container_width=True)