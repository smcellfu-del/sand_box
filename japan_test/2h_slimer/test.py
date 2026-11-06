import json
import unicodedata
from pathlib import Path

import sandbox.japan_test.main as jp


# ============================================================
# CONFIG
# 目的：
# 比較 Lyrics ↔ Whisper ASR 在不同表示法下的 Edit Distance
#
# 比較模式：
# 1. Roma
# 2. Hiragana
# 3. Katakana
# 4. Vowel
#
# 指標：
# - Edit Distance：越低越好
# - Normalized Edit Distance (NED)：越低越好
# - Edit Similarity = 1 - NED：越高越好
# ============================================================

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
]

# None = 全部歌曲
# 例如只測思想犯：
# TARGET_SONGS = {"ヨルシカ_思想犯"}
TARGET_SONGS = None

lyrics_file = "lyrics_roma.json"
lyrics_field = "hira"

asr_file = "whisper_roma.json"
asr_field = "line"

REPRESENTATION_MODES = {
    "roma": "roma",
    "hira": "hira",
    "kata": "kata",
    "vowel": "vowel",
}


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text: str) -> str:
    """
    移除：
    - 標點符號
    - 空白
    """
    cleaned = []

    for char in text:
        category = unicodedata.category(char)

        if category.startswith("P"):
            continue

        if category.startswith("Z"):
            continue

        if char.isspace():
            continue

        cleaned.append(char)

    return "".join(cleaned)


# ============================================================
# LOAD DATA
# ============================================================

def load_song(song_name: str):
    song_path = base_path / song_name

    with open(
        song_path / lyrics_file,
        "r",
        encoding="utf-8"
    ) as f:
        lyrics_json = json.load(f)

    with open(
        song_path / asr_file,
        "r",
        encoding="utf-8"
    ) as f:
        asr_json = json.load(f)

    lyrics_data = [
        item[lyrics_field]
        for item in lyrics_json
    ]

    asr_data = [
        item[asr_field]
        for item in asr_json
    ]

    return lyrics_data, asr_data


# ============================================================
# PHONETIC REPRESENTATION
# ============================================================

def phonetic_sequence(text: str, mode: str) -> str:
    """
    將文字轉換成指定表示法：

    roma   : 羅馬拼音
    hira   : 平假名
    kata   : 片假名
    vowel  : 母音
    """

    result = jp.analyze_japanese_phonetics(
        text,
        mode=mode,
        separator=""
    )

    return clean_text(result)


def flatten_sequence(lines, mode: str) -> str:
    """
    將整首歌所有 line 攤平成一條完整 sequence。
    """

    return "".join(
        phonetic_sequence(text, mode)
        for text in lines
    )


# ============================================================
# LEVENSHTEIN EDIT DISTANCE
# ============================================================

def levenshtein_distance(ref: str, hyp: str) -> int:
    """
    Levenshtein Distance

    Cost:
    - Match        = 0
    - Substitution = 1
    - Insertion    = 1
    - Deletion     = 1

    使用兩列 DP，避免建立完整 NxM matrix。
    """

    # 讓 hyp 是較短字串，降低記憶體使用量
    if len(ref) < len(hyp):
        ref, hyp = hyp, ref

    previous_row = list(range(len(hyp) + 1))

    for i, ref_char in enumerate(ref, start=1):

        current_row = [i]

        for j, hyp_char in enumerate(hyp, start=1):

            deletion = previous_row[j] + 1

            insertion = current_row[j - 1] + 1

            substitution = (
                previous_row[j - 1]
                + (0 if ref_char == hyp_char else 1)
            )

            current_row.append(
                min(
                    deletion,
                    insertion,
                    substitution
                )
            )

        previous_row = current_row

    return previous_row[-1]


