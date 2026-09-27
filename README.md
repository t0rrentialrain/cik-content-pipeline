# Comprehensible-Input Korean Content Pipeline

A resumable, multi-phase Python pipeline that turns an entire YouTube channel
([Comprehensible Input Korean](https://www.youtube.com/@ComprehensibleInputKorean),
175 videos) into:

1. **An Anki deck** with one card per subtitle line: sliced audio clip, Korean
   sentence, and timestamps.
2. **A personalized watch order**, which ranks every video by *predicted
   comprehension*: the share of its words you already know, measured against
   your own known-word list rather than video length or average word frequency.

## Phases (`pipeline.py`)

| Phase | What it does |
|---|---|
| 1 | Download audio (`.m4a`) for every video with `yt-dlp` |
| 2 | Download the manual (human-made) Korean subtitles where they exist |
| 3 | Transcribe the rest with the [Soniox](https://soniox.com) speech-to-text API and build SRTs from the JSON |
| 4 | Slice per-line audio clips with [subs2cia](https://github.com/mattvsjapan/subs2cia) |
| 5 | Combine the TSVs and package everything into an importable `.apkg` |

Each phase checkpoints its outputs and skips work that's already done, so after
an interruption you just re-run it:

```bash
python pipeline.py            # all phases
python pipeline.py --phase 4  # a single phase
```

## Difficulty ranking

| Script | Purpose |
|---|---|
| `analyze3.py` | Tokenizes every transcript with [kiwipiepy](https://github.com/bab2min/kiwipiepy), then scores each video against your known words and a KoFREN frequency ranking |
| `cefr_grade.py` | Combines the channel's own level tags with the transcript metrics to assign CEFR levels |
| `gen_report.py` | Writes the Markdown difficulty report and CSVs |
| `post_pipeline.py` | Re-runs the analysis and reports after new transcripts come in |
| `make_srts.py` | Converts YouTube auto-subs to SRT for the first-pass analysis |

## Setup

```bash
pip install -r requirements.txt   # plus ffmpeg on your PATH
```

- Phases 3 and 5 call the transcription and `apkg_export.py` helpers from [dojo-prompts](https://github.com/mattvsjapan/dojo-prompts), which should be cloned into `$KO_DIR/dojo-prompts`.

- Put `SONIOX_API_KEY=...` in the environment or in a `.env` next to the scripts. The `.env` file is gitignored.
- Generate the video list:
  ```bash
  yt-dlp --flat-playlist --print "%(id)s\t%(duration)s\t%(title)s" "https://www.youtube.com/@ComprehensibleInputKorean/videos" > videos.tsv
  ```
- Optional environment variables:
  - `KO_DIR`: data folder with the KoFREN frequency list and outputs. Defaults to the parent folder.
  - `KNOWN_WORDS_DIR`: where your `known_words.csv` / AnkiMorphs `known_morphs-*.csv` exports live. Defaults to `~/Downloads`.

Downloaded media, transcripts, and generated decks aren't included in this repo.
