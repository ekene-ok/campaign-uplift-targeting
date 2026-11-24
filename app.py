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
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
import brand_style as b

st.set_page_config(page_title="Campaign Uplift Targeting", layout="wide")
RES = Path(__file__).resolve().parent / "results"
HL = b.PROJECT["campaign-uplift-targeting"]
HIGHLIGHT, CONTEXT, INK, INK2 = HL, b.CONTEXT, b.INK, b.MUTED


@st.cache_data
def load():
    t = pd.read_csv(RES / "targeting_list.csv")
    t["past_spend"] = t["history_segment"].str.replace(r"^\d\) ", "", regex=True).str.replace(" - ", " to ")
    t["tenure"] = np.where(t["newbie"] == 1, "New (last 12 months)", "Existing")
    be = pd.read_csv(RES / "breakeven_curve.csv")
    policies = pd.read_csv(RES / "policy_comparison.csv")
    real = pd.read_csv(RES / "is_the_difference_real.csv")
    v = float(pd.read_csv(RES / "value_per_visit.csv").iloc[0, 0])
    return t, be, policies, real, v


t, be, policies, real, VALUE_PER_VISIT = load()
BLANKET_VISITS = float(be.iloc[0]["net_visits_send_all"])  # extra visits per 1,000 from contacting everyone

st.title("Is personalised targeting worth it?")
st.write("Explore the results of a randomised email test with 64,000 customers: one group got a men's merchandise "
         "email, one a women's email, and one nothing. Uplift is the extra visits an email caused compared with "
         "sending nothing. The short answer: for email, one well-chosen email to everyone does almost all the work. "
         "Targeting starts to pay once each contact costs real money. [Read the full analysis](https://github.com/ekene-ok/campaign-uplift-targeting)")

# Section 2: is targeting worth it?
st.header("1. Is targeting worth it for your channel?")
st.write("Targeting means contacting only the customers the model expects to respond. It saves money when each "
         "contact costs something real (a discount, a printed mailer, a sales call). Set your cost per contact and "
         "what an extra website visit is worth to you.")
c1, c2 = st.columns(2)
cost = c1.slider("Cost per contact ($)", 0.00, 2.00, 0.01, 0.01,
                 help="Email is close to $0. Direct mail is often $0.60 to $1.50. Include any discount you give away.")
value = c2.slider("Value of one extra website visit ($)", 1.00, 30.00, float(round(VALUE_PER_VISIT, 2)), 0.50,
                  help=f"The test produced about ${VALUE_PER_VISIT:.0f} of revenue per extra visit. Use profit per visit for a stricter view.")

ratio = cost / value
r = be["cost_per_contact_in_visits"].to_numpy()
tgt = np.interp(ratio, r, be["net_visits_targeted"]) if ratio <= r.max() else 0.0
share = np.interp(ratio, r, be["share_contacted"]) if ratio <= r.max() else 0.0
blanket = BLANKET_VISITS - ratio * 1000
net_all, net_tgt = blanket * value, tgt * value
def money(x):
    return f"-${abs(x):,.0f}" if x < 0 else f"${x:,.0f}"

# Targeting is the call only when it leaves a real share of customers out AND clearly beats contacting everyone
best_is_target = 0.02 <= share < 0.9 and net_tgt - net_all > 20
n1, n2, n3 = st.columns(3)
n1.metric("Net value, contact everyone (per 1,000)", money(net_all))
n2.metric("Net value, contact predicted responders (per 1,000)", money(net_tgt))
n3.metric("Share of customers worth contacting", f"{share:.0%}")
if best_is_target:
    st.success(f"Target. At ${cost:.2f} a contact, contact only the top {share:.0%} of customers by predicted uplift.")
elif net_all > 0:
    st.info("Contact everyone with the men's email. At this cost, targeting adds too little to be worth the extra work.")
else:
    st.warning("Don't run this campaign. At this cost, even the best responders don't cover what each contact costs.")

costs = np.linspace(0, 2, 81)
rr = costs / value
fig, ax = plt.subplots(figsize=(8, 3.6))
y_all = (BLANKET_VISITS - rr * 1000) * value
y_tgt = np.where(rr <= r.max(), np.interp(rr, r, be["net_visits_targeted"]), 0) * value
ax.plot(costs, y_all, color=b.CONTEXT, linewidth=2.2)
ax.plot(costs, y_tgt, color=HL, linewidth=2.6)
ax.axhline(0, color=b.HAIRLINE, linewidth=1)
ax.scatter([cost], [net_tgt if best_is_target else net_all], color=b.INK, s=40, zorder=3)
ax.text(costs[-1] + 0.03, y_all[-1], "Contact everyone", va="center", fontsize=9, color=b.MUTED)
ax.text(costs[-1] + 0.03, y_tgt[-1], "Contact predicted\nresponders", va="center", fontsize=9, color=HL)
ax.set_xlim(0, 2.45)
ax.set_xlabel("Cost per contact", color=b.MUTED)
b.clean(ax, keep="x")
from matplotlib.ticker import FuncFormatter
ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:.2f}"))
ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"-${abs(y):,.0f}" if y < 0 else f"${y:,.0f}"))
ax.tick_params(axis="y", labelsize=9)
ax.set_title("Net value per 1,000 customers as the cost per contact rises", loc="left", fontsize=12, color=b.INK)
chart_col, _ = st.columns([3, 2])
chart_col.pyplot(fig)
st.caption(f"Contacting everyone stops paying once a contact costs more than about {BLANKET_VISITS / 10:.1f}% of an "
           "extra visit's value. Results are measured on the held-out 30% of customers using the random assignment.")

# Section 1: segment explorer
st.header("2. Which email works for which customers?")
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
        ax.text(v + 0.2, y, f"+{v:.1f} visits per 100", va="center", color=INK if y == hi else INK2)
    ax.set_xlim(0, max(vals) * 1.45 + 0.5)
    ax.set_xticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_title(f"For this segment, the {better} email works better", loc="left", fontsize=12, color=INK)
    chart_col, _ = st.columns([3, 2])
    chart_col.pyplot(fig)
    st.caption("Predicted by the uplift model (one model per test group). Values are averages across the segment.")

# Section 3: policies tested
st.header("3. How targeting policies compared on unseen customers")
p = policies.rename(columns={"policy": "Policy", "emails_sent_per_1000": "Emails per 1,000",
                             "visits_per_1000": "Visits per 1,000", "spend_per_1000": "Spend per 1,000 ($)"})
p["Policy"] = p["Policy"].str.replace("Womens", "Women's").str.replace("Mens", "Men's")
p["95% interval for spend ($)"] = p["ci_low"].map("{:,.0f}".format) + " to " + p["ci_high"].map("{:,.0f}".format)
st.dataframe(p[["Policy", "Emails per 1,000", "Visits per 1,000", "Spend per 1,000 ($)", "95% interval for spend ($)"]],
             hide_index=True, width="stretch")
g = real.iloc[0]
st.caption(f"The model adds {g.estimate:+.1f} visits per 1,000 over sending everyone the men's email (95% interval {g.ci_low:+.1f} to {g.ci_high:+.1f}), so it is not a clear improvement. Spend differences between "
           "policies are directional only: about 1% of customers buy, so the intervals overlap.")
st.caption("Data: Kevin Hillstrom, MineThatData E-Mail Analytics And Data Mining Challenge (2008).")
