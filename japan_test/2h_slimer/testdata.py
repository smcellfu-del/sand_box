import json
import unicodedata
from pathlib import Path
from collections import defaultdict, Counter
import sandbox.japan_test.main as jp

from .alignment_algorithm import (
    sequence_similarity,
    global_align,
    evaluate_real_alignment,
    project_mapping_to_segments,
    calculate_w_coverage,
    find_low_coverage_blocks,
    search_loop_lyrics,
    recover_loop_detail
)


# ============================================================
# CONFIG
# 測試項目：
# 1. Roma / Hira / Kata / Roma Mom 表示法比較
# 2. Token Reading 差異診斷
# 3. 真實 Lyrics ↔ ASR Global DP
# 4. 低 Coverage ASR Loop Recovery
# ============================================================

base_path = Path("sandbox/japan_test/2h_slimer/debug-4")

test_data = [
    "ヨルシカ_八月、某、月明かり", "ヨルシカ_又三郎", "ヨルシカ_五月は花緑青の窓辺から",
    "ヨルシカ_春ひさぎ", "ヨルシカ_夜行", "ヨルシカ_斜陽", "ヨルシカ_昼鳶",
    "ヨルシカ_嘘月", "ヨルシカ_ヒッチコック", "ヨルシカ_へび", "ヨルシカ_チノカテ",
    "ヨルシカ_ルバート", "ヨルシカ_ただ君に晴れ" , 'ヨルシカ_思想犯'
]

chose = {
    "lyrics": {"file": "lyrics_roma.json", "field": "hira"},
    "ars": {"file": "whisper_roma.json", "field": "line"}
}

TARGET_SONGS = { 'ヨルシカ_思想犯'}

RUN_REPRESENTATION_TEST = False
RUN_TOKEN_DIAGNOSTIC = False
RUN_REAL_GLOBAL_TEST = True
RUN_LOOP_RECOVERY = False

GLOBAL_MODE = "roma"

REPRESENTATION_MODES = {
    "roma": "roma",
    "hira": "hira",
    "kata": "kata",
    "roma_mom": "vowel"
}

LOOP_COVERAGE_THRESHOLD = 0.50
LOOP_MIN_SCORE = 0.80
LOOP_MAX_LYRIC_SPAN = 6

ROMA_WEIGHT = 0.50
ROMA_MOM_WEIGHT = 0.50


# ============================================================
# COMMON FUNCTIONS
# 測試點：
# 1. 載入 Lyrics / ASR
# 2. 清除空白、標點
# 3. Sudachi 轉 Roma / Roma Mom
# ============================================================

def clean_text(text: str) -> str:
    cleaned = []

    for char in text:
        category = unicodedata.category(char)

        if category.startswith("P") or category.startswith("Z") or char.isspace():
            continue

        cleaned.append(char)

    return "".join(cleaned)


def load_song(song_name: str):
    song_path = base_path / song_name

    with open(song_path / chose["lyrics"]["file"], "r", encoding="utf-8") as f:
        lyrics_json = json.load(f)

    with open(song_path / chose["ars"]["file"], "r", encoding="utf-8") as f:
        ars_json = json.load(f)

    lyrics_data = [item[chose["lyrics"]["field"]] for item in lyrics_json]
    ars_data = [item[chose["ars"]["field"]] for item in ars_json]

    return lyrics_json, ars_json, lyrics_data, ars_data


def phonetic_sequence(text: str, mode: str) -> str:
    actual_mode = "vowel" if mode == "roma_mom" else mode

    result = jp.analyze_japanese_phonetics(
        text,
        mode=actual_mode,
        separator=""
    )

    return clean_text(result)


def flatten_choose_mode(lines, mode):
    return "".join(
        phonetic_sequence(text, mode)
        for text in lines
    )


# ============================================================
# TEST 1 — REPRESENTATION COMPARISON
# 測試點：
# 1. Roma
# 2. Hiragana
# 3. Katakana
# 4. Roma Mom（母音）
# 5. 比較整首 Lyrics ↔ ASR 相似度
# ============================================================

def run_representation_test(lyrics_data, ars_data):
    print("\n" + "=" * 100)
    print("測試一：發音表示法相似度比較")
    print("=" * 100)

    scores = {}

    for display_name in REPRESENTATION_MODES:
        lyrics_flat = flatten_choose_mode(lyrics_data, display_name)
        ars_flat = flatten_choose_mode(ars_data, display_name)

        score = sequence_similarity(
            lyrics_flat,
            ars_flat
        )

        scores[display_name] = score
        print(f"{display_name:<10}：{score:.6f}")

    best_mode = max(scores, key=scores.get)

    print(
        f"最高分表示法：{best_mode} "
        f"（{scores[best_mode]:.6f}）"
    )

    return scores


