"""Interactive explorer for the campaign uplift targeting analysis.

Run locally:  streamlit run app.py
Uses the model outputs in results/, so it runs without the raw dataset.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
import brand_style as b

st.set_page_config(page_title="Is personalised targeting worth it?", page_icon="✉️", layout="centered",
                   initial_sidebar_state="collapsed")
RES = Path(__file__).resolve().parent / "results"
HL, GREY, INK, MUTED, RULE = b.PROJECT["campaign-uplift-targeting"], "#c9c6bf", "#1d2433", "#5b6170", "#e3e5ea"
FONT = "Albert Sans"
FONTS = "'Albert Sans', Helvetica, Arial, sans-serif"
VFONT = "Albert Sans, Helvetica, Arial, sans-serif"  # for chart text

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Albert+Sans:wght@400;500;600;700&display=swap');
html, body, .stApp, .stMarkdown p, h1, h2, h3, label, button p, input {{ font-family: {FONTS}; }}
header[data-testid="stHeader"], [data-testid="stToolbar"], footer {{ display: none; }}
.block-container {{ padding-top: 2.5rem; max-width: 820px; }}
h1 {{ font-weight: 700; letter-spacing: -0.02em; font-size: 2.4rem; line-height: 1.1; color: {INK}; }}
h2 {{ font-weight: 600; letter-spacing: -0.01em; font-size: 1.45rem; color: {INK}; margin-top: 2.2rem; }}
p, li {{ color: {INK}; font-size: 1.02rem; line-height: 1.55; }}
.sub {{ color: {MUTED}; font-size: 1.1rem; margin-top: -0.6rem; max-width: 62ch; }}
.verdict {{ border-left: 4px solid {HL}; padding: 0.4rem 0 0.4rem 1.1rem; margin: 1.6rem 0 1.2rem; }}
.verdict .big {{ font-size: 1.6rem; font-weight: 600; line-height: 1.25; color: {INK}; }}
.verdict .why {{ color: {MUTED}; margin-top: 0.4rem; font-size: 1rem; }}
.figs {{ display: flex; gap: 2.5rem; flex-wrap: wrap; margin: 0.4rem 0 1rem; }}
.fig .n {{ font-size: 1.7rem; font-weight: 600; color: {INK}; font-variant-numeric: tabular-nums; }}
.fig .l {{ color: {MUTED}; font-size: 0.9rem; max-width: 22ch; line-height: 1.35; }}
.note {{ color: {MUTED}; font-size: 0.9rem; }}
.foot {{ border-top: 1px solid {RULE}; margin-top: 3rem; padding-top: 1rem; color: {MUTED}; font-size: 0.92rem; }}
.foot a, .sub a {{ color: {INK}; }}
</style>""", unsafe_allow_html=True)


@st.cache_data
def load():
    t = pd.read_csv(RES / "targeting_list.csv")
    t["past_spend"] = t["history_segment"].str.replace(r"^\d\) ", "", regex=True).str.replace(" - ", " to ")
    t["tenure"] = np.where(t["newbie"] == 1, "New this year", "Existing")
    t["bought"] = t["purchase_history"].map({"Bought both": "Both", "Bought mens only": "Men's items only",
                                             "Bought womens only": "Women's items only"}).fillna(t["purchase_history"])
    be = pd.read_csv(RES / "breakeven_curve.csv")
    policies = pd.read_csv(RES / "policy_comparison.csv")
    real = pd.read_csv(RES / "is_the_difference_real.csv")
    v = float(pd.read_csv(RES / "value_per_visit.csv").iloc[0, 0])
    return t, be, policies, real, v


t, be, policies, real, VALUE_PER_VISIT = load()
BLANKET_VISITS = float(be.iloc[0]["net_visits_send_all"])  # extra visits per 1,000 from emailing everyone
r = be["cost_per_contact_in_visits"].to_numpy()


def money(x):
    return f"-${abs(x):,.0f}" if x < 0 else f"${x:,.0f}"


def outcome(cost, value):
    """Net value per 1,000 customers without a model (email everyone or skip) and with the model."""
    ratio = cost / value
    tgt = np.interp(ratio, r, be["net_visits_targeted"]) if ratio <= r.max() else 0.0
    share = np.interp(ratio, r, be["share_contacted"]) if ratio <= r.max() else 0.0
    everyone = (BLANKET_VISITS - ratio * 1000) * value
    return max(everyone, 0.0), everyone, tgt * value, share


st.title("Is personalised targeting worth it?")
st.markdown("<p class='sub'>Pick your channel and see whether to contact everyone, target a smaller group, or skip "
            "the campaign. Based on a real email test with 64,000 customers.</p>", unsafe_allow_html=True)

