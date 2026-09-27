# -*- coding: utf-8 -*-
"""
Full Anki deck pipeline for Comprehensible Input Korean channel.

Phases:
  1. Download audio (m4a) for all 175 videos
  2. Download manual Korean SRTs for the 44 videos that have them
  3. Transcribe remaining 131 via Soniox + generate SRT from JSON
  4. Run subs2cia on all audio+SRT pairs → out_srs/
  5. Combine TSVs → ci_korean.apkg

Usage:
  python pipeline.py [--phase N]   (default: run all phases)
"""

import os, sys, re, glob, json, csv, shutil, subprocess, time, threading
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────
S       = Path(__file__).parent
KO      = Path(os.environ.get("KO_DIR", Path(__file__).resolve().parent.parent))
SCRIPTS = KO / "dojo-prompts" / "scripts"
WORK    = S / "anki_work"          # audio + SRTs live here (flat)
JSON_D  = S / "json_transcripts"   # Soniox JSON
OUT_SRS = WORK / "out_srs"
APKG_OUT = KO / "ci_korean.apkg"
WORK.mkdir(exist_ok=True)
JSON_D.mkdir(exist_ok=True)

SONIOX_KEY = os.environ.get("SONIOX_API_KEY", "")
if not SONIOX_KEY:
    _env = S / ".env"
    if _env.exists():
        for _line in _env.read_text().splitlines():
            if _line.startswith("SONIOX_API_KEY="):
                SONIOX_KEY = _line.split("=", 1)[1].strip()
                break
SEP = "\\t"   # literal backslash-t in videos.tsv

# ── video metadata ──────────────────────────────────────────────────────────
def load_videos():
    rows = {}
    for line in open(S / "videos.tsv", encoding="utf-8"):
        p = line.rstrip().split(SEP)
        if len(p) >= 3:
            rows[p[0]] = p[2]
    return rows  # {vid: title}

# ── manual-sub IDs (44 videos) ──────────────────────────────────────────────
MANUAL_TITLES = [
    "COMPLETE Beginner Korean #6 [Lv.A0]",
    "TPRS Korean for beginners ep10 (pt.2 ep0)",
    "TPRS Korean for beginners ep1",
    "COMPLETE Beginner Korean #14 [Lv.A0]",
    "TPRS Korean for beginners ep3",
    "TPRS Korean for beginners ep9",
    "TPRS Korean for beginners ep6",
    "TPRS Korean pt.2 ep3",
    "TPRS Korean for beginners ep5",
    "TPRS Korean pt.2 ep1",
    "TPRS Korean for beginners ep7",
    "COMPLETE Beginner Korean #2 [Lv.A0]",
    "TPRS Korean for beginners ep2",
    "COMPLETE Beginner Korean #15 [Lv.A0]",
    "COMPLETE Beginner Korean #11 [Lv.A0]",
    "TPRS Korean for beginners ep8",
    "TPRS Korean for beginners ep4",
    "COMPLETE Beginner Korean #3 [Lv.A0]",
    "COMPLETE Beginner Korean #16  [Lv.A0]",
    "TPRS Korean pt.2 ep2",
    "COMPLETE Beginner Korean #1 [Lv.A0]",
    "COMPLETE Beginner Korean #9 [Lv.A0]",
    "COMPLETE Beginner Korean #4 [Lv.A0]",
    "COMPLETE Beginner Korean #10 [Lv.A0]",
    "COMPLETE Beginner Korean #12 [Lv.A0]",
    "COMPLETE Beginner Korean #8 [Lv.A0]",
    "[Lv.A1-2] Learn Korean with games - [Thief Simulator] ep2",
    "COMPLETE Beginner Korean #17 [Lv.A0]",
    "[Lv.A1-2] Learn Korean with games - [Thief Simulator] ep1",
    "Learn Korean with games - [Milo and the Magpies] ep2",
    "Learn Korean with games - [The White Door] ep7",
    "Learn Korean with games - [The White Door] ep4",
    "COMPLETE Beginner Korean #5 [Lv.A0]",
    "Learn Korean with games - [The White Door] ep6",
    "Learn Korean with games - [Milo and the Magpies] ep1",
    "Learn Korean with games - [unpacking] ep4",
    "Learn Korean with games - [The White Door] ep1",
    "Learn Korean with games - [unpacking] ep3",
    "Learn Korean with games - [The White Door] ep3",
    "COMPLETE Beginner Korean #7 [Lv.A0]",
    "Learn Korean with games - [The White Door] ep5",
    "COMPLETE Beginner Korean #13 [Lv.A0]",
    "Learn Korean with games - [unpacking] ep1",
    "Learn Korean with games - [The White Door] ep2",
    "Learn Korean with games - [unpacking] ep2",
]

