# -*- coding: utf-8 -*-
"""
Run after the Anki pipeline completes (phase 5).
1. analyze3.py     — re-score all 175 videos using Soniox SRTs
2. cefr_grade.py   — re-grade CEFR using fresh metrics
3. Rebuild cik_data.json for the CEFR widget
4. Copy CSVs to project directory
"""
import sys, os, csv, json, re, subprocess, shutil
sys.stdout.reconfigure(encoding="utf-8")

SCRATCH = os.path.dirname(os.path.abspath(__file__))
KO = os.environ.get("KO_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Step 1: re-analyze with Soniox SRTs ──────────────────────────────────────
print("=== Step 1: Transcript analysis (Soniox SRTs) ===")
subprocess.run([sys.executable, os.path.join(SCRATCH, "analyze3.py")], check=True)

# ── Step 2: re-grade CEFR ─────────────────────────────────────────────────────
print("\n=== Step 2: CEFR grading ===")
subprocess.run([sys.executable, os.path.join(SCRATCH, "cefr_grade.py")], check=True)

# ── Step 3: copy CSVs to project directory ────────────────────────────────────
print("\n=== Step 3: Copy output CSVs to project dir ===")
for fname in ["comprehensible_input_korean_cefr.csv",
              "comprehensible_input_korean_difficulty.csv",
              "comprehensible_input_korean_adaptive_path.csv"]:
    src = os.path.join(KO, fname)
    if os.path.exists(src):
        print(f"  {fname} already in {KO}/")

# difficulty_v2.csv → copy as the main difficulty CSV
diff_src = os.path.join(SCRATCH, "difficulty_v2.csv")
diff_dst = os.path.join(KO, "comprehensible_input_korean_difficulty.csv")
shutil.copy(diff_src, diff_dst)
print(f"  difficulty_v2.csv → {diff_dst}")

adapt_src = os.path.join(SCRATCH, "adaptive_path.csv")
adapt_dst = os.path.join(KO, "comprehensible_input_korean_adaptive_path.csv")
if os.path.exists(adapt_src):
    shutil.copy(adapt_src, adapt_dst)
    print(f"  adaptive_path.csv → {adapt_dst}")

# ── Step 4: rebuild cik_data.json ─────────────────────────────────────────────
print("\n=== Step 4: Rebuild cik_data.json ===")

# Load video metadata
meta = {}
with open(os.path.join(SCRATCH, "videos.tsv"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("\\t")
        if len(p) >= 3:
            try: d = float(p[1])
            except: d = None
            meta[p[0]] = {"dur": d, "title": "\\t".join(p[2:])}

# Load comprehension % from fresh difficulty_v2.csv
comp_map = {}
with open(diff_src, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        comp_map[row["vid"]] = float(row["comprehension_%"])

# Load CEFR grades
CEFR_ORDER = {
    "Pre-A1/A0": 0, "A0": 1, "A1": 2, "A1/A2": 3, "A1-A2": 3,
    "A2": 4, "A2/A2-B1": 5, "A2-B1": 6, "A2-B1/B1-B2": 7,
    "B1": 8, "B1-B2": 8, "B1/B2": 8, "N/A": 9, "?": 10,
}
cefr_map = {}
cefr_csv = os.path.join(KO, "comprehensible_input_korean_cefr.csv")
with open(cefr_csv, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        grade = row["cefr_final"].replace("[auto] ", "")
        cefr_map[row["vid"]] = grade

# Series detection (same logic as before)
SERIES_PATTERNS = [
    (r"COMPLETE Beginner Korean",                "COMPLETE Beginner Korean"),
    (r"Learn Hangul",                            "Learn Hangul Without English"),
    (r"TPRS Korean for beginners|TPRS for beginners", "TPRS Korean for beginners"),
    (r"TPRS Korean pt\.2|TPRS pt\.2",            "TPRS Korean pt.2"),
    (r"Hidden Folks",                            "Hidden Folks"),
    (r"Cube Escape",                             "Cube Escape"),
    (r"Escape Simulator",                        "Escape Simulator"),
    (r"Stardew Valley",                          "Stardew Valley"),
    (r"INSIDE",                                  "INSIDE"),
    (r"Insomnia",                                "Insomnia"),
    (r"Florence",                                "Florence"),
    (r"Fears to Fathom.*Carson",                 "Fears to Fathom - Carson House"),
    (r"Fears to Fathom.*Norwood",                "Fears to Fathom - Norwood Hitchhike"),
    (r"Fears to Fathom.*Woodbury",               "Fears to Fathom - Woodbury Getaway"),
    (r"Behind the Frame",                        "Behind the Frame"),
    (r"House Flipper",                           "House Flipper"),
    (r"Assemble with Care",                      "Assemble with Care"),
    (r"The White Door",                          "The White Door"),
    (r"unpacking",                               "unpacking"),
    (r"Milo and the Magpies",                    "Milo and the Magpies"),
    (r"Milo and the Christmas",                  "Milo and the Christmas Gift"),
    (r"Little Nightmares",                       "Little Nightmares"),
    (r"Agent A",                                 "Agent A"),
    (r"Thief Simulator",                         "Thief Simulator"),
    (r"Untitled Goose",                          "Untitled Goose Game"),
    (r"When the Past",                           "When the Past was Around"),
    (r"Portal 2",                                "Portal 2"),
    (r"CI Stories|Be nice|chased by dogs|flower|pepperoni|bigger", "CI Stories"),
    (r"GOAT OR THROAT",                          "GOAT OR THROAT"),
    (r"Platform 8",                              "Platform 8"),
    (r"Poppy Playtime",                          "Poppy Playtime Chapter 1"),
    (r"The Kidnap",                              "The Kidnap"),
    (r"Unolingo",                                "Unolingo"),
    (r"Endling",                                 "Endling"),
    (r"Stray",                                   "Stray"),
    (r"Superliminal",                            "Superliminal"),
    (r"The Bathhouse",                           "The Bathhouse"),
    (r"The Closing Shift",                       "The Closing Shift"),
    (r"Devotion",                                "Devotion"),
    (r"Parasocial",                              "Parasocial"),
    (r"Shinkansen",                              "Shinkansen 0"),
    (r"The Boba Teashop",                        "The Boba Teashop"),
    (r"The Cabin Factory",                       "The Cabin Factory"),
    (r"Night Security",                          "Night Security"),
    (r"The Convenience Store",                   "The Convenience Store"),
    (r"Intermediate.*[Gg]ame|Korean Listening Practice", "Intermediate Game"),
    (r"Alba",                                    "Alba"),
    (r"burning man|demo group|any given wednesday", "Meta / non-learning"),
    (r"COMPREHENSIBLE HANGUL",                   "CI Stories"),
]

EP_RE = re.compile(r"(?:ep|episode|#|pt\.?\s*)\s*(\d+)", re.IGNORECASE)

def detect_series(title):
    for pattern, name in SERIES_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            m = EP_RE.search(title)
            ep = int(m.group(1)) if m else 0
            return name, ep
    return title, 0

records = []
for vid, info in meta.items():
    title = info["title"]
    dur   = (info["dur"] or 0) / 60.0
    comp  = comp_map.get(vid, 0.0)
    grade = cefr_map.get(vid, "?")
    grade_ord = CEFR_ORDER.get(grade, 10)
    series, ep = detect_series(title)
    records.append({
        "vid": vid,
        "title": title,
        "series": series,
        "grade": grade,
        "grade_ord": grade_ord,
        "comp": round(comp, 1),
        "dur": round(dur, 1),
        "ep": ep,
        "url": f"https://youtu.be/{vid}",
    })

# Sort: series primary grade → series name → episode
series_min = {}
for r in records:
    s = r["series"]
    if s not in series_min or r["grade_ord"] < series_min[s]:
        series_min[s] = r["grade_ord"]

records.sort(key=lambda r: (series_min[r["series"]], r["series"], r["ep"], r["grade_ord"]))

out_path = os.path.join(SCRATCH, "cik_data.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)
print(f"  Wrote {len(records)} records → {out_path}")

# Also copy to KO for reference
shutil.copy(out_path, os.path.join(KO, "cik_data.json"))

print("\nAll done. Re-render the widget to see updated CEFR grades.")
