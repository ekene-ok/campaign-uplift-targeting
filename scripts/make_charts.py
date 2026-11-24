"""README charts in the portfolio chart style: one message per chart, one highlight colour, short direct labels."""
from pathlib import Path
import sys
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
import brand_style as b

ROOT = Path(__file__).resolve().parents[1]
RES, OUT = ROOT / "results", ROOT / "charts"
OUT.mkdir(exist_ok=True)
HL = b.PROJECT["campaign-uplift-targeting"]
SRC = "Kevin Hillstrom MineThatData email test, 64,000 customers; policy results on a held-out 30%"

# Chart 1: one email does almost all the work
pol = pd.read_csv(RES / "policy_comparison.csv").set_index("policy")
base = pol.loc["Email nobody", "visits_per_1000"]
keys = ["Womens email to everyone", "Mens email to everyone", "Model picks the email, everyone"]
vals = [pol.loc[k, "visits_per_1000"] - base for k in keys]
gain = pd.read_csv(RES / "is_the_difference_real.csv").iloc[0]
fig, ax = b.chart(height=3.8, label_in=1.5)
b.hbar(ax, ["Women's email", "Men's email", "Model's pick"], vals, {1}, lambda v: f"+{v:.0f}", HL)
b.titles(fig, "One email does almost all the work",
         f"Extra site visits per 1,000 customers vs no email. The model's extra {gain.estimate:.0f} is within noise")
b.credit(fig, SRC)
b.save(fig, OUT / "01_one_email_does_the_work.png")

# Chart 2: what a targeting model adds over the best choice without one
be = pd.read_csv(RES / "breakeven_curve.csv")
v = float(pd.read_csv(RES / "value_per_visit.csv").iloc[0, 0])
be["cost"] = be.cost_per_contact_in_visits * v
be = be[be.cost <= 1.6]
be["no_model"] = be.net_visits_send_all.clip(lower=0) * v   # email everyone, or skip once that loses money
be["model"] = be.net_visits_targeted * v
cross = be.iloc[0].net_visits_send_all / 1000 * v
fig, ax = b.chart(height=4.6, label_in=0.45, xaxis=True, right_in=0.4)
ax.fill_between(be.cost, be.no_model, be.model, where=be.model >= be.no_model, color=HL, alpha=0.15, linewidth=0)
ax.plot(be.cost, be.no_model, color=b.CONTEXT, linewidth=2.2)
ax.plot(be.cost, be.model, color=HL, linewidth=2.4)
ax.axvline(cross, color=b.HAIRLINE, linewidth=1)
ax.text(cross + 0.03, 760, f"${cross:.2f}: a mass\nsend stops paying", fontsize=9.5, color=b.MUTED, va="top")
ax.text(0.3, 640, "With the model", fontsize=b.VALUE, color=HL)
ax.text(0.06, 330, "Without a model", fontsize=b.VALUE, color=b.MUTED)
ax.set_xlim(0, 1.6)
ax.set_ylim(0, 880)
ax.set_xticks([0, 0.5, 1.0, 1.5])
ax.set_xticklabels(["$0", "$0.50", "$1.00", "$1.50"])
ax.set_yticks([400, 800])
ax.set_yticklabels(["$400", "$800"])
ax.set_xlabel("Cost per contact", fontsize=9.5, color=b.MUTED)
b.line_axes(ax)
b.titles(fig, "A targeting model adds little at any contact cost",
         "Net revenue per 1,000 customers. The shaded gap is what the model adds")
b.credit(fig, SRC)
b.save(fig, OUT / "02_when_targeting_pays.png")
print("charts saved")