# ============================================================
# TEST 2 — TOKEN READING DIAGNOSTIC
# 測試點：
# 1. Lyrics / ASR 都經 Sudachi
# 2. 找出 Reading 不一致 Token
# 3. 僅用於觀察，不判斷錯誤來源
# ============================================================

def build_token_reading_map(lines):
    full_reading = ""
    tokens = []
    global_index = 0

    for line_index, text in enumerate(lines, 1):
        token_results = jp.analyze_japanese_phonetics(
            text,
            mode="tokens"
        )

        for token in token_results:
            reading = token["reading"]
            start = len(full_reading)

            full_reading += reading
            end = len(full_reading)

            global_index += 1

            tokens.append({
                "global_index": global_index,
                "line": line_index,
                "surface": token["surface"],
                "reading": reading,
                "romaji": token["romaji"],
                "start": start,
                "end": end
            })

    return full_reading, tokens


def find_tokens_in_range(tokens, start, end):
    return [
        token
        for token in tokens
        if token["end"] > start and token["start"] < end
    ]


def join_token(tokens, field):
    return "".join(token[field] for token in tokens)


def token_key(tokens):
    return tuple(
        (token["line"], token["global_index"])
        for token in tokens
    )


def run_token_diagnostic(lyrics_data, ars_data):
    from difflib import SequenceMatcher

    lyrics_reading, lyrics_tokens = build_token_reading_map(lyrics_data)
    ars_reading, ars_tokens = build_token_reading_map(ars_data)

    matcher = SequenceMatcher(
        None,
        lyrics_reading,
        ars_reading,
        autojunk=False
    )

    print("\n" + "=" * 100)
    print("測試二：Token Reading 差異診斷")
    print("=" * 100)

    seen = set()
    index = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        l_tokens = find_tokens_in_range(
            lyrics_tokens,
            i1,
            i2
        )

        a_tokens = find_tokens_in_range(
            ars_tokens,
            j1,
            j2
        )

        key = (
            token_key(l_tokens),
            token_key(a_tokens)
        )

        if key in seen:
            continue

        seen.add(key)
        index += 1

        print(f"\n#{index}")
        print(f"歌詞文字：{join_token(l_tokens, 'surface')}")
        print(f"ASR 文字 ：{join_token(a_tokens, 'surface')}")
        print(f"歌詞讀音：{join_token(l_tokens, 'reading')}")
        print(f"ASR 讀音 ：{join_token(a_tokens, 'reading')}")
        print(f"歌詞 Roma：{join_token(l_tokens, 'romaji')}")
        print(f"ASR Roma ：{join_token(a_tokens, 'romaji')}")

    print(f"\nToken Reading 差異群組總數：{index}")


# ============================================================
# GLOBAL SEQUENCE DATA
# 測試點：
# 1. Lyrics / ASR 全部攤平成完整 Sequence
# 2. Segment Boundary 不參與 DP
# 3. 每個 Segment 同時保存 Roma / Roma Mom
# 4. 完成 DP 後才能重新投影回 L / W
# ============================================================

def build_repeat_info(lyrics_data):
    groups = defaultdict(list)

    for index, text in enumerate(lyrics_data):
        groups[clean_text(text)].append(index)

    repeated = {
        text: indexes
        for text, indexes in groups.items()
        if len(indexes) >= 2
    }

    repeat_info = {}

    for group_index, (_, indexes) in enumerate(repeated.items(), 1):
        for occurrence, index in enumerate(indexes, 1):
            repeat_info[index] = {
                "group": f"R{group_index}",
                "occurrence": occurrence,
                "total": len(indexes)
            }

    return repeat_info


