# -*- coding: utf-8 -*-
"""
Convert downloaded auto-captions (srv1 XML or vtt) to clean Korean-only SRT files.
One SRT per video → goes into anki_work/<vid>/<vid>.srt alongside the audio.
"""
import os, re, glob, html, sys
import xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding="utf-8")

S = os.path.dirname(os.path.abspath(__file__))
SUBS = os.path.join(S, "subs")
OUT = os.path.join(S, "srts")
os.makedirs(OUT, exist_ok=True)

def ts(sec):
    sec = float(sec)
    h = int(sec // 3600); m = int((sec % 3600) // 60); s = sec % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")

def parse_srv1(path):
    """Returns list of (start_sec, end_sec, text)."""
    try:
        root = ET.fromstring(open(path, encoding="utf-8").read())
    except ET.ParseError:
        return []
    segs = []
    for t in root.findall("text"):
        if not t.text: continue
        raw = html.unescape(t.text).strip()
        raw = re.sub(r"\[[^\]]*\]", "", raw).strip()   # remove [음악] etc.
        if not raw: continue
        start = float(t.get("start", 0))
        dur = float(t.get("dur", 2))
        segs.append((start, start + dur, raw))
    return segs

def parse_vtt(path):
    segs = []; prev_text = None
    start = end = None
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if "-->" in line:
            parts = line.split("-->")
            def vtt_ts(s):
                s = s.strip().split()[0]
                p = s.split(":")
                if len(p) == 3: h, m, sec = p
                else: h = "0"; m, sec = p
                return float(h) * 3600 + float(m) * 60 + float(sec.replace(",", "."))
            start = vtt_ts(parts[0]); end = vtt_ts(parts[1])
        elif line and start is not None and not line.isdigit() and "WEBVTT" not in line:
            raw = re.sub(r"<[^>]+>", "", line)
            raw = re.sub(r"\[[^\]]*\]", "", raw).strip()
            if raw and raw != prev_text:
                segs.append((start, end, raw))
                prev_text = raw
                start = end = None
    return segs

def merge_short(segs, max_gap=0.5, max_len=60, max_dur=5.0):
    """Merge consecutive short segments into subtitle blocks."""
    if not segs: return []
    merged = [list(segs[0])]
    for (s, e, t) in segs[1:]:
        last = merged[-1]
        gap = s - last[1]
        combined = last[2] + " " + t
        if gap < max_gap and len(combined) < max_len and (e - last[0]) < max_dur:
            last[1] = e; last[2] = combined
        else:
            merged.append([s, e, t])
    return merged

# Process all available caption files
files = {}
for p in glob.glob(os.path.join(SUBS, "*")):
    vid = os.path.basename(p).split(".")[0]
    files.setdefault(vid, {})
    if p.endswith(".srv1"): files[vid]["srv1"] = p
    elif p.endswith(".vtt"): files[vid]["vtt"] = p

written = 0
for vid, fs in files.items():
    segs = parse_srv1(fs["srv1"]) if "srv1" in fs else parse_vtt(fs.get("vtt", ""))
    if not segs: continue
    segs = merge_short(segs)
    out_path = os.path.join(OUT, f"{vid}.srt")
    with open(out_path, "w", encoding="utf-8") as f:
        for i, (s, e, t) in enumerate(segs, 1):
            f.write(f"{i}\n{ts(s)} --> {ts(e)}\n{t}\n\n")
    written += 1

print(f"wrote {written} SRT files to {OUT}/")
