"""README charts: one message per chart, one highlight colour, direct labels."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RES, OUT = ROOT / "results", ROOT / "charts"
OUT.mkdir(exist_ok=True)
SURFACE, INK, INK2 = "#ffffff", "#1a1a1a", "#6b6a66"
HIGHLIGHT, CONTEXT = "#e0612e", "#d9d8d3"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "text.color": INK,
                     "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})


def hbar(ax, labels, values, hi_index, fmt, xmax):
    colors = [HIGHLIGHT if i == hi_index else CONTEXT for i in range(len(values))]
    ax.barh(labels, values, height=0.5, color=colors)
    for y, v in enumerate(values):
        hi = y == hi_index
        ax.text(v + xmax * 0.015, y, fmt(v), va="center", fontsize=12 if hi else 11,
                fontweight="bold" if hi else "normal", color=INK if hi else INK2)
    for i, lbl in enumerate(ax.get_yticklabels()):
        lbl.set_color(INK if i == hi_index else INK2)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([])
    ax.tick_params(axis="y", length=0, pad=8)
    ax.set_xlim(0, xmax)


def titles(fig, title, subtitle):
    fig.text(0.03, 0.97, title, fontsize=15, fontweight="bold", va="top")
    fig.text(0.03, 0.88, subtitle, fontsize=10.5, color=INK2, va="top")


# Chart 1: extra spend per 1,000 customers emailed
lift = pd.read_csv(RES / "lift_with_confidence_intervals.csv").query("metric == 'spend'").set_index("arm")
vals = [lift.loc["Womens E-Mail", "uplift"] * 1000, lift.loc["Mens E-Mail", "uplift"] * 1000]
fig, ax = plt.subplots(figsize=(9, 3.8))
hbar(ax, ["Women's email", "Men's email"], vals, 1, lambda v: f"${v:,.0f}", 1000)
titles(fig, "The men's email drove 1.8x the extra spend of the women's",
       "Extra spend per 1,000 customers in the two weeks after the email, compared with\n"
       "customers who received no email (randomised test, 64,000 customers).")
fig.subplots_adjust(left=0.2, right=0.97, top=0.66, bottom=0.05)
fig.savefig(OUT / "01_extra_spend_by_email.png", dpi=200)
plt.close(fig)

# Chart 2: the women's email barely moves men-only buyers
seg = pd.read_csv(RES / "segment_uplift.csv").query("dimension == 'Purchase history'").set_index("segment_value")
order = ["Bought mens only", "Bought both", "Bought womens only"][::-1]
labels = {"Bought mens only": "Men's products only", "Bought both": "Both", "Bought womens only": "Women's products only"}
vals = [seg.loc[o, "visit_uplift_womens"] * 100 for o in order]
fig, ax = plt.subplots(figsize=(9, 4.2))
hbar(ax, [labels[o] for o in order], vals, 2, lambda v: f"+{v:.1f} pts", 10)
titles(fig, "The women's email barely moves men-only buyers",
       "Increase in website visit rate from the women's email, by what customers bought before.\n"
       "The men's email lifts men-only buyers by +6.9 pts.")
fig.subplots_adjust(left=0.27, right=0.97, top=0.68, bottom=0.05)
fig.savefig(OUT / "02_womens_email_by_history.png", dpi=200)
plt.close(fig)
print("Charts saved to charts/")
