import csv
import json
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import sandbox.japan_test.main as jp


# ============================================================
# CONFIG
# ============================================================

BASE_PATH = Path("sandbox/japan_test/2h_slimer/debug-4")

TEST_DATA = [
    "ヨルシカ_へび",
    "ヨルシカ_春泥棒",
    "ヨルシカ_左右盲",
    "ヨルシカ_ルバート",
    "ヨルシカ_アルジャーノン",
    "ヨルシカ_アポリア(",
    "ヨルシカ_チノカテ",
    "ヨルシカ_あぶく",
    "ヨルシカ_又三郎",
    "ヨルシカ_千鳥",
    "ヨルシカ_嘘月",
    "ヨルシカ_斜陽",
    "ヨルシカ_昼鳶",
    "ヨルシカ_夜行",
    "ヨルシカ_だから僕は音楽を辞めた",
    "ヨルシカ_春ひさぎ",
    "ヨルシカ_ヒッチコック",
    "ヨルシカ_八月、某、月明かり",
    "ヨルシカ_五月は花緑青の窓辺から",
]

LYRICS_FILE = "lyrics_roma.json"
ASR_FILE = "whisper_roma.json"

LYRICS_FIELD = "hira"
ASR_FIELD = "line"

OUTPUT_CSV = BASE_PATH / "phoneme_error_summary.csv"

MATCH_SCORE = 2
MISMATCH_SCORE = -1
GAP_SCORE = -2


# ============================================================
# ROMAJI -> PHONEME
# ============================================================

VOWELS = set("aiueo")
CONSONANTS = set("bcdfghjklmnpqrstvwxyz")

MULTI = [
    "tch", "sh", "ch", "ts",
    "ky", "gy", "ny", "hy", "by", "py",
    "my", "ry", "dy", "ty", "jy",
]


def clean_text(text: str) -> str:
    """移除標點、空白。"""
    return "".join(
        c for c in text
        if not unicodedata.category(c).startswith(("P", "Z"))
        and not c.isspace()
    )


def to_roma(text: str) -> str:
    """日文 -> romaji。"""
    roma = jp.analyze_japanese_phonetics(
        text,
        mode="roma",
        separator="",
    )
    return clean_text(roma).lower()


def roma_to_tokens(roma: str) -> list[str]:
    """romaji -> phoneme token，例如 'gakkou' -> ['g','a','q','k','o','u']。"""
    tokens = []
    i = 0

    while i < len(roma):
        c = roma[i]

        # vowel
        if c in VOWELS:
            tokens.append(c)
            i += 1
            continue

        # 促音：kk / tt / pp ... -> q
        if (
            c in CONSONANTS
            and c != "n"
            and i + 1 < len(roma)
            and roma[i + 1] == c
        ):
            tokens.append("q")
            i += 1
            continue

        # 複合子音：sh / ch / ky ...
        matched = False
        for sound in MULTI:
            if roma.startswith(sound, i):
                tokens.append(sound)
                i += len(sound)
                matched = True
                break

        if matched:
            continue

        # 單一子音
        if c in CONSONANTS:
            tokens.append(c)

        i += 1

    return tokens


# ============================================================
# LOAD SONG
# ============================================================


def load_song(song_name: str):
    song_dir = BASE_PATH / song_name

    with open(song_dir / LYRICS_FILE, "r", encoding="utf-8") as f:
        lyrics_json = json.load(f)

    with open(song_dir / ASR_FILE, "r", encoding="utf-8") as f:
        asr_json = json.load(f)

    return lyrics_json, asr_json


def rows_to_tokens(rows, field: str) -> list[str]:
    """整首歌所有 line 直接串成 phoneme token。"""
    tokens = []

    for row in rows:
        text = row[field]
        roma = to_roma(text)
        tokens.extend(roma_to_tokens(roma))

    return tokens


# ============================================================
# NEEDLEMAN-WUNSCH GLOBAL ALIGNMENT
# ============================================================