def build_global_segments(
    lines,
    display_lines,
    mode,
    prefix,
    repeat_info=None
):
    full_sequence = ""
    segments = []

    for index, text in enumerate(lines):
        roma_sequence = phonetic_sequence(
            text,
            "roma"
        )

        roma_mom_sequence = phonetic_sequence(
            text,
            "roma_mom"
        )

        if mode == "roma":
            sequence = roma_sequence

        elif mode == "roma_mom":
            sequence = roma_mom_sequence

        else:
            sequence = phonetic_sequence(
                text,
                mode
            )

        start = len(full_sequence)
        full_sequence += sequence
        end = len(full_sequence)

        repeat = (
            repeat_info.get(index)
            if repeat_info
            else None
        )

        segments.append({
            "id": f"{prefix}{index + 1}",
            "index": index,
            "start": start,
            "end": end,
            "sequence": sequence,
            "roma_sequence": roma_sequence,
            "roma_mom_sequence": roma_mom_sequence,
            "text": display_lines[index],
            "repeat_group": repeat["group"] if repeat else None,
            "repeat_occurrence": repeat["occurrence"] if repeat else None,
            "repeat_total": repeat["total"] if repeat else None
        })

    return full_sequence, segments


def print_global_data(
    song_name,
    mode,
    lyrics_sequence,
    ars_sequence,
    lyrics_segments
):
    print("\n" + "=" * 100)
    print(f"全域對齊資料：{song_name}")
    print("=" * 100)

    print(f"Global DP 表示法       ：{mode}")
    print(f"Lyrics Sequence 長度   ：{len(lyrics_sequence)}")
    print(f"ASR Sequence 長度      ：{len(ars_sequence)}")

    print("\n[重複歌詞]")

    found = False

    for segment in lyrics_segments:
        if not segment["repeat_group"]:
            continue

        found = True

        print(
            f"{segment['id']:<4} "
            f"{segment['repeat_group']:<4} "
            f"第 {segment['repeat_occurrence']}/"
            f"{segment['repeat_total']} 次 "
            f"[{segment['start']},{segment['end']}) "
            f"{segment['text']}"
        )

    if not found:
        print("無完全重複歌詞")


# ============================================================
# MAIN SEGMENT OUTPUT
# 測試點：
# 1. 高 Coverage W → 正常 Global Mapping
# 2. 低 Coverage W → 不直接相信少量 Character Mapping
# 3. 改標記為 Loop Candidate
# ============================================================

def print_segment_alignment(
    lyrics_segments,
    ars_segments,
    w_to_l,
    l_to_w,
    coverage_results
):
    coverage_lookup = {
        item["w_index"]: item
        for item in coverage_results
    }

    print("\n" + "=" * 100)
    print("W ↔ L Segment 全域對齊結果")
    print("=" * 100)

    for w_index, w_segment in enumerate(ars_segments):
        coverage = coverage_lookup[w_index]
        links = w_to_l.get(w_index, Counter())

        if coverage["coverage"] < LOOP_COVERAGE_THRESHOLD:
            print(
                f"\n{w_segment['id']} ↔ "
                f"低覆蓋／Loop 候選 "
                f"(Coverage={coverage['coverage']:.3f})"
            )

            print(f"ASR ：{w_segment['text']}")

            if links:
                temp = ", ".join(
                    f"{lyrics_segments[l_index]['id']}={count}字元"
                    for l_index, count in sorted(links.items())
                )

                print(f"暫時字元落點：{temp}")

            continue

        if not links:
            print(f"\n{w_segment['id']} ↔ 無對應 Lyrics")
            print(f"ASR ：{w_segment['text']}")
            continue

        sorted_links = sorted(
            links.items(),
            key=lambda x: x[0]
        )

        l_ids = [
            lyrics_segments[l_index]["id"]
            for l_index, _ in sorted_links
        ]

        print(
            f"\n{w_segment['id']} ↔ "
            f"{', '.join(l_ids)} "
            f"(Coverage={coverage['coverage']:.3f})"
        )

        print(f"ASR ：{w_segment['text']}")

        for l_index, mapped_chars in sorted_links:
            l_segment = lyrics_segments[l_index]
            repeat_text = ""

            if l_segment["repeat_group"]:
                repeat_text = (
                    f" [{l_segment['repeat_group']} "
                    f"第{l_segment['repeat_occurrence']}/"
                    f"{l_segment['repeat_total']}次]"
                )

            print(
                f"{l_segment['id']}："
                f"{l_segment['text']} "
                f"| 對應字元={mapped_chars}"
                f"{repeat_text}"
            )

    print("\n" + "-" * 100)
    print("未對到任何 W Segment 的 Lyrics")

    unmapped = [
        segment
        for index, segment in enumerate(lyrics_segments)
        if not l_to_w.get(index)
    ]

    if not unmapped:
        print("無")

    else:
        for segment in unmapped:
            print(
                f"{segment['id']}："
                f"{segment['text']}"
            )