def calculate_edit_metrics(
    lyrics_sequence: str,
    asr_sequence: str
):
    """
    回傳：

    Edit Distance
    Normalized Edit Distance
    Edit Similarity

    NED = distance / max(len(Lyrics), len(ASR))
    Similarity = 1 - NED
    """

    distance = levenshtein_distance(
        lyrics_sequence,
        asr_sequence
    )

    denominator = max(
        len(lyrics_sequence),
        len(asr_sequence)
    )

    if denominator == 0:
        normalized_distance = 0.0

    else:
        normalized_distance = (
            distance / denominator
        )

    similarity = 1.0 - normalized_distance

    return {
        "distance": distance,
        "normalized_distance": normalized_distance,
        "similarity": similarity,
        "lyrics_length": len(lyrics_sequence),
        "asr_length": len(asr_sequence),
    }


# ============================================================
# SINGLE SONG TEST
# ============================================================

def run_song_test(
    song_name: str,
    lyrics_data,
    asr_data
):
    print("\n" + "#" * 110)
    print(f"歌曲：{song_name}")
    print("#" * 110)

    results = {}

    for display_name, actual_mode in REPRESENTATION_MODES.items():

        lyrics_sequence = flatten_sequence(
            lyrics_data,
            actual_mode
        )

        asr_sequence = flatten_sequence(
            asr_data,
            actual_mode
        )

        metrics = calculate_edit_metrics(
            lyrics_sequence,
            asr_sequence
        )

        results[display_name] = metrics

        print(
            f"{display_name:<8} | "
            f"Edit={metrics['distance']:<5} | "
            f"NED={metrics['normalized_distance']:.6f} | "
            f"Similarity={metrics['similarity']:.6f} | "
            f"Lyrics Len={metrics['lyrics_length']:<5} | "
            f"ASR Len={metrics['asr_length']:<5}"
        )

    best_mode = min(
        results,
        key=lambda mode:
        results[mode]["normalized_distance"]
    )

    print(
        f"\n最低 Normalized Edit Distance："
        f"{best_mode} "
        f"({results[best_mode]['normalized_distance']:.6f})"
    )

    return results


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    all_results = {
        mode: []
        for mode in REPRESENTATION_MODES
    }

    tested_song_count = 0

    for song_name in test_data:

        if (
            TARGET_SONGS is not None
            and song_name not in TARGET_SONGS
        ):
            continue

        lyrics_data, asr_data = load_song(
            song_name
        )

        results = run_song_test(
            song_name,
            lyrics_data,
            asr_data
        )

        tested_song_count += 1

        for mode in REPRESENTATION_MODES:
            all_results[mode].append(
                results[mode]
            )

    # ========================================================
    # ALL SONGS SUMMARY
    # ========================================================

    print("\n" + "=" * 110)
    print("全部歌曲 Edit Distance 平均結果")
    print("=" * 110)

    print(
        f"測試歌曲數：{tested_song_count}\n"
    )

    summary = {}

    for mode in REPRESENTATION_MODES:

        mode_results = all_results[mode]

        if not mode_results:
            continue

        avg_distance = (
            sum(
                item["distance"]
                for item in mode_results
            )
            / len(mode_results)
        )

        avg_ned = (
            sum(
                item["normalized_distance"]
                for item in mode_results
            )
            / len(mode_results)
        )

        avg_similarity = (
            sum(
                item["similarity"]
                for item in mode_results
            )
            / len(mode_results)
        )

        summary[mode] = {
            "avg_distance": avg_distance,
            "avg_ned": avg_ned,
            "avg_similarity": avg_similarity,
        }

        print(
            f"{mode:<8} | "
            f"Avg Edit={avg_distance:.3f} | "
            f"Avg NED={avg_ned:.6f} | "
            f"Avg Similarity={avg_similarity:.6f}"
        )

    if summary:

        best_mode = min(
            summary,
            key=lambda mode:
            summary[mode]["avg_ned"]
        )

        print("\n" + "-" * 110)

        print(
            f"整體最低 Avg NED："
            f"{best_mode} "
            f"({summary[best_mode]['avg_ned']:.6f})"
        )
