"""Campaign uplift targeting pipeline.

1. SQL: topline arm results, balance check, segment-level uplift
2. Statistics: lift with 95% confidence intervals for each email vs control
3. Uplift model (T-learner): predict each customer's visit probability under each arm,
   then recommend the email with the highest predicted uplift
4. Evaluate on a held-out 30% using the randomisation (inverse probability weighting):
   cumulative incremental visits by targeting depth, and spend under alternative policies

Usage (repo root):  python scripts/run_all.py
"""
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)
SEED = 42
rng = np.random.default_rng(SEED)

# 1. SQL -------------------------------------------------------------------------
con = duckdb.connect()
con.execute(f"SET file_search_path = '{ROOT}'")
for f in sorted((ROOT / "sql").glob("*.sql")):
    con.execute(f.read_text())
for view in ["arm_results", "balance_check", "segment_uplift"]:
    con.sql(f"SELECT * FROM {view}").write_csv(str(OUT / f"{view}.csv"))
df = con.sql("SELECT * FROM customers").df()
ARMS = ["No E-Mail", "Mens E-Mail", "Womens E-Mail"]


# 2. Lift with confidence intervals -------------------------------------------------
def diff_ci(a, b, n_boot=2000):
    """Difference in means (a minus b) with a bootstrap 95% CI."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    boots = [rng.choice(a, a.size).mean() - rng.choice(b, b.size).mean() for _ in range(n_boot)]
    return a.mean() - b.mean(), *np.percentile(boots, [2.5, 97.5])

rows = []
ctrl = df[df.segment == "No E-Mail"]
for arm in ARMS[1:]:
    t = df[df.segment == arm]
    for metric in ["visit", "conversion", "spend"]:
        d, lo, hi = diff_ci(t[metric], ctrl[metric])
        rows.append({"arm": arm, "metric": metric, "control": round(ctrl[metric].mean(), 5),
                     "treated": round(t[metric].mean(), 5), "uplift": round(d, 5),
                     "ci_low": round(lo, 5), "ci_high": round(hi, 5),
                     "relative_lift": round(d / ctrl[metric].mean(), 3)})
lift = pd.DataFrame(rows)
lift.to_csv(OUT / "lift_with_confidence_intervals.csv", index=False)

# 3. T-learner uplift model -----------------------------------------------------------
FEATURES = ["recency", "history", "mens", "womens", "newbie"]
X = df[FEATURES].copy()
X = X.join(pd.get_dummies(df["zip_code"], prefix="zip").astype(int))
X = X.join(pd.get_dummies(df["channel"], prefix="channel").astype(int))
train_idx, test_idx = train_test_split(df.index, test_size=0.30, random_state=SEED,
                                       stratify=df["segment"])

pred = pd.DataFrame(index=df.index)
for arm in ARMS:
    tr = train_idx[df.loc[train_idx, "segment"] == arm]
    model = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_depth=3,
                                           min_samples_leaf=200, random_state=SEED)
    model.fit(X.loc[tr], df.loc[tr, "visit"])
    pred[arm] = model.predict_proba(X)[:, 1]
pred["uplift_mens"] = pred["Mens E-Mail"] - pred["No E-Mail"]
pred["uplift_womens"] = pred["Womens E-Mail"] - pred["No E-Mail"]
pred["recommended_email"] = np.where(pred["uplift_mens"] >= pred["uplift_womens"], "Mens E-Mail", "Womens E-Mail")
pred["best_uplift"] = pred[["uplift_mens", "uplift_womens"]].max(axis=1)

# 4. Held-out evaluation ----------------------------------------------------------------
# Each customer had a 1/3 chance of each arm, so weighting by 3 turns the matching
# customers into an unbiased estimate of what the whole test set would do under a policy.
test = df.loc[test_idx].join(pred.loc[test_idx])
P = 1 / 3

def policy_value(sub, assigned, metric):
    """Estimated total metric if every customer in `sub` received `assigned` (a Series of arms)."""
    match = sub["segment"] == assigned
    return (sub.loc[match, metric] / P).sum()

# Cumulative incremental visits by targeting depth (sorted by predicted uplift).
test_sorted = test.sort_values("best_uplift", ascending=False)
n = len(test_sorted)
depths = np.arange(0.05, 1.0001, 0.05)
curve = []
total_inc = (policy_value(test_sorted, test_sorted["recommended_email"], "visit")
             - policy_value(test_sorted, pd.Series("No E-Mail", index=test_sorted.index), "visit"))
for d in depths:
    top = test_sorted.iloc[: int(round(d * n))]
    inc = (policy_value(top, top["recommended_email"], "visit")
           - policy_value(top, pd.Series("No E-Mail", index=top.index), "visit"))
    curve.append({"share_emailed": round(d, 2), "incremental_visits": round(inc, 1),
                  "share_of_total_incremental": round(inc / total_inc, 3)})
curve = pd.DataFrame(curve)
curve.to_csv(OUT / "targeting_curve.csv", index=False)

# Spend per 1,000 customers under alternative policies, with bootstrap CIs.
top_half = test["best_uplift"] >= test["best_uplift"].quantile(0.5)
POLICIES = {
    "Email nobody": pd.Series("No E-Mail", index=test.index),
    "Womens email to everyone": pd.Series("Womens E-Mail", index=test.index),
    "Mens email to everyone": pd.Series("Mens E-Mail", index=test.index),
    "Model picks the email, everyone": test["recommended_email"],
    "Model picks the email, top 50% only": test["recommended_email"].where(top_half, "No E-Mail"),
}
prow = []
for name, assigned in POLICIES.items():
    match = (test["segment"] == assigned).to_numpy()
    w_spend = np.where(match, test["spend"].to_numpy() / P, 0.0)
    w_visit = np.where(match, test["visit"].to_numpy() / P, 0.0)
    boots = [rng.choice(w_spend, w_spend.size).mean() for _ in range(2000)]
    prow.append({"policy": name,
                 "emails_sent_per_1000": round((assigned != "No E-Mail").mean() * 1000),
                 "spend_per_1000": round(w_spend.mean() * 1000, 0),
                 "ci_low": round(np.percentile(boots, 2.5) * 1000, 0),
                 "ci_high": round(np.percentile(boots, 97.5) * 1000, 0),
                 "visits_per_1000": round(w_visit.mean() * 1000, 1)})
policies = pd.DataFrame(prow)
policies.to_csv(OUT / "policy_comparison.csv", index=False)

# Targeting list for the whole file (in practice: score the live customer base).
out = df[["customer_id", "purchase_history", "history_segment", "newbie", "channel"]].join(
    pred[["recommended_email", "uplift_mens", "uplift_womens", "best_uplift"]].round(4))
out["send_email"] = out["best_uplift"] >= out["best_uplift"].quantile(0.5)
out.sort_values("best_uplift", ascending=False).to_csv(OUT / "targeting_list.csv", index=False)
mix = out[out["send_email"]].groupby(["purchase_history", "recommended_email"]).size().unstack(fill_value=0)
mix.to_csv(OUT / "recommended_mix_top50.csv")

print(lift.to_string(index=False))
print(curve.iloc[[1, 3, 5, 7, 9, 13, 19]].to_string(index=False))
print(policies.to_string(index=False))
print(mix)
print(out.recommended_email.value_counts())

# 5. Is targeting worth it? ------------------------------------------------------------------
# a) Does the model beat the simple rule "men's email to everyone"? Paired bootstrap on the
#    held-out customers (same resample for both policies), visits per 1,000.
def ipw(sub, assigned, metric):
    return np.where((sub["segment"] == assigned).to_numpy(), sub[metric].to_numpy() / P, 0.0)

mens_all = pd.Series("Mens E-Mail", index=test.index)
v_model, v_mens = ipw(test, test["recommended_email"], "visit"), ipw(test, mens_all, "visit")
idx_boot = [rng.integers(0, len(test), len(test)) for _ in range(2000)]
gain = np.array([(v_model[i] - v_mens[i]).mean() * 1000 for i in idx_boot])
model_vs_rule = pd.DataFrame([{
    "comparison": "Model picks the email vs men's email to everyone", "unit": "extra visits per 1,000 customers",
    "estimate": round((v_model - v_mens).mean() * 1000, 1),
    "ci_low": round(np.percentile(gain, 2.5), 1), "ci_high": round(np.percentile(gain, 97.5), 1)}])

# b) Is the men's email really better than the women's? Bootstrap of the differences.
m, w, c = (df.loc[df.segment == a, "spend"].to_numpy() for a in ["Mens E-Mail", "Womens E-Mail", "No E-Mail"])
dd = [(rng.choice(m, m.size).mean() - rng.choice(c, c.size).mean())
      - (rng.choice(w, w.size).mean() - rng.choice(c, c.size).mean()) for _ in range(2000)]
mv, wv, cv = (df.loc[df.segment == a, "visit"].to_numpy() for a in ["Mens E-Mail", "Womens E-Mail", "No E-Mail"])
dv = [(rng.choice(mv, mv.size).mean() - rng.choice(wv, wv.size).mean()) for _ in range(2000)]
mens_vs_womens = pd.DataFrame([
    {"comparison": "Men's email vs women's email", "unit": "visit rate (percentage points)",
     "estimate": round((mv.mean() - wv.mean()) * 100, 2),
     "ci_low": round(np.percentile(dv, 2.5) * 100, 2), "ci_high": round(np.percentile(dv, 97.5) * 100, 2)},
    {"comparison": "Men's email vs women's email", "unit": "extra spend per customer ($)",
     "estimate": round(m.mean() - w.mean(), 3),
     "ci_low": round(np.percentile(dd, 2.5), 3), "ci_high": round(np.percentile(dd, 97.5), 3)}])
real = pd.concat([model_vs_rule, mens_vs_womens], ignore_index=True)
real["clear_difference"] = (real.ci_low > 0) | (real.ci_high < 0)
real.to_csv(OUT / "is_the_difference_real.csv", index=False)

# c) Break-even cost per contact. Policy: contact a customer only if their predicted uplift
#    (extra visits per contact) is above the contact cost expressed in visits, cost / value per visit.
#    The rule uses predictions only; outcomes come from the held-out randomised test.
v_none = ipw(test, pd.Series("No E-Mail", index=test.index), "visit")
inc_mens_all = (v_mens - v_none).sum() / len(test) * 1000         # extra visits per 1,000, blanket
rows = []
for r in np.round(np.arange(0.0, 0.2001, 0.005), 3):               # cost per contact, in visits
    send = test["best_uplift"].to_numpy() > r
    assigned = test["recommended_email"].where(send, "No E-Mail")
    v_pol = ipw(test, assigned, "visit")
    inc = (v_pol - v_none).sum() / len(test) * 1000
    contacts = send.mean() * 1000
    rows.append({"cost_per_contact_in_visits": r, "share_contacted": round(send.mean(), 3),
                 "net_visits_targeted": round(inc - r * contacts, 1),
                 "net_visits_send_all": round(inc_mens_all - r * 1000, 1)})
be = pd.DataFrame(rows)
be["targeting_advantage"] = (be.net_visits_targeted - be.net_visits_send_all).round(1)
be.to_csv(OUT / "breakeven_curve.csv", index=False)

# Revenue per extra visit, from the test itself (directional: spend is sparse)
rev_per_visit = (m.mean() - c.mean()) / (mv.mean() - cv.mean())
pd.DataFrame([{"revenue_per_extra_visit": round(rev_per_visit, 2)}]).to_csv(OUT / "value_per_visit.csv", index=False)

print("\n", model_vs_rule.to_string(index=False))
print(mens_vs_womens.to_string(index=False))
print(be.iloc[::2].to_string(index=False))
print("revenue per extra visit", round(rev_per_visit, 2), " blanket extra visits/1000", round(inc_mens_all, 1))
