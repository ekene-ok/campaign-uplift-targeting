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

# Chart 2: what a targeting model adds over the best choice without one ----------------------
be = pd.read_csv(RES / "breakeven_curve.csv")
v = float(pd.read_csv(RES / "value_per_visit.csv").iloc[0, 0])
be["cost"] = be.cost_per_contact_in_visits * v
be = be[be.cost <= 1.6]
be["no_model"] = be.net_visits_send_all.clip(lower=0) * v   # email everyone, or skip the campaign once that loses money
be["model"] = be.net_visits_targeted * v
cross = be.iloc[0].net_visits_send_all / 1000 * v
gap = (be.model - be.no_model).max()
fig, ax = b.figure(8, 5)
ax.fill_between(be.cost, be.no_model, be.model, where=be.model >= be.no_model, color=HL, alpha=0.18, linewidth=0)
ax.plot(be.cost, be.no_model, color=b.CONTEXT, linewidth=2.2)
ax.plot(be.cost, be.model, color=HL, linewidth=2.6)
ax.axvline(cross, color=b.HAIRLINE, linewidth=1)
ax.text(cross + 0.03, 780, f"At ${cross:.2f} a contact, emailing\neveryone stops paying, so\nwithout a model you skip it",
        fontsize=9.5, color=b.MUTED, va="top")
ax.text(0.33, 590, "With the model", fontsize=10, color=HL, ha="left")
ax.text(0.03, 290, "Best choice without a model:\nemail everyone", fontsize=10, color=b.MUTED, ha="left", va="top")
ax.text(1.02, 75, f"Shaded gap = what the model adds,\nnever more than ${gap:.0f} per 1,000 customers",
        fontsize=9.5, color=b.INK, va="bottom")
ax.set_xlim(0, 1.6)
ax.set_ylim(-20, 880)
ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5])
ax.set_xticklabels(["$0", "$0.25", "$0.50", "$0.75", "$1.00", "$1.25", "$1.50"])
ax.set_yticks([0, 200, 400, 600, 800])
ax.set_yticklabels(["$0", "$200", "$400", "$600", "$800"])
ax.set_xlabel("Cost per contact", color=b.MUTED, fontsize=10)
ax.set_ylabel("Net revenue per 1,000 customers", color=b.MUTED, fontsize=10)
b.clean(ax, keep="x")
ax.axhline(0, color=b.HAIRLINE, linewidth=1)
b.headline(fig, "A targeting model adds little at any contact cost",
           f"Net revenue per 1,000 customers, valuing an extra visit at ${v:.0f} (revenue per extra visit in the test)")
b.source(fig, SRC)
b.finish(fig, OUT / "02_when_targeting_pays.png", top=0.82, bottom=0.17, left=0.12)
print("charts saved")