def get_manual_ids(videos):
    manual = set()
    for title in MANUAL_TITLES:
        for vid, t in videos.items():
            if t.strip() == title.strip():
                manual.add(vid)
    return manual

# ── naming ──────────────────────────────────────────────────────────────────
def stem(vid): return f"cik_{vid}"

# ── Phase 1: download audio ──────────────────────────────────────────────────
def phase1_download_audio(videos):
    print("\n=== Phase 1: Download audio for all 175 videos ===")
    missing = [vid for vid in videos if not list(WORK.glob(f"cik_{vid}.*a"))]
    if not missing:
        print("  All audio already downloaded.")
        return
    print(f"  Downloading {len(missing)} audio files...")
    urls = [f"https://www.youtube.com/watch?v={v}" for v in missing]
    url_file = S / "_dl_urls.txt"
    url_file.write_text("\n".join(urls), encoding="utf-8")
    subprocess.run([
        "yt-dlp", "-f", "ba[ext=m4a]/ba",
        "--no-playlist", "--sleep-requests", "0.3",
        "-o", str(WORK / "cik_%(id)s.%(ext)s"),
        "-a", str(url_file),
    ], check=True)
    print(f"  Done. Audio files in {WORK}/")

# ── Phase 2: download manual Korean SRTs ────────────────────────────────────
def phase2_manual_subs(videos, manual_ids):
    print("\n=== Phase 2: Download manual Korean SRTs ===")
    for vid in sorted(manual_ids):
        srt_out = WORK / f"cik_{vid}.srt"
        if srt_out.exists():
            continue
        print(f"  {vid} — {videos[vid][:60]}")
        url = f"https://www.youtube.com/watch?v={vid}"
        tmp_stem = WORK / f"_manual_{vid}"
        result = subprocess.run([
            "yt-dlp", "--skip-download",
            "--write-subs", "--no-write-auto-subs",
            "--sub-langs", "ko",
            "--sub-format", "srt/vtt",
            "-o", str(tmp_stem) + ".%(ext)s",
            url,
        ], capture_output=True, text=True)
        # find downloaded file (could be .ko.srt or .ko.vtt)
        found = list(WORK.glob(f"_manual_{vid}*"))
        if not found:
            print(f"    WARNING: no manual sub found for {vid}, will transcribe instead")
            manual_ids.discard(vid)
            continue
        src = found[0]
        if src.suffix == ".vtt":
            # convert vtt → srt
            _vtt_to_srt(src, srt_out)
            src.unlink()
        else:
            src.rename(srt_out)
        print(f"    → {srt_out.name}")
    print("  Done.")

def _vtt_to_srt(vtt_path, srt_path):
    import html as htmlmod
    lines = vtt_path.read_text(encoding="utf-8").splitlines()
    out = []; i = 0; idx = 1
    while i < len(lines):
        ln = lines[i].strip()
        if "-->" in ln:
            ts = ln.replace(".", ",").split()
            start, end = ts[0], ts[2]
            text_lines = []
            i += 1
            while i < len(lines) and lines[i].strip():
                t = re.sub(r"<[^>]+>", "", lines[i].strip())
                t = htmlmod.unescape(t)
                if t: text_lines.append(t)
                i += 1
            if text_lines:
                out.append(f"{idx}\n{start} --> {end}\n" + "\n".join(text_lines) + "\n")
                idx += 1
        i += 1
    srt_path.write_text("\n".join(out), encoding="utf-8")

