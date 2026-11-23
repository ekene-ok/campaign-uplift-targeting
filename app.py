"""Interactive explorer for the campaign uplift targeting analysis.

Run locally:  streamlit run app.py
Uses the model outputs in results/, so it runs without the raw dataset.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import streamlit as st

st.set_page_config(page_title="Campaign Uplift Targeting", layout="wide")
RES = Path(__file__).resolve().parent / "results"
HIGHLIGHT, CONTEXT, INK, INK2 = "#e0612e", "#d9d8d3", "#1a1a1a", "#6b6a66"
TEST_CUSTOMERS = 19_200  # held-out 30% of 64,000 used for the targeting curve


@st.cache_data
def load():
    t = pd.read_csv(RES / "targeting_list.csv")
    t["past_spend"] = t["history_segment"].str.replace(r"^\d\) ", "", regex=True).str.replace(" - ", " to ")
    t["tenure"] = np.where(t["newbie"] == 1, "New (last 12 months)", "Existing")
    curve = pd.read_csv(RES / "targeting_curve.csv")
    policies = pd.read_csv(RES / "policy_comparison.csv")
    return t, curve, policies


t, curve, policies = load()

st.title("Who should get which email?")
st.write("Explore the results of a randomised email test with 64,000 customers: one group got a men's merchandise "
         "email, one a women's email, and one nothing. Uplift is the extra visits an email caused compared with "
         "sending nothing. [Read the full analysis](https://github.com/ekene-ok/campaign-uplift-targeting)")

# Section 1: segment explorer
st.header("1. Pick a customer segment")
f1, f2, f3, f4 = st.columns(4)
hist = f1.multiselect("Previously bought", sorted(t["purchase_history"].unique()), default=sorted(t["purchase_history"].unique()))
spend_order = sorted(t["past_spend"].unique(), key=lambda s: float(s.split(" ")[0].replace("$", "").replace(",", "").replace("+", "")))
spend = f2.multiselect("Past spend", spend_order, default=spend_order)
tenure = f3.multiselect("Customer tenure", ["Existing", "New (last 12 months)"], default=["Existing", "New (last 12 months)"])
chan = f4.multiselect("Purchase channel", sorted(t["channel"].unique()), default=sorted(t["channel"].unique()))
seg = t[t["purchase_history"].isin(hist) & t["past_spend"].isin(spend) & t["tenure"].isin(tenure) & t["channel"].isin(chan)]

if seg.empty:
    st.info("No customers match. Widen the filters.")
else:
    mens, womens = seg["uplift_mens"].mean() * 100, seg["uplift_womens"].mean() * 100
    share_mens = (seg["recommended_email"] == "Mens E-Mail").mean()
    better = "men's" if mens >= womens else "women's"
    m1, m2, m3 = st.columns(3)
    m1.metric("Customers in segment", f"{len(seg):,}")
    m2.metric("Extra visits per 100 customers, best email", f"{max(mens, womens):.1f}")
    m3.metric("Customers who should get the men's email", f"{share_mens:.0%}")
    fig, ax = plt.subplots(figsize=(8, 2.6))
    vals = [womens, mens]
    hi = 1 if mens >= womens else 0
    ax.barh(["Women's email", "Men's email"], vals, height=0.5, color=[HIGHLIGHT if i == hi else CONTEXT for i in range(2)])
    for y, v in enumerate(vals):
        ax.text(v + 0.2, y, f"+{v:.1f} visits per 100", va="center", color=INK if y == hi else INK2,
                fontweight="bold" if y == hi else "normal")
    ax.set_xlim(0, max(vals) * 1.45 + 0.5)
    ax.set_xticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_title(f"For this segment, the {better} email works better", loc="left", fontsize=13, fontweight="bold")
    chart_col, _ = st.columns([3, 2])
    chart_col.pyplot(fig)
    st.caption("Predicted by the uplift model (one model per test group). Values are averages across the segment.")

# Section 2: how many customers to email
st.header("2. How many customers are worth emailing?")
st.write("Rank customers by predicted uplift and email from the top. Set what an email costs (including discounts or "
         "fatigue) and what an extra visit is worth, and see where the net value peaks.")
c1, c2 = st.columns(2)
cost = c1.slider("Cost per email sent ($)", 0.00, 2.00, 0.01, 0.01)
value = c2.slider("Value of one extra website visit ($)", 0.50, 20.00, 5.00, 0.50)

cv = curve.copy()
cv["emails_per_1000"] = cv["share_emailed"] * 1000
cv["extra_visits_per_1000"] = cv["incremental_visits"] * 1000 / TEST_CUSTOMERS
cv["net_value_per_1000"] = cv["extra_visits_per_1000"] * value - cv["emails_per_1000"] * cost
best = cv.loc[cv["net_value_per_1000"].idxmax()]

n1, n2, n3 = st.columns(3)
n1.metric("Best share of customers to email", f"{best['share_emailed']:.0%}")
n2.metric("Share of all extra visits captured", f"{best['share_of_total_incremental']:.0%}")
n3.metric("Net value per 1,000 customers", f"${best['net_value_per_1000']:,.0f}")

fig, ax = plt.subplots(figsize=(8, 3.2))
ax.plot(cv["share_emailed"] * 100, cv["net_value_per_1000"], color=CONTEXT, linewidth=2.5)
ax.scatter([best["share_emailed"] * 100], [best["net_value_per_1000"]], color=HIGHLIGHT, s=90, zorder=3)
label = "Best: email everyone" if best["share_emailed"] >= 0.999 else f"Best: email the top {best['share_emailed']:.0%}"
# Place the label above the point, on the side with room, so it never overlaps the line or the axis.
bx = best["share_emailed"] * 100
on_right = bx < 50
ax.annotate(label, (bx, best["net_value_per_1000"]), xytext=(10 if on_right else -10, 14),
            textcoords="offset points", ha="left" if on_right else "right", va="bottom",
            color=INK, fontweight="bold")
lo, hi = cv["net_value_per_1000"].min(), cv["net_value_per_1000"].max()
span = max(hi - lo, 1)
ax.set_ylim(min(lo, 0) - span * 0.05, max(hi, 0) + span * 0.25)
ax.set_xlim(0, 103)
ax.axhline(0, color=INK2, linewidth=0.6)
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
ax.set_xlabel("Share of customers emailed, highest predicted uplift first (%)", color=INK2)
ax.set_ylabel("Net value per 1,000 ($)", color=INK2)
title = ("When emails cost almost nothing, email nearly everyone" if best["share_emailed"] >= 0.9
         else "With this cost per email, target the top of the list")
ax.set_title(title, loc="left", fontsize=13, fontweight="bold")
chart_col, _ = st.columns([3, 2])
chart_col.pyplot(fig)
st.caption("Extra visits come from the held-out 30% of customers, estimated using the random assignment, "
           "so the curve reflects what targeting achieved on customers the model never saw.")

# Section 3: policies tested
st.header("3. How targeting policies compared on unseen customers")
p = policies.rename(columns={"policy": "Policy", "emails_sent_per_1000": "Emails per 1,000",
                             "visits_per_1000": "Visits per 1,000", "spend_per_1000": "Spend per 1,000 ($)"})
p["Policy"] = p["Policy"].str.replace("Womens", "Women's").str.replace("Mens", "Men's")
p["95% interval for spend ($)"] = p["ci_low"].map("{:,.0f}".format) + " to " + p["ci_high"].map("{:,.0f}".format)
st.dataframe(p[["Policy", "Emails per 1,000", "Visits per 1,000", "Spend per 1,000 ($)", "95% interval for spend ($)"]],
             hide_index=True, width="stretch")
st.caption("Data: Kevin Hillstrom, MineThatData E-Mail Analytics And Data Mining Challenge (2008).")
