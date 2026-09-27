# -*- coding: utf-8 -*-
"""
CEFR grader for Comprehensible Input Korean videos.
Calibrates against the channel's own labeled videos, then grades unlabeled ones.
Uses metrics already computed in difficulty_v2.csv.
"""
import csv, re, sys, os
sys.stdout.reconfigure(encoding="utf-8")
S = os.path.dirname(os.path.abspath(__file__))
KO = os.environ.get("KO_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

rows = list(csv.DictReader(open(os.path.join(S, "difficulty_v2.csv"), encoding="utf-8-sig")))

# ---- extract CEFR label from title (channel's own tagging) ----
LABEL_RE = re.compile(r'\[(?:Lv\.)?([ABC][012](?:-[AB][012])?|For Beginners|For Intermediate)\]|'
                      r'For Beginners\s*/\s*(A\d)|For Intermediate\s*/\s*(B\d)', re.IGNORECASE)

def extract_label(title):
    m = LABEL_RE.search(title)
    if not m: return None
    g = next((x for x in m.groups() if x), "")
    g = g.strip()
    if re.match(r'^A0$', g, re.I): return "A0"
    if re.match(r'^A1', g, re.I): return "A1"
    if re.match(r'^A2-B1|A2-B2', g, re.I): return "A2-B1"
    if re.match(r'^A2', g, re.I): return "A2"
    if re.match(r'^B1-[B2]|B1-B2', g, re.I): return "B1-B2"
    if re.match(r'^B1', g, re.I): return "B1"
    if re.match(r'For Beginners', g, re.I): return "A2"
    if re.match(r'For Intermediate', g, re.I): return "B1"
    if re.match(r'^A1-2|A1-A2', g, re.I): return "A1-A2"
    return None

for r in rows:
    r["label"] = extract_label(r["title"])

# ---- calibration: collect per-label medians ----
from statistics import median
def meds(label_set):
    subset = [r for r in rows if r["label"] in label_set]
    if not subset: return None
    return {
        "rate": median(float(r["tokens_per_min"]) for r in subset),
        "sent": median(float(r["avg_sent_len"]) for r in subset),
        "rare": median(float(r["unknown_rarity_logrank"]) for r in subset),
        "new_pm": median(float(r["new_per_min"]) for r in subset),
    }

CAL = {k: meds(v) for k, v in {
    "A0":    {"A0"},
    "A1":    {"A1", "A1-A2"},
    "A2":    {"A2"},
    "A2-B1": {"A2-B1"},
    "B1-B2": {"B1-B2", "B1"},
}.items()}
print("=== Calibration medians ===")
for k, v in CAL.items():
    if v: print(f"  {k:6s}  rate={v['rate']:.0f}  sent={v['sent']:.1f}  rare={v['rare']:.2f}  new/min={v['new_pm']:.1f}")

# ---- grade unlabeled videos ----
# Thresholds derived from calibration; the dominant signal is tokens/min + sent_len.
# Rare vocabulary distinguishes A2 from A2-B1; new-word density separates B1+ from A2.
def assign_cefr(rate, sent, rare, new_pm, title):
    # Title-based overrides for things with no linguistic signal
    t = title.lower()
    if "hangul" in t or "comprehensible hangul" in t:
        return "Pre-A1/A0"
    if any(k in t for k in ["be nice", "bigger", "chased by dogs", "flower", "pepperoni", "candie"]):
        return "A0"
    if any(k in t for k in ["burning man", "demo group", "any given wednesday"]):
        return "N/A"   # meta/non-learning content

    # Score: rate and sent_len each cast a vote for a CEFR level; rare+new_pm act as modifiers
    def score(val, thresholds):
        # thresholds = [(upper_bound, label), ..., (inf, label)]
        for upper, lbl in thresholds:
            if val <= upper: return lbl
        return thresholds[-1][1]

    rate_vote = score(rate, [(58, "A0"), (78, "A1"), (100, "A2"), (125, "A2-B1"), (float("inf"), "B1-B2")])
    sent_vote = score(sent, [(5.5, "A0"), (7.5, "A1"), (10.0, "A2"), (12.5, "A2-B1"), (float("inf"), "B1-B2")])

    ORDER = ["A0", "A1", "A2", "A2-B1", "B1-B2"]
    avg_idx = (ORDER.index(rate_vote) + ORDER.index(sent_vote)) / 2

    # Modifier: high rare vocab pushes harder; lots of new words/min also harder
    rare_push = max(0, rare - 4.0) * 0.8   # each 0.1 logrank above 4.0 → +0.08 levels
    new_push  = max(0, new_pm - 4.0) * 0.05
    idx = min(avg_idx + rare_push + new_push, 4.0)

    # Map to CEFR string
    labels = ["A0", "A1", "A2", "A2-B1", "B1-B2"]
    lo, hi = int(idx), min(int(idx) + 1, 4)
    frac = idx - int(idx)
    if frac < 0.25: return labels[lo]
    if frac > 0.75: return labels[hi]
    # borderline → show both
    if lo != hi: return f"{labels[lo]}/{labels[hi]}"
    return labels[lo]

unlabeled = [r for r in rows if r["label"] is None]
print(f"\n=== Grading {len(unlabeled)} unlabeled videos ===\n")
results = []
for r in unlabeled:
    grade = assign_cefr(
        float(r["tokens_per_min"]), float(r["avg_sent_len"]),
        float(r["unknown_rarity_logrank"]), float(r["new_per_min"]),
        r["title"]
    )
    results.append((grade, r["vid"], r["title"], r["tokens_per_min"],
                    r["avg_sent_len"], r["unknown_rarity_logrank"], r["new_per_min"]))

# Group and print
from collections import defaultdict
by_grade = defaultdict(list)
for grade, vid, title, rate, sent, rare, new_pm in results:
    by_grade[grade].append((title, rate, sent))

for grade in ["Pre-A1/A0", "A0", "A1", "A2", "A2/A2-B1", "A2-B1", "A2-B1/B1-B2", "B1-B2", "N/A"]:
    if grade in by_grade:
        print(f"\n--- {grade} ---")
        for title, rate, sent in by_grade[grade]:
            print(f"  {title[:70]:70s}  rate={rate:>4}  sent={sent}")

# Write CSV
out = []
for r in rows:
    label = r["label"]
    if label is None:
        g = next((x[0] for x in results if x[1] == r["vid"]), "?")
        label = f"[auto] {g}"
    out.append({**r, "cefr_final": label})

with open(os.path.join(KO, "comprehensible_input_korean_cefr.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["vid", "title", "cefr_final", "dur_min", "tokens_per_min",
                "avg_sent_len", "unknown_rarity_logrank", "new_per_min", "comprehension_%"])
    for r in out:
        w.writerow([r["vid"], r["title"], r["cefr_final"], r["dur_min"],
                    r["tokens_per_min"], r["avg_sent_len"], r["unknown_rarity_logrank"],
                    r["new_per_min"], r["comprehension_%"]])

print("\nwrote comprehensible_input_korean_cefr.csv")