# ── Phase 3: Soniox transcription for videos without manual subs ─────────────
def phase3_transcribe(videos, manual_ids, workers=6):
    print("\n=== Phase 3: Soniox transcription for remaining videos ===")
    if not SONIOX_KEY:
        print("  ERROR: SONIOX_API_KEY not set"); return

    to_transcribe = []
    for vid in videos:
        if vid in manual_ids: continue
        srt_out = WORK / f"cik_{vid}.srt"
        if srt_out.exists(): continue
        json_out = WORK / f"cik_{vid}.json"  # transcribe_soniox writes to audio file's dir
        audio = list(WORK.glob(f"cik_{vid}.*a"))
        if not audio:
            print(f"  SKIP {vid}: no audio file")
            continue
        to_transcribe.append((vid, audio[0], json_out, srt_out))

    if not to_transcribe:
        print("  All already transcribed.")
        return
    print(f"  Transcribing {len(to_transcribe)} videos with {workers} workers...")

    lock = threading.Lock()
    done = [0]

    def transcribe_one(args):
        vid, audio_path, json_out, srt_out = args
        try:
            # transcribe → JSON (writes to audio_path.parent / stem.json = WORK)
            if not json_out.exists():
                subprocess.run([
                    sys.executable,
                    str(SCRIPTS / "transcribe_soniox.py"),
                    str(audio_path),
                ], check=True,
                   env={**os.environ, "SONIOX_API_KEY": SONIOX_KEY})
            # JSON → SRT (writes to json_out.parent / stem.srt = WORK)
            if not srt_out.exists() and json_out.exists():
                subprocess.run([
                    sys.executable,
                    str(SCRIPTS / "srt_watch.py"),
                    str(json_out),
                ], check=True, cwd=str(SCRIPTS),
                   env={**os.environ, "PYTHONUTF8": "1"})
            with lock:
                done[0] += 1
                print(f"  [{done[0]}/{len(to_transcribe)}] done: {vid}")
            return vid, True
        except Exception as e:
            with lock:
                print(f"  ERROR {vid}: {e}", file=sys.stderr)
            return vid, False

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(transcribe_one, a) for a in to_transcribe]
        for f in as_completed(futures):
            pass  # progress printed inside transcribe_one
    print("  Phase 3 done.")

# ── Phase 4: subs2cia (resumable — one video at a time) ─────────────────────
def phase4_subs2cia():
    print("\n=== Phase 4: subs2cia ===")
    OUT_SRS.mkdir(exist_ok=True)

    pairs = []
    for audio in sorted(WORK.glob("cik_*.m4a")):
        srt = WORK / (audio.stem + ".srt")
        if srt.exists():
            pairs.append((audio, srt))
        else:
            print(f"  MISSING SRT: {audio.name}")
    print(f"  {len(pairs)} audio+SRT pairs found")

    done = skipped = failed = 0
    for audio, srt in pairs:
        tsv_out = OUT_SRS / f"{audio.stem}.tsv"
        if tsv_out.exists():
            skipped += 1
            continue
        result = subprocess.run(
            f"subs2cia srs -i \"{audio.name}\" \"{srt.name}\""
            f" -p 500 -N --no-export-screenshot"
            f" -d \"{OUT_SRS}\" --export-header-row",
            shell=True, cwd=str(WORK),
            capture_output=True, text=True)
        if tsv_out.exists():
            done += 1
            if done % 10 == 0:
                print(f"  [{done+skipped}/{len(pairs)}] done so far…")
        else:
            print(f"  WARN: no TSV for {audio.stem} (rc={result.returncode})")
            failed += 1

    print(f"  subs2cia: {done} processed, {skipped} skipped, {failed} failed → {OUT_SRS}/")

# ── Phase 5: combine + apkg ──────────────────────────────────────────────────
def phase5_export():
    print("\n=== Phase 5: Combine TSVs + export .apkg ===")
    tsvs = sorted(OUT_SRS.glob("*.tsv"))
    if not tsvs:
        print("  No TSVs found."); return

    combined = OUT_SRS / "combined.tsv"
    with open(combined, "w", encoding="utf-8", newline="") as fout:
        header_written = False
        for tsv in tsvs:
            with open(tsv, encoding="utf-8") as fin:
                lines = fin.readlines()
            if not lines: continue
            if not header_written:
                fout.write(lines[0])
                header_written = True
            fout.writelines(lines[1:])
    print(f"  Combined {len(tsvs)} TSVs → {combined}")

    subprocess.run([
        sys.executable,
        str(SCRIPTS / "apkg_export.py"),
        str(combined),
        str(OUT_SRS),
        "ci_korean",
        str(KO),
    ], check=True)

    # cleanup
    shutil.rmtree(str(OUT_SRS))
    print(f"\n  ✓ Deck exported → {APKG_OUT}")

# ── main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", type=int, default=0, help="Run only phase N (0=all)")
    ap.add_argument("--workers", type=int, default=6, help="Soniox parallel workers")
    args = ap.parse_args()

    videos = load_videos()
    manual_ids = get_manual_ids(videos)
    print(f"Videos: {len(videos)} total | {len(manual_ids)} with manual subs | "
          f"{len(videos)-len(manual_ids)} need Soniox")

    run = lambda n: args.phase == 0 or args.phase == n
    if run(1): phase1_download_audio(videos)
    if run(2): phase2_manual_subs(videos, manual_ids)
    if run(3): phase3_transcribe(videos, manual_ids, workers=args.workers)
    if run(4): phase4_subs2cia()
    if run(5): phase5_export()