# Channel presets set the cost per contact; the slider stays available for any other figure
PRESETS = {"Email": 0.01, "Direct mail": 0.90, "Discount or sales call": 1.50}
if "cost" not in st.session_state:
    st.session_state.cost = PRESETS["Email"]


def use_preset():
    choice = st.session_state.channel
    if choice in PRESETS:
        st.session_state.cost = PRESETS[choice]


st.segmented_control("Your channel", list(PRESETS), key="channel", default="Email", on_change=use_preset)
c1, c2 = st.columns(2)
cost = c1.slider("What each contact costs you", 0.00, 2.00, key="cost", step=0.01, format="$%.2f",
                 help="Email is close to $0. Printed mail is often $0.60 to $1.50. Include any discount you give away.")
value = c2.slider("What one extra website visit is worth", 1.0, 30.0, float(round(VALUE_PER_VISIT, 2)), 0.5,
                  format="$%.2f", help=f"In this test, each extra visit brought in about ${VALUE_PER_VISIT:.0f} of sales.")

no_model, everyone, with_model, share = outcome(cost, value)
gain = with_model - no_model
target = 0.02 <= share < 0.9 and gain > 20
if target:
    big = f"Target. Contact only the {share:.0%} of customers most likely to respond."
    why = f"At ${cost:.2f} a contact, emailing everyone no longer pays, but this smaller group still earns {money(with_model)} per 1,000 customers."
elif everyone > 0:
    big = "Contact everyone with the same email."
    why = f"Choosing a different email for each person would add only {money(max(gain, 0))} per 1,000 customers, not enough to justify a second email and a model."
else:
    big = "Skip this campaign."
    why = f"At ${cost:.2f} a contact, even the customers most likely to respond don't cover the cost."
st.markdown(f"<div class='verdict'><div class='big'>{big}</div><div class='why'>{why}</div></div>",
            unsafe_allow_html=True)
st.markdown(f"""<div class='figs'>
<div class='fig'><div class='n'>{money(no_model)}</div><div class='l'>per 1,000 customers, sending one email to everyone (or nothing, once that loses money)</div></div>
<div class='fig'><div class='n'>{money(with_model)}</div><div class='l'>per 1,000 customers, contacting only who a model picks</div></div>
<div class='fig'><div class='n'>{share:.0%}</div><div class='l'>of customers the model would contact</div></div>
</div>""", unsafe_allow_html=True)

# The cost ruler: value per 1,000 customers with and without a model, as the cost per contact rises
costs = np.round(np.linspace(0, 2, 161), 4)
rows = []
for c in costs:
    nm, _, wm, _ = outcome(c, value)
    rows += [{"cost": c, "value": nm, "how": "One email to everyone"}, {"cost": c, "value": wm, "how": "Contact who a model picks"}]
d = pd.DataFrame(rows)
break_even = BLANKET_VISITS / 1000 * value
base = alt.Chart(d).encode(x=alt.X("cost:Q", title="What each contact costs you",
                                   axis=alt.Axis(format="$.2f", grid=False, tickCount=5)))
lines = base.mark_line(strokeWidth=2.6).encode(
    y=alt.Y("value:Q", title=None, axis=alt.Axis(format="$,.0f", grid=False, tickCount=4)),
    color=alt.Color("how:N", scale=alt.Scale(domain=["One email to everyone", "Contact who a model picks"], range=[GREY, HL]), legend=None),
    tooltip=[alt.Tooltip("cost:Q", title="Cost per contact", format="$.2f"), alt.Tooltip("how:N", title=""),
             alt.Tooltip("value:Q", title="Per 1,000 customers", format="$,.0f")])
labels = alt.Chart(pd.DataFrame([
    {"cost": 0.16, "value": outcome(0.16, value)[2] + 70, "t": "Contact who a model picks", "c": HL},
    {"cost": break_even + 0.04, "value": 160, "t": f"${break_even:.2f}", "c": MUTED},
])).mark_text(align="left", fontSize=13, font=VFONT).encode(x="cost:Q", y="value:Q", text="t:N", color=alt.Color("c:N", scale=None))
rule = alt.Chart(pd.DataFrame({"cost": [break_even]})).mark_rule(color=RULE, strokeWidth=1.5).encode(x="cost:Q")
you = alt.Chart(pd.DataFrame({"cost": [cost], "value": [with_model if target else no_model]})).mark_point(
    filled=True, size=90, color=INK).encode(x="cost:Q", y="value:Q")
st.markdown(f"<p style='font-weight:600;font-size:1.1rem;margin:1.2rem 0 0'>A model only earns its keep once contacts get expensive</p>"
            f"<p class='note'>Value per 1,000 customers. Emailing everyone stops paying at ${break_even:.2f} a contact (the grey line). The dot is your channel.</p>",
            unsafe_allow_html=True)