def needleman_wunsch(ref: list[str], obs: list[str]):
    """
    ref = Lyrics phoneme
    obs = Whisper phoneme

    回傳：
        [(lyrics_token, whisper_token), ...]

    gap 用 None 表示。
    """
    n = len(ref)
    m = len(obs)

    dp = [[0] * (m + 1) for _ in range(n + 1)]
    trace = [[None] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp[i][0] = i * GAP_SCORE
        trace[i][0] = "U"

    for j in range(1, m + 1):
        dp[0][j] = j * GAP_SCORE
        trace[0][j] = "L"

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diagonal = dp[i - 1][j - 1] + (
                MATCH_SCORE if ref[i - 1] == obs[j - 1]
                else MISMATCH_SCORE
            )
            up = dp[i - 1][j] + GAP_SCORE
            left = dp[i][j - 1] + GAP_SCORE

            best = max(diagonal, up, left)
            dp[i][j] = best

            # 同分時優先 diagonal，和你原本腳本一致
            if best == diagonal:
                trace[i][j] = "D"
            elif best == up:
                trace[i][j] = "U"
            else:
                trace[i][j] = "L"

    aligned = []
    i, j = n, m

    while i > 0 or j > 0:
        direction = trace[i][j]

        if i > 0 and j > 0 and direction == "D":
            aligned.append((ref[i - 1], obs[j - 1]))
            i -= 1
            j -= 1

        elif i > 0 and direction == "U":
            aligned.append((ref[i - 1], None))
            i -= 1

        else:
            aligned.append((None, obs[j - 1]))
            j -= 1

    aligned.reverse()
    return aligned


# ============================================================
# STATISTICS
# ============================================================


def get_error_type(lyrics_token, whisper_token):
    if lyrics_token is None:
        return "INSERT"

    if whisper_token is None:
        return "DELETE"

    if lyrics_token != whisper_token:
        return "SUB"

    return "MATCH"


def collect_statistics(
    song_name,
    aligned,
    lyrics_total,
    whisper_total,
    lyrics_song_set,
    whisper_song_set,
    error_counter,
    error_song_set,
):
    """
    統計 phoneme occurrence 與 error。

    CSV 欄位定義：
    - lyrics         : Lyrics phoneme；INSERT 時為 '-'
    - whisper        : Whisper phoneme；DELETE 時為 '-'
    - roma_type      : SUB / INSERT / DELETE
    - all_count      : 這個 phoneme 在全部資料中出現的總次數
                       SUB/DELETE -> 看 Lyrics 端
                       INSERT     -> 看 Whisper 端
    - all_song_count : 這個 phoneme 出現過幾首不同歌曲
    - err_count      : 這一種錯誤 pair 總共發生幾次
    - err_song_count : 這一種錯誤 pair 發生在幾首不同歌曲
    """
    for lyrics_token, whisper_token in aligned:
        if lyrics_token is not None:
            lyrics_total[lyrics_token] += 1
            lyrics_song_set[lyrics_token].add(song_name)

        if whisper_token is not None:
            whisper_total[whisper_token] += 1
            whisper_song_set[whisper_token].add(song_name)

        roma_type = get_error_type(lyrics_token, whisper_token)

        if roma_type == "MATCH":
            continue

        key = (
            lyrics_token if lyrics_token is not None else "-",
            whisper_token if whisper_token is not None else "-",
            roma_type,
        )

        error_counter[key] += 1
        error_song_set[key].add(song_name)


def save_csv(
    lyrics_total,
    whisper_total,
    lyrics_song_set,
    whisper_song_set,
    error_counter,
    error_song_set,
):
    rows = []

    for (lyrics_token, whisper_token, roma_type), err_count in error_counter.items():
        if roma_type == "INSERT":
            all_count = whisper_total[whisper_token]
            all_song_count = len(whisper_song_set[whisper_token])
        else:
            all_count = lyrics_total[lyrics_token]
            all_song_count = len(lyrics_song_set[lyrics_token])

        err_song_count = len(
            error_song_set[(lyrics_token, whisper_token, roma_type)]
        )

        rows.append({
            "lyrics": lyrics_token,
            "whisper": whisper_token,
            "roma_type": roma_type,
            "all_count": all_count,
            "all_song_count": all_song_count,
            "err_count": err_count,
            "err_song_count": err_song_count,
        })

    rows.sort(
        key=lambda x: (
            -x["err_count"],
            x["lyrics"],
            x["whisper"],
        )
    )

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    # utf-8-sig：直接用 Excel 開日文比較不容易亂碼
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "lyrics",
                "whisper",
                "roma_type",
                "all_count",
                "all_song_count",
                "err_count",
                "err_song_count",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    return rows


# ============================================================
# MAIN
# ============================================================


def main():
    lyrics_total = Counter()
    whisper_total = Counter()

    # token -> {song1, song2, ...}
    lyrics_song_set = defaultdict(set)
    whisper_song_set = defaultdict(set)

    # (lyrics, whisper, type) -> count / {songs}
    error_counter = Counter()
    error_song_set = defaultdict(set)

    for song_name in TEST_DATA:
        print(f"Processing: {song_name}")

        lyrics_json, asr_json = load_song(song_name)

        lyrics_tokens = rows_to_tokens(
            lyrics_json,
            LYRICS_FIELD,
        )
        whisper_tokens = rows_to_tokens(
            asr_json,
            ASR_FIELD,
        )

        aligned = needleman_wunsch(
            lyrics_tokens,
            whisper_tokens,
        )

        collect_statistics(
            song_name,
            aligned,
            lyrics_total,
            whisper_total,
            lyrics_song_set,
            whisper_song_set,
            error_counter,
            error_song_set,
        )

    rows = save_csv(
        lyrics_total,
        whisper_total,
        lyrics_song_set,
        whisper_song_set,
        error_counter,
        error_song_set,
    )

    print("\nDone")
    print(f"CSV: {OUTPUT_CSV}")
    print(f"Error types: {len(rows)}")
    print(f"Total errors: {sum(x['err_count'] for x in rows)}")

    print("\nTop 20 errors")
    for row in rows[:20]:
        print(
            f"{row['lyrics']:>4} -> {row['whisper']:<4} "
            f"{row['roma_type']:<6} "
            f"all={row['all_count']:<5} "
            f"all_songs={row['all_song_count']:<3} "
            f"err={row['err_count']:<4} "
            f"err_songs={row['err_song_count']}"
        )


if __name__ == "__main__":
    main()