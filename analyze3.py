# -*- coding: utf-8 -*-
"""
Re-analysis using Soniox-transcribed (and manual) SRTs from anki_work/.
Identical methodology to analyze2.py but reads cik_<vid>.srt files.
"""
import os, re, glob, csv, math, sys
from kiwipiepy import Kiwi

sys.stdout.reconfigure(encoding="utf-8")
SCRATCH = os.path.dirname(os.path.abspath(__file__))
DL      = os.environ.get("KNOWN_WORDS_DIR", os.path.expanduser("~/Downloads"))
KO      = os.environ.get("KO_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORK    = os.path.join(SCRATCH, "anki_work")

# ── frequency rank ────────────────────────────────────────────────────────────
rank = {}
with open(os.path.join(KO, "kofren", "ko-KoFREN-lemma-priority.csv"), encoding="utf-8") as f:
    next(f)
    for i, line in enumerate(f):
        w = line.strip()
        if w and w not in rank:
            rank[w] = i + 1
MAXRANK = len(rank) + 1

# ── known-word set ─────────────────────────────────────────────────────────────
def add_known(s, w):
    w = w.strip()
    if not w: return
    s.add(w)
    if w.endswith("다") and len(w) > 1:
        s.add(w[:-1])

KNOWN = set()
with open(os.path.join(DL, "known_words.csv"), encoding="utf-8-sig") as f:
    next(f, None)
    for line in f:
        add_known(KNOWN, line.split(",")[0])
km = sorted(glob.glob(os.path.join(DL, "known_morphs-*.csv")))
if km:
    with open(km[-1], encoding="utf-8-sig") as f:
        next(f, None)
        for line in f:
            add_known(KNOWN, line.split(",")[0])
ws = os.path.join(KO, "word-statuses-2026-05-22.csv")
if os.path.exists(ws):
    with open(ws, encoding="utf-8-sig") as f:
        for line in f:
            parts = line.split(",")
            if parts and parts[0].strip():
                add_known(KNOWN, parts[0])

CONTENT = lambda tag: (tag.startswith(("NNG","NNP","VV","VA","MAG","MAJ","MM","XR","IC","NR"))
                       and not tag.startswith("NNB"))

def is_known(tok):
    f, t = tok.form, tok.tag
    if not re.search(r"[가-힣]", f): return True
    if not CONTENT(t): return True
    if f in KNOWN: return True
    if (f + "다") in KNOWN: return True
    return False

# ── SRT parser ────────────────────────────────────────────────────────────────
def parse_srt(path):
    lines = []
    try:
        for ln in open(path, encoding="utf-8"):
            ln = ln.strip()
            if not ln or ln.isdigit() or "-->" in ln:
                continue
            ln = re.sub(r"<[^>]+>", "", ln)
            if ln:
                lines.append(ln)
    except Exception:
        return ""
    return " ".join(lines)

def clean(t):
    t = re.sub(r"\[[^\]]*\]", " ", t)
    t = re.sub(r"\([^)]*\)", " ", t)
    return re.sub(r"\s+", " ", t).strip()

# ── video meta ────────────────────────────────────────────────────────────────
meta = {}
with open(os.path.join(SCRATCH, "videos.tsv"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("\\t")
        if len(p) >= 3:
            try: d = float(p[1])
            except: d = None
            meta[p[0]] = {"dur": d, "title": "\\t".join(p[2:])}

# ── topic familiarity ─────────────────────────────────────────────────────────
def topic_fam(title):
    t = title.lower()
    if any(k in t for k in ["complete beginner","tprs","hangul","comprehensible input",
                             "candies","pepperoni","bigger","chased","flower","unolingo"]):
        return 1.00
    if any(k in t for k in ["stardew","unpacking","house flipper","hidden folks","goose",
                             "thief","milo","assemble"]):
        return 0.90
    if any(k in t for k in ["bathhouse","kidnap","convenience","closing shift","poppy",
                             "parasocial","shinkansen","fears to fathom","boba","cabin",
                             "platform 8","night security","devotion"]):
        return 0.45
    if any(k in t for k in ["cube escape","inside","white door","behind the frame","florence",
                             "when the past","insomnia","agent a","escape simulator","endling",
                             "stray","superliminal","portal","alba"]):
        return 0.65
    return 0.70

# ── per-video analysis ────────────────────────────────────────────────────────
kiwi  = Kiwi()
rows  = []
vtoks = {}   # cached token lists for adaptive path

for srt_path in sorted(glob.glob(os.path.join(WORK, "cik_*.srt"))):
    vid = os.path.basename(srt_path)[4:-4]   # strip "cik_" prefix and ".srt"
    if vid not in meta or not meta[vid]["dur"]: continue
    dur = meta[vid]["dur"]

    text = clean(parse_srt(srt_path))
    if not text: continue

    toks  = [t for t in kiwi.tokenize(text) if re.search(r"[가-힣]", t.form) or t.tag.startswith("S")]
    htoks = [t for t in toks if re.search(r"[가-힣]", t.form)]
    n     = len(htoks)
    if n < 30: continue

    latin  = len(re.findall(r"[A-Za-z]", text))
    hangul = len(re.findall(r"[가-힣]", text))
    latin_ratio = latin / max(hangul, 1)
    reliable = latin_ratio < 0.05 and n / (dur / 60.0) > 25

    known_flags = [is_known(t) for t in htoks]
    comp  = sum(known_flags) / n
    unk_idx   = [i for i, t in enumerate(htoks) if not known_flags[i]]
    unk_forms = [htoks[i].form for i in unk_idx]
    n_unk = len(unk_idx)
    uniq_unk  = {}
    for fm in unk_forms: uniq_unk[fm] = uniq_unk.get(fm, 0) + 1

    if uniq_unk:
        rarity = sum(math.log10(rank.get(fm, MAXRANK)) for fm in uniq_unk) / len(uniq_unk)
        reps   = sum(uniq_unk.values()) / len(uniq_unk)
    else:
        rarity = 0.0; reps = 0.0

    if len(unk_idx) >= 2:
        gaps = [unk_idx[i+1] - unk_idx[i] for i in range(len(unk_idx)-1)]
        mean_gap = sum(gaps) / len(gaps); longest_run = max(gaps) - 1
    else:
        mean_gap = float(n); longest_run = n

    new_types  = len(uniq_unk)
    new_per_min = new_types / (dur / 60.0)
    sents       = kiwi.split_into_sents(text)
    n_sents     = max(len(sents), 1)
    avg_sent_len = n / n_sents
    rate        = n / (dur / 60.0)
    fam         = topic_fam(meta[vid]["title"])

    rows.append(dict(vid=vid, title=meta[vid]["title"], dur=dur/60.0, n=n,
        comp=comp, n_unk=n_unk, new_types=new_types, new_per_min=new_per_min, reps=reps,
        rarity=rarity, mean_gap=mean_gap, longest_run=longest_run,
        avg_sent_len=avg_sent_len, rate=rate, fam=fam,
        latin_ratio=latin_ratio, reliable=reliable))
    vtoks[vid] = [(t.form, t.tag) for t in [x for x in kiwi.tokenize(text) if re.search(r"[가-힣]", x.form)]]

# ── normalize + score ─────────────────────────────────────────────────────────
def scale(x, lo, hi, invert=False):
    if hi == lo: return 0.5
    v = (x - lo) / (hi - lo)
    return 1 - v if invert else v

def col(key): return [r[key] for r in rows]

GAPCAP = 40.0
rar_lo,  rar_hi  = min(col("rarity")),       max(col("rarity"))
gap_lo,  gap_hi  = min(min(col("mean_gap")), 0.0), GAPCAP
sent_lo, sent_hi = min(col("avg_sent_len")), max(col("avg_sent_len"))
rate_lo, rate_hi = min(col("rate")),         max(col("rate"))

for r in rows:
    s_comp   = r["comp"]
    s_common = scale(r["rarity"],     rar_lo,  rar_hi,  invert=True)
    s_space  = scale(min(r["mean_gap"], GAPCAP), gap_lo, gap_hi)
    s_gram   = 0.5*scale(r["avg_sent_len"], sent_lo, sent_hi, invert=True) + \
               0.5*scale(r["rate"],         rate_lo, rate_hi, invert=True)
    s_topic  = r["fam"]
    r["s_comp"] = s_comp; r["s_common"] = s_common
    r["s_space"] = s_space; r["s_gram"] = s_gram; r["s_topic"] = s_topic
    r["secondary"] = 0.40*s_common + 0.30*s_space + 0.20*s_gram + 0.10*s_topic
    r["score"]     = 0.50*s_comp   + 0.20*s_common + 0.15*s_space + 0.10*s_gram + 0.05*s_topic

def band(c): return round(c * 50)
rows.sort(key=lambda r: (-band(r["comp"]), -r["secondary"]))

# Write difficulty CSV (cefr_grade.py reads from this)
with open(os.path.join(SCRATCH, "difficulty_v2.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["order","vid","title","dur_min","tokens","comprehension_%","new_word_types",
                "new_per_min","avg_reps_of_new","unknown_rarity_logrank","mean_gap_tokens",
                "avg_sent_len","tokens_per_min","topic_fam","reliable","score"])
    for i, r in enumerate(rows, 1):
        w.writerow([i, r["vid"], r["title"], f"{r['dur']:.1f}", r["n"], f"{r['comp']*100:.1f}",
            r["new_types"], f"{r['new_per_min']:.1f}", f"{r['reps']:.2f}", f"{r['rarity']:.2f}",
            f"{r['mean_gap']:.1f}", f"{r['avg_sent_len']:.1f}", f"{r['rate']:.0f}",
            f"{r['fam']:.2f}", "Y" if r["reliable"] else "LOW", f"{r['score']:.3f}"])

# ── adaptive greedy path ──────────────────────────────────────────────────────
cur_known = set(KNOWN)
remaining = {r["vid"]: r for r in rows}
path = []
recent = set()
while remaining:
    best = None; best_val = -1; best_info = None
    for vid, r in remaining.items():
        tt = vtoks.get(vid, [])
        n  = len(tt)
        if not n: continue
        kn = 0; unk_types = set(); reinforce = 0
        for form, tag in tt:
            known = (not CONTENT(tag)) or (form in cur_known) or ((form+"다") in cur_known)
            if known: kn += 1
            else: unk_types.add(form)
            if form in recent: reinforce += 1
        comp = kn / n; new = len(unk_types)
        sweet    = 1 - abs(0.90 - comp) / 0.90
        load_pen = min(new / 60.0, 1.0)
        val = 0.6*comp + 0.25*sweet + 0.10*(reinforce/n) - 0.15*load_pen
        if val > best_val:
            best_val = val; best = vid; best_info = (comp, new, unk_types)
    if best is None: break
    comp, new, unk_types = best_info
    path.append((best, remaining[best]["title"], comp, new))
    recent = set(list(unk_types)[:200])
    cur_known |= unk_types
    del remaining[best]

with open(os.path.join(SCRATCH, "adaptive_path.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["step","vid","title","comprehension_at_watch_%","new_words_introduced"])
    for i, (vid, title, comp, new) in enumerate(path, 1):
        w.writerow([i, vid, title, f"{comp*100:.1f}", new])

print(f"Known content-word set: {len(KNOWN)}")
print(f"Analyzed {len(rows)} videos")
print("Wrote difficulty_v2.csv and adaptive_path.csv")