# ============================================================
# LOOP RECOVERY
# 測試點：
# 1. 找出連續低 Coverage W
# 2. 整段搜尋完整 Lyrics
# 3. Roma + Roma Mom 各自計分
# 4. Combined = 0.5 Roma + 0.5 Roma Mom
# 5. 找到 Candidate 後再恢復 W ↔ L 細部 Mapping
# ============================================================

def run_loop_recovery(
    result,
    lyrics_segments,
    ars_segments,
    coverage_results
):
    print("\n" + "=" * 100)
    print("Loop Recovery：未對齊 ASR 重複段落恢復")
    print("=" * 100)

    blocks = find_low_coverage_blocks(
        coverage_results,
        threshold=LOOP_COVERAGE_THRESHOLD
    )

    if not blocks:
        print("沒有偵測到 Loop Candidate。")
        return []

    recovered = []

    for block_index, (w_start, w_end) in enumerate(blocks, 1):
        print("\n" + "-" * 100)
        print(
            f"Loop Candidate #{block_index}："
            f"{ars_segments[w_start]['id']} ~ "
            f"{ars_segments[w_end]['id']}"
        )

        for i in range(w_start, w_end + 1):
            print(
                f"{ars_segments[i]['id']}："
                f"{ars_segments[i]['text']}"
            )

        candidates = search_loop_lyrics(
            w_start=w_start,
            w_end=w_end,
            ars_segments=ars_segments,
            lyrics_segments=lyrics_segments,
            max_lyric_span=LOOP_MAX_LYRIC_SPAN,
            roma_weight=ROMA_WEIGHT,
            roma_mom_weight=ROMA_MOM_WEIGHT
        )

        if not candidates:
            print("\n找不到 Lyrics Candidate。")
            continue

        print("\n[前三名 Lyrics 候選]")

        for rank, candidate in enumerate(candidates[:3], 1):
            l_start = candidate["l_start"]
            l_end = candidate["l_end"]

            print(
                f"#{rank} "
                f"{lyrics_segments[l_start]['id']} ~ "
                f"{lyrics_segments[l_end]['id']} | "
                f"Roma={candidate['roma_score']:.3f} | "
                f"Roma Mom={candidate['roma_mom_score']:.3f} | "
                f"綜合={candidate['score']:.3f}"
            )

        best = candidates[0]

        if best["score"] < LOOP_MIN_SCORE:
            print(
                f"\n最佳綜合分數={best['score']:.3f}，"
                f"低於門檻 {LOOP_MIN_SCORE:.3f}，"
                f"暫不判定為 Loop。"
            )
            continue

        detail = recover_loop_detail(
            candidate=best,
            w_start=w_start,
            w_end=w_end,
            ars_segments=ars_segments,
            lyrics_segments=lyrics_segments
        )

        print("\n[Loop 恢復結果]")

        local_w = detail["ars_segments"]
        local_l = detail["lyrics_segments"]
        local_w_to_l = detail["w_to_l"]

        for local_w_index, w_segment in enumerate(local_w):
            links = local_w_to_l.get(
                local_w_index,
                Counter()
            )

            if not links:
                print(
                    f"{w_segment['id']} ↔ "
                    f"無 Lyrics [LOOP]"
                )
                continue

            l_ids = [
                local_l[l_index]["id"]
                for l_index in sorted(links)
            ]

            print(
                f"{w_segment['id']} ↔ "
                f"{', '.join(l_ids)} [LOOP]"
            )

        recovered.append({
            "w_start": w_start,
            "w_end": w_end,
            "best": best,
            "detail": detail
        })

    return recovered


# ============================================================
# TEST 3 — REAL ASR GLOBAL DP
# 測試點：
# 1. 真實 Lyrics ↔ 真實 ASR
# 2. Global DP 主幹使用 Roma
# 3. DP 後恢復 W ↔ L Segment
# 4. 低 Coverage W 再進 Loop Recovery
# 5. Loop Search 使用 Roma + Roma Mom
# ============================================================

def run_real_global_test(
    song_name,
    lyrics_json,
    ars_json,
    lyrics_data,
    ars_data,
    mode="roma"
):
    lyrics_display = [
        item["line"]
        for item in lyrics_json
    ]

    ars_display = [
        item[chose["ars"]["field"]]
        for item in ars_json
    ]

    repeat_info = build_repeat_info(
        lyrics_data
    )

    lyrics_sequence, lyrics_segments = build_global_segments(
        lyrics_data,
        lyrics_display,
        mode,
        prefix="L",
        repeat_info=repeat_info
    )

    ars_sequence, ars_segments = build_global_segments(
        ars_data,
        ars_display,
        mode,
        prefix="W"
    )

    print_global_data(
        song_name,
        mode,
        lyrics_sequence,
        ars_sequence,
        lyrics_segments
    )

    print("\n" + "=" * 100)
    print("測試三：真實 ASR ↔ Lyrics 整首 Global DP")
    print("=" * 100)

    print(
        f"整首 Sequence 相似度："
        f"{sequence_similarity(lyrics_sequence, ars_sequence):.6f}"
    )

    result = global_align(
        lyrics_sequence,
        ars_sequence
    )

    stats = evaluate_real_alignment(
        lyrics_sequence,
        ars_sequence,
        result["ref_to_target"]
    )

    print(f"DP 對齊分數           ：{result['score']}")
    print(f"Lyrics Sequence 長度  ：{len(lyrics_sequence)}")
    print(f"ASR Sequence 長度     ：{len(ars_sequence)}")
    print(f"Lyrics Mapping 覆蓋率 ：{stats['lyrics_coverage']:.6f}")
    print(f"ASR Mapping 覆蓋率    ：{stats['ars_coverage']:.6f}")
    print(f"字元完全相同率        ：{stats['exact_rate']:.6f}")
    print(f"完全相同字元          ：{stats['exact_matches']}/{stats['mapped_pairs']}")

    w_to_l, l_to_w = project_mapping_to_segments(
        result["ref_to_target"],
        lyrics_segments,
        ars_segments,
        len(lyrics_sequence),
        len(ars_sequence)
    )

    coverage_results = calculate_w_coverage(
        ars_segments,
        result["target_to_ref"]
    )

    print_segment_alignment(
        lyrics_segments,
        ars_segments,
        w_to_l,
        l_to_w,
        coverage_results
    )

    recovered = []

    if RUN_LOOP_RECOVERY:
        recovered = run_loop_recovery(
            result,
            lyrics_segments,
            ars_segments,
            coverage_results
        )

    return {
        "result": result,
        "lyrics_segments": lyrics_segments,
        "ars_segments": ars_segments,
        "w_to_l": w_to_l,
        "l_to_w": l_to_w,
        "coverage": coverage_results,
        "loop_recovery": recovered
    }


# ============================================================
# MAIN
# 報告測試順序：
# Test 1：Roma / Hira / Kata / Roma Mom
# Test 2：Token Reading Diagnostic
# Test 3：Real Global DP + Loop Recovery
# ============================================================

if __name__ == "__main__":

    representation_scores = {
        mode: []
        for mode in REPRESENTATION_MODES
    }

    for song_name in test_data:

        if TARGET_SONGS is not None and song_name not in TARGET_SONGS:
            continue

        print("\n" + "#" * 110)
        print(f"歌曲：{song_name}")
        print("#" * 110)

        lyrics_json, ars_json, lyrics_data, ars_data = load_song(
            song_name
        )

        # ====================================================
        # TEST 1 — 發音表示法比較
        # ====================================================

        if RUN_REPRESENTATION_TEST:
            scores = run_representation_test(
                lyrics_data,
                ars_data
            )

            for mode, score in scores.items():
                representation_scores[mode].append(
                    score
                )

        # ====================================================
        # TEST 2 — Token Reading 差異診斷
        # ====================================================

        if RUN_TOKEN_DIAGNOSTIC:
            run_token_diagnostic(
                lyrics_data,
                ars_data
            )

        # ====================================================
        # TEST 3 — Global DP + Loop Recovery
        # ====================================================

        if RUN_REAL_GLOBAL_TEST:
            run_real_global_test(
                song_name,
                lyrics_json,
                ars_json,
                lyrics_data,
                ars_data,
                mode=GLOBAL_MODE
            )

    # ========================================================
    # Representation 全歌曲平均
    # ========================================================

    if RUN_REPRESENTATION_TEST:
        print("\n" + "#" * 110)
        print("發音表示法平均結果")
        print("#" * 110)

        for mode in REPRESENTATION_MODES:
            scores = representation_scores[mode]
            avg = (
                sum(scores) / len(scores)
                if scores
                else 0.0
            )

            print(
                f"{mode:<10}："
                f"{avg:.6f}"
            )