"""README charts in the portfolio chart style: one message per chart, one highlight colour, direct labels."""
from pathlib import Path
import sys
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
import brand_style as b

ROOT = Path(__file__).resolve().parents[1]
RES, OUT = ROOT / "results", ROOT / "charts"
OUT.mkdir(exist_ok=True)
HL = b.PROJECT["campaign-uplift-targeting"]
SRC = "Kevin Hillstrom MineThatData email test (64,000 customers); held-out 30% for policy results"

# Chart 1: one email does almost all the work -------------------------------------------------
pol = pd.read_csv(RES / "policy_comparison.csv").set_index("policy")
base = pol.loc["Email nobody", "visits_per_1000"]
rows = [("Women's email to everyone", "Womens email to everyone"),
        ("Men's email to everyone", "Mens email to everyone"),
        ("Model picks each customer's email", "Model picks the email, everyone")]
vals = [pol.loc[k, "visits_per_1000"] - base for _, k in rows]
fig, ax = b.figure(8, 4.2)
colors = [b.CONTEXT, HL, b.CONTEXT]
bars = ax.barh([r[0] for r in rows][::-1], vals[::-1], color=colors[::-1], height=0.55)
gain = pd.read_csv(RES / "is_the_difference_real.csv").iloc[0]
notes = ["", "", f"  only +{gain.estimate:.0f} more, not a clear gain"][::-1]
for bar, v, note, c in zip(bars, vals[::-1], notes, colors[::-1]):
    ax.text(v + 1, bar.get_y() + bar.get_height() / 2, f"+{v:.0f}", va="center", fontsize=11.5,
            color=b.INK)
    if note:
        ax.text(v + 17, bar.get_y() + bar.get_height() / 2, note.strip(), va="center", fontsize=9.5, color=b.MUTED)
ax.set_xlim(0, max(vals) * 2.15)
ax.set_xticks([])
b.clean(ax, keep="y")
b.headline(fig, "One email does almost all the work",
           "Extra website visits per 1,000 customers, compared with sending no email")
b.source(fig, SRC)
b.finish(fig, OUT / "01_one_email_does_the_work.png", top=0.80, bottom=0.12, left=0.33)

# Chart 2: targeting pays only once contacts cost real money ----------------------------------
be = pd.read_csv(RES / "breakeven_curve.csv")
v = float(pd.read_csv(RES / "value_per_visit.csv").iloc[0, 0])
be["cost"] = be.cost_per_contact_in_visits * v
be = be[be.cost <= 1.6]
fig, ax = b.figure(8, 5)
ax.plot(be.cost, be.net_visits_send_all * v, color=b.CONTEXT, linewidth=2.2)
ax.plot(be.cost, be.net_visits_targeted * v, color=HL, linewidth=2.6)
ax.axhline(0, color=b.HAIRLINE, linewidth=1)
cross = be.iloc[0].net_visits_send_all / 1000 * v  # average extra visits per contact x value per visit
ax.axvline(cross, color=b.HAIRLINE, linewidth=1)
ax.text(cross + 0.03, be.net_visits_targeted.max() * v * 0.95, f"Sending to everyone stops\npaying at about ${cross:.2f}",
        fontsize=9.5, color=b.MUTED, va="top")
end = be.iloc[-1]
ax.text(end.cost + 0.02, end.net_visits_send_all * v, "Email everyone", va="center", fontsize=10, color=b.MUTED)
ax.text(1.02, be[be.cost.between(0.95, 1.05)].net_visits_targeted.mean() * v + 40,
        "Contact only predicted\ntop responders", va="bottom", fontsize=10, color=HL)
ax.set_xlim(0, 1.95)
ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5])
ax.set_xticklabels(["$0", "$0.25", "$0.50", "$0.75", "$1.00", "$1.25", "$1.50"])
ax.set_yticks([-500, 0, 500])
ax.set_yticklabels(["-$500", "$0", "$500"])
ax.set_xlabel("Cost per contact", color=b.MUTED, fontsize=10)
b.clean(ax, keep="x")
b.headline(fig, "Targeting only pays once each contact costs real money",
           f"Net revenue per 1,000 customers, valuing an extra visit at ${v:.0f} (revenue per extra visit in the test)")
b.source(fig, SRC)
b.finish(fig, OUT / "02_when_targeting_pays.png", top=0.82, bottom=0.17, left=0.09)
print("charts saved")
