import json
import unicodedata
from pathlib import Path
from collections import Counter

import sandbox.japan_test.main as jp

from .alignment_algorithm import (
    global_align,
    evaluate_real_alignment,
    project_mapping_to_segments,
    calculate_w_coverage,
    calculate_w_alignment_quality,
    filter_w_to_l,
)

# ============================================================
# CONFIG
# ============================================================
MIN_W_COVERAGE = 0.50

MIN_W_EXACT_RATIO = 0.35

MIN_PAIR_SHARE = 0.15

MIN_PAIR_CHARS = 3
base_path = Path("sandbox/japan_test/2h_slimer/debug-4")

test_data = [
    "ヨルシカ_八月、某、月明かり",
    "ヨルシカ_又三郎",
    "ヨルシカ_五月は花緑青の窓辺から",
    "ヨルシカ_春ひさぎ",
    "ヨルシカ_夜行",
    "ヨルシカ_斜陽",
    "ヨルシカ_昼鳶",
    "ヨルシカ_嘘月",
    "ヨルシカ_ヒッチコック",
    "ヨルシカ_へび",
    "ヨルシカ_チノカテ",
    "ヨルシカ_ルバート",
    "ヨルシカ_ただ君に晴れ",
    "ヨルシカ_思想犯",
    "ヨルシカ_忘れてください",
    "ヨルシカ_あの夏に咲け copy"
]

chose = {
    "lyrics": {
        "file": "lyrics_roma.json",
        "field": "hira",
    },
    "asr": {
        "file": "whisper_roma.json",
        "field": "line",
    },
}

TARGET_SONGS = {"ヨルシカ_あの夏に咲け copy"}

GLOBAL_MODE = "roma"

# ============================================================
# TEXT / PHONETIC
# ============================================================

def clean_text(text: str) -> str:
    cleaned = []
    for char in text:
        category = unicodedata.category(char)
        if category.startswith("P") or category.startswith("Z") or char.isspace():
            continue
        cleaned.append(char)
    return "".join(cleaned)


def phonetic_sequence(text: str, mode: str) -> str:
    result = jp.analyze_japanese_phonetics(
        text,
        mode=mode,
        separator=""
    )
    return clean_text(result)

# ============================================================
# LOAD SONG
# ============================================================

def load_song(song_name: str):
    song_path = base_path / song_name

    with open(song_path / chose["lyrics"]["file"], "r", encoding="utf-8") as f:
        lyrics_json = json.load(f)

    with open(song_path / chose["asr"]["file"], "r", encoding="utf-8") as f:
        asr_json = json.load(f)

    lyrics_data = [item[chose["lyrics"]["field"]] for item in lyrics_json]
    asr_data = [item[chose["asr"]["field"]] for item in asr_json]

    return lyrics_json, asr_json, lyrics_data, asr_data

# ============================================================
# BUILD GLOBAL SEGMENTS
# ============================================================

def build_global_segments(source_lines, display_lines, mode, prefix):
    full_sequence = ""
    segments = []

    for index, source_text in enumerate(source_lines):
        hira = phonetic_sequence(source_text, "hira")
        kata = phonetic_sequence(source_text, "kata")
        roma = phonetic_sequence(source_text, "roma")
        vowel = phonetic_sequence(source_text, "vowel")

        representations = {
            "hira": hira,
            "kata": kata,
            "roma": roma,
            "vowel": vowel,
        }

        if mode not in representations:
            raise ValueError(f"不支援 GLOBAL_MODE={mode!r}，可用：{list(representations)}")

        sequence = representations[mode]
        start = len(full_sequence)
        full_sequence += sequence
        end = len(full_sequence)

        segments.append({
            "id": f"{prefix}{index + 1}",
            "index": index,
            "start": start,
            "end": end,
            "sequence": sequence,
            "text": display_lines[index],
            "hira_sequence": hira,
            "kata_sequence": kata,
            "roma_sequence": roma,
            "vowel_sequence": vowel,
        })

    return full_sequence, segments

# ============================================================
# SIMPLIFIED SEGMENT ALIGNMENT OUTPUT
# ============================================================

def print_simple_alignment(lyrics_segments, asr_segments, w_to_l):
    print("\n" + "=" * 80)
    print("Matched Lyrics & Whisper (ASR) Lines")
    print("=" * 80)

    for w_index, w_segment in enumerate(asr_segments):
        links = w_to_l.get(w_index, Counter())
        sorted_links = sorted(links.items(), key=lambda item: item[0])

        if not sorted_links:
            print(f"\n[Whisper {w_segment['id']}] {w_segment['text']}")
            print(f"  └── ↔ UNMATCHED")
            continue

        print(f"\n[Whisper {w_segment['id']}] {w_segment['text']}")
        for l_index, _ in sorted_links:
            l_segment = lyrics_segments[l_index]
            print(f"  └── ↔ [Lyrics {l_segment['id']}] {l_segment['text']}")

# ============================================================
# GLOBAL DP
# ============================================================

def run_real_global_test(song_name, lyrics_json, asr_json, lyrics_data, asr_data, mode="roma"):
    lyrics_display = [item["line"] for item in lyrics_json]
    asr_display = [item[chose["asr"]["field"]] for item in asr_json]

    lyrics_sequence, lyrics_segments = build_global_segments(
        source_lines=lyrics_data,
        display_lines=lyrics_display,
        mode=mode,
        prefix="L",
    )

    asr_sequence, asr_segments = build_global_segments(
        source_lines=asr_data,
        display_lines=asr_display,
        mode=mode,
        prefix="W",
    )

    result = global_align(lyrics_sequence, asr_sequence)

    w_to_l, l_to_w = project_mapping_to_segments(
        result["ref_to_target"],
        lyrics_segments,
        asr_segments,
        len(lyrics_sequence),
        len(asr_sequence),
    )

    coverage_results = calculate_w_coverage(asr_segments, result["target_to_ref"])

    # Call the simplified print function
    print_simple_alignment(lyrics_segments, asr_segments, w_to_l)

    return {
        "result": result,
        "lyrics_segments": lyrics_segments,
        "asr_segments": asr_segments,
        "w_to_l": w_to_l,
        "l_to_w": l_to_w,
        "coverage": coverage_results,
    }

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    for song_name in test_data:
        if TARGET_SONGS is not None and song_name not in TARGET_SONGS:
            continue

        print("\n" + "#" * 80)
        print(f"歌曲：{song_name}")
        print("#" * 80)

        lyrics_json, asr_json, lyrics_data, asr_data = load_song(song_name)

        run_real_global_test(
            song_name=song_name,
            lyrics_json=lyrics_json,
            asr_json=asr_json,
            lyrics_data=lyrics_data,
            asr_data=asr_data,
            mode=GLOBAL_MODE,
        )