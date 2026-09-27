# -*- coding: utf-8 -*-
import csv, sys, os
sys.stdout.reconfigure(encoding="utf-8")
S=os.path.dirname(os.path.abspath(__file__))
KO=os.environ.get("KO_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

diff=list(csv.DictReader(open(os.path.join(S,"difficulty_v2.csv"),encoding="utf-8-sig")))
path=list(csv.DictReader(open(os.path.join(S,"adaptive_path.csv"),encoding="utf-8-sig")))

def yt(v): return f"https://youtu.be/{v}"

out=[]
out.append("# Comprehensible Input Korean — Transcript-Based Difficulty Ranking\n")
out.append("Channel: https://www.youtube.com/@ComprehensibleInputKorean\n")
out.append("Ranked by analyzing the **actual Korean auto-caption transcript of all 175 videos** "
"against **your own known-word list** (Kimchi Reader + AnkiMorphs, ~3,480 content lemmas; "
"grammatical morphemes auto-credited).\n")

out.append("## Method (comprehension-first, per your spec)\n")
out.append("Primary axis = **predicted comprehension** = % of word tokens you already know "
"(token-weighted, so a new word repeated 80× counts 80×). Videos are bucketed into 2-point "
"comprehension bands; **within** a band they're ordered by a secondary score:\n")
out.append("- `0.40` commonness of unknown words (KoFREN frequency rank — a rank-#300 unknown is cheap, rank-#15k is expensive)\n"
"- `0.30` spacing of unknown words (mean token-gap between unknowns; capped so sparse-speech videos don't game it)\n"
"- `0.20` grammar/speech simplicity (avg sentence length + speech speed proxy)\n"
"- `0.10` topic familiarity (daily-life > sim games > puzzle/story > horror)\n")

out.append("## Key findings\n")
out.append("- **Your comprehension is high across the whole channel** (80–99%, median ~89%). Almost "
"everything here is comprehensible input for you — nothing is below the ~75% floor.\n")
out.append("- **The \"beginner\" label no longer predicts ease for you.** The easiest videos are the ones "
"that recycle words you know; the *hardest* are vocab-drill lessons and object-naming games "
"(Hidden Folks, unpacking, House Flipper, and the rooms-of-the-house lesson COMPLETE Beginner #7, "
"which repeats 침실/욕실/주방 dozens of times — all new for you).\n")
out.append("- **6 of the oldest videos have garbage auto-captions** (English/romanization noise); their "
"scores are flagged `LOW` and should be trusted less.\n")

# reliability list
low=[r for r in diff if r["reliable"]=="LOW"]
out.append("\n**Low-confidence transcripts (ASR noise):** "+", ".join(r["title"] for r in low)+"\n")

out.append("\n---\n")
out.append("## A. Full difficulty ranking — easiest → hardest (comprehension-led)\n")
out.append("`comp` = predicted comprehension. `new` = distinct new words. `reps` = avg times each new "
"word repeats (higher = easier to acquire). `rare` = unknown-word rarity (log10 freq-rank; higher = rarer). "
"`gap` = avg tokens between unknowns (higher = easier).\n")
out.append("| # | Video | comp% | new | reps | rare | gap | min | conf |")
out.append("|---|---|---|---|---|---|---|---|---|")
for r in diff:
    out.append(f"| {r['order']} | [{r['title']}]({yt(r['vid'])}) | {r['comprehension_%']} | "
               f"{r['new_word_types']} | {r['avg_reps_of_new']} | {r['unknown_rarity_logrank']} | "
               f"{r['mean_gap_tokens']} | {r['dur_min']} | {r['reliable']} |")

out.append("\n---\n")
out.append("## B. Adaptive watch path (recommended) — maximizes learning efficiency\n")
out.append("This re-computes comprehension **as your vocabulary grows**. At each step it picks the next "
"video that stays in the 85–95% sweet spot, reinforces words you just met, and keeps new-word load "
"manageable. `comp@watch` = your predicted comprehension at the point you'd watch it (after everything "
"above it).\n")
out.append("| step | Video | comp@watch% | +new words |")
out.append("|---|---|---|---|")
for r in path:
    out.append(f"| {r['step']} | [{r['title']}]({yt(r['vid'])}) | {r['comprehension_at_watch_%']} | {r['new_words_introduced']} |")

out.append("\n---\n")
out.append("### Notes\n")
out.append("- Transcript-only analysis can't see **visuals or speech speed/clarity**. Heavily visual games "
"(Hidden Folks, INSIDE) are easier to *follow* in practice than their word-level score suggests; fast "
"talkers are harder than their comprehension % suggests.\n")
out.append("- Re-run anytime your Kimchi Reader known-word list grows — the ranking will shift toward "
"whatever is now in your sweet spot.\n")

open(os.path.join(KO,"comprehensible_input_korean_difficulty.md"),"w",encoding="utf-8").write("\n".join(out))
# copy data files into project
import shutil
shutil.copy(os.path.join(S,"difficulty_v2.csv"),os.path.join(KO,"comprehensible_input_korean_difficulty.csv"))
shutil.copy(os.path.join(S,"adaptive_path.csv"),os.path.join(KO,"comprehensible_input_korean_adaptive_path.csv"))
print("wrote report + 2 CSVs to project")