chart = (rule + lines + labels + you).properties(height=280).configure_view(stroke=None).configure_axis(labelFont=VFONT, titleFont=VFONT, labelColor=MUTED, titleColor=MUTED,
                                              domainColor=RULE, tickColor=RULE, labelFontSize=12, titleFontSize=12, titleFontWeight="normal")
st.altair_chart(chart, width='stretch')
st.markdown("<p class='note'>Measured on 30% of customers the model never saw, using the test's random groups.</p>",
            unsafe_allow_html=True)

# Which email for which customers
st.header("Which email works for which customers?")
st.markdown("<p>The test sent a men's email, a women's email or nothing. Narrow down the customers to see which "
            "email brings more extra visits.</p>", unsafe_allow_html=True)
spend_order = sorted(t["past_spend"].unique(), key=lambda s: float(s.split(" ")[0].replace("$", "").replace(",", "").replace("+", "")))
f1, f2 = st.columns(2)
BOUGHT = ["Men's items only", "Women's items only", "Both"]
hist = f1.pills("Bought before", BOUGHT, selection_mode="multi", default=BOUGHT)
tenure = f2.pills("Customer since", ["Existing", "New this year"], selection_mode="multi", default=["Existing", "New this year"])
spend = st.pills("Spent in the past year", spend_order, selection_mode="multi", default=spend_order)
seg = t[t["bought"].isin(hist or []) & t["past_spend"].isin(spend or []) & t["tenure"].isin(tenure or [])]

if seg.empty:
    st.markdown("<p class='note'>No customers match. Select at least one option in each row.</p>", unsafe_allow_html=True)
else:
    mens, womens = seg["uplift_mens"].mean() * 100, seg["uplift_womens"].mean() * 100
    better = "men's" if mens >= womens else "women's"
    e = pd.DataFrame({"email": ["Men's email", "Women's email"], "v": [mens, womens]})
    e["c"] = np.where(e["v"] == e["v"].max(), HL, GREY)
    e["t"] = e["v"].map(lambda v: f"+{v:.1f}")
    bars = alt.Chart(e).mark_bar(height=26, cornerRadiusEnd=2).encode(
        y=alt.Y("email:N", title=None, sort=None, axis=alt.Axis(domain=False, ticks=False, labelFontSize=13, labelColor=INK, labelPadding=8)),
        x=alt.X("v:Q", title=None, axis=None, scale=alt.Scale(domain=[0, max(e.v) * 1.5])), color=alt.Color("c:N", scale=None))
    txt = bars.mark_text(align="left", dx=6, fontSize=13, font=VFONT, color=INK).encode(text="t:N", color=alt.value(INK))
    st.markdown(f"<p style='font-weight:600;font-size:1.1rem;margin:1rem 0 0'>For these {len(seg):,} customers, the {better} email brings more visits</p>"
                "<p class='note'>Predicted extra visits per 100 customers, compared with sending nothing.</p>", unsafe_allow_html=True)
    st.altair_chart((bars + txt).properties(height=90).configure_view(stroke=None).configure_axis(labelFont=VFONT),
                    width='stretch')

with st.expander("How each approach performed on customers the model never saw"):
    p = policies.copy()
    p["policy"] = p["policy"].str.replace("Womens", "Women's").str.replace("Mens", "Men's")
    p = p.rename(columns={"policy": "Approach", "emails_sent_per_1000": "Emails sent per 1,000",
                          "visits_per_1000": "Visits per 1,000", "spend_per_1000": "Sales per 1,000"})
    p["Sales per 1,000"] = p["Sales per 1,000"].map("${:,.0f}".format)
    p["Likely range of sales"] = p["ci_low"].map("${:,.0f}".format) + " to " + p["ci_high"].map("${:,.0f}".format)
    st.dataframe(p[["Approach", "Emails sent per 1,000", "Visits per 1,000", "Sales per 1,000", "Likely range of sales"]],
                 hide_index=True, width='stretch')
    g = real.iloc[0]
    st.markdown(f"<p class='note'>Letting a model pick the email adds {g.estimate:+.1f} visits per 1,000 over sending "
                f"everyone the men's email, with a likely range of {g.ci_low:+.1f} to {g.ci_high:+.1f}. Because that range "
                "includes zero, the model is not a clear improvement. Only about 1% of customers buy, so sales "
                "differences between approaches are too small to read reliably.</p>", unsafe_allow_html=True)

st.markdown("""<div class='foot'>Made by Ekene Okafor. Read the <a href="https://github.com/ekene-ok/campaign-uplift-targeting">full analysis and code on GitHub</a>,
or <a href="https://linkedin.com/in/cnokafor">connect on LinkedIn</a>.<br>
Data: Kevin Hillstrom, MineThatData E-Mail Analytics and Data Mining Challenge (2008).</div>""", unsafe_allow_html=True)
