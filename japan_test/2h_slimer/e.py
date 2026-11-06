import json
import unicodedata
from pathlib import Path
from collections import defaultdict

import sandbox.japan_test.main as jp


# ============================================================
# CONFIG
#
# 實驗目的：
#
# Baseline:
#     Standard phoneme-level Edit Distance
#
# Matrix:
#     Weighted phoneme-level Edit Distance
#
# 唯一差別：
#
#     Baseline SUB cost = 1
#
#     Matrix SUB cost =
#         1 - calculated_score
#
# ============================================================

base_path = Path(
    "sandbox/japan_test/2h_slimer/debug-4"
)


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
    "ヨルシカ_あの夏に咲け",
    "ヨルシカ_アポリア(",
    "ヨルシカ_あぶく",
    
]

# None = 全部歌曲
#
# 例如：
#
# TARGET_SONGS = {
#     "ヨルシカ_思想犯"
# }
#
TARGET_SONGS = None


lyrics_file = "lyrics_roma.json"
lyrics_field = "hira"

asr_file = "whisper_roma.json"
asr_field = "line"


# ============================================================
# DEBUG
# ============================================================

# 是否顯示每首歌前面多少 phoneme token
SHOW_TOKEN_PREVIEW = True

TOKEN_PREVIEW_COUNT = 40


# 是否顯示每首歌最佳路徑實際使用的 Matrix Pair
SHOW_MATRIX_HITS = True


# ============================================================
# SUBSTITUTION MATRIX
#
# 目前先用 Python dict 代替 SQL。
#
# Key:
#
#     (Lyrics phoneme, Whisper phoneme)
#
# Value:
#
#     calculated_score
#
# 注意方向：
#
#     Lyrics -> Whisper
#
# d -> t 不等於 t -> d
# ============================================================

SUBSTITUTION_SCORES = {

    # ========================================================
    # LEARNED SCORES
    # ========================================================

    ("g", "k"): 0.2814498933901919,

    ("d", "t"): 0.2684931506849315,

    ("n", "m"): 0.2545454545454545,

    ("r", "n"): 0.24350649350649353,

    ("k", "ch"): 0.19852941176470587,

    ("s", "z"): 0.1873015873015873,

    ("m", "w"): 0.1588235294117647,

    ("p", "t"): 0.14857142857142858,

    ("f", "k"): 0.13424657534246576,

    ("t", "b"): 0.13197278911564628,

    ("t", "d"): 0.13197278911564628,

    ("k", "g"): 0.11082802547770701,

    ("b", "g"): 0.09577464788732395,

    ("w", "h"): 0.08064516129032258,

    ("z", "s"): 0.07804232804232804,

    ("z", "ts"): 0.07804232804232804,

    ("sh", "j"): 0.07804232804232804,

    ("ch", "sh"): 0.07804232804232804,

    ("m", "b"): 0.07388535031847134,

    ("b", "r"): 0.07307692307692307,

    ("ch", "j"): 0.07307692307692307,

    ("f", "p"): 0.07307692307692307,

    ("j", "d"): 0.0707070707070707,

    ("r", "d"): 0.06748971193415639,

    ("k", "f"): 0.06617647058823528,

    ("b", "m"): 0.04218106995884774,

    ("m", "n"): 0.03611111111111111,

    ("m", "g"): 0.02256944444444444,

    ("d", "b"): 0.017326732673267328,

    ("f", "n"): 0.017326732673267328,

    ("r", "m"): 0.017326732673267328,

    ("t", "n"): 0.008258258258258265,

    ("k", "t"): -0.0013440860215053762,

    ("d", "n"): -0.011229314420803778,


    # ========================================================
    # MANUAL PRIOR
    # 人工補上的清濁音 / 對應音
    #
    # score = 0.5
    #
    # 只補目前 learned matrix 裡不存在的 pair
    # ========================================================

    # は行 ↔ ば行
    # h ↔ b
    ("h", "b"): 0.5,
    ("b", "h"): 0.5,


    # し ↔ じ
    #
    # sh -> j 已經有 learned score
    # 所以只補反方向
    ("j", "sh"): 0.5,


    # ち ↔ ぢ
    #
    # ch -> j 已經有 learned score
    # 所以只補反方向
    ("j", "ch"): 0.5,


    # つ ↔ づ / ず
    #
    # z -> ts 已經有 learned score
    # 所以只補反方向
    ("ts", "z"): 0.5,
}

# ============================================================
# MATRIX PARAMETERS
# ============================================================

LAMBDA_SCORE = 1.0


# False:
#
#     negative score -> 0
#
# 例如：
#
#     d -> n = -0.011
#
# 最終依然：
#
#     SUB cost = 1
#
USE_NEGATIVE_SCORE = False


# ============================================================
# PHONEME DEFINITION
# ============================================================
#
# 這裡的目的：
#
# "shiranai"
#
# ->
#
# ["sh", "i", "r", "a", "n", "a", "i"]
#
#
# "chizu"
#
# ->
#
# ["ch", "i", "z", "u"]
#
#
# "tsuki"
#
# ->
#
# ["ts", "u", "k", "i"]
#
# ============================================================


# 一定要由長到短比
MULTI_PHONEMES = sorted(
    {
        "tch",

        "sh",
        "ch",
        "ts",

        "ky",
        "gy",

        "ny",

        "hy",
        "by",
        "py",

        "my",
        "ry",

        # 某些 Romanization 可能出現
        "ty",
        "dy",

        "sy",
        "zy",

        "fy",
    },
    key=len,
    reverse=True
)


SINGLE_PHONEMES = {
    "a",
    "i",
    "u",
    "e",
    "o",

    "k",
    "g",

    "s",
    "z",

    "t",
    "d",

    "n",

    "h",
    "f",

    "b",
    "p",

    "m",

    "y",

    "r",

    "w",

    "j",

    # 促音等
    "q",

    # 外來語可能出現
    "v",
}


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text: str) -> str:
    """
    移除：
        punctuation
        separator
        whitespace

    但保留英文字母。
    """

    cleaned = []

    for char in text:

        category = unicodedata.category(
            char
        )

        if category.startswith("P"):
            continue

        if category.startswith("Z"):
            continue

        if char.isspace():
            continue

        cleaned.append(
            char
        )

    return "".join(
        cleaned
    )


# ============================================================
# LOAD SONG
# ============================================================

def load_song(song_name: str):

    song_path = (
        base_path
        / song_name
    )

    with open(
        song_path / lyrics_file,
        "r",
        encoding="utf-8"
    ) as f:

        lyrics_json = json.load(
            f
        )

    with open(
        song_path / asr_file,
        "r",
        encoding="utf-8"
    ) as f:

        asr_json = json.load(
            f
        )

    lyrics_data = [
        item[lyrics_field]
        for item in lyrics_json
    ]

    asr_data = [
        item[asr_field]
        for item in asr_json
    ]

    return (
        lyrics_data,
        asr_data
    )


# ============================================================
# ROMAJI -> PHONEME
# ============================================================

def split_romaji_phonemes(
    romaji: str
):
    """
    Greedy phoneme tokenizer.

    Example:

        shiranai

    ->

        [
            "sh",
            "i",
            "r",
            "a",
            "n",
            "a",
            "i"
        ]
    """

    romaji = (
        clean_text(
            romaji
        )
        .lower()
    )

    tokens = []

    i = 0

    while i < len(romaji):

        matched = False

        # ----------------------------------------------------
        # 1. Multi-character phoneme
        # ----------------------------------------------------

        for phoneme in MULTI_PHONEMES:

            if romaji.startswith(
                phoneme,
                i
            ):

                tokens.append(
                    phoneme
                )

                i += len(
                    phoneme
                )

                matched = True

                break

        if matched:
            continue

        # ----------------------------------------------------
        # 2. Single-character phoneme
        # ----------------------------------------------------

        char = romaji[i]

        if char in SINGLE_PHONEMES:

            tokens.append(
                char
            )

        else:
            # 不直接丟掉未知符號。
            #
            # 如果 Romanization 有我們沒定義的 token，
            # 先保留，避免 Sequence 被偷偷縮短。
            tokens.append(
                char
            )

        i += 1

    return tokens


# ============================================================
# JAPANESE -> PHONEME TOKENS
# ============================================================

def phoneme_tokens(
    text: str
):
    """
    先利用原本 jp.analyze_japanese_phonetics
    轉 Roma。

    separator=" "

    不假設它一定是 phoneme separator。

    因此之後仍然會逐 chunk 做
    split_romaji_phonemes()。

    這樣兩種情況都能處理：

    情況 A：
        "sh i r a"

    情況 B：
        "shira"

    最後都會變：

        ["sh", "i", "r", "a"]
    """

    romaji = (
        jp.analyze_japanese_phonetics(
            text,
            mode="roma",
            separator=" "
        )
    )

    result = []

    # jp 如果真的有 separator
    # 就逐 chunk 處理
    for chunk in romaji.split():

        chunk_tokens = (
            split_romaji_phonemes(
                chunk
            )
        )

        result.extend(
            chunk_tokens
        )

    return result


# ============================================================
# FLATTEN WHOLE SONG
# ============================================================

def flatten_phoneme_sequence(
    lines
):
    """
    整首歌曲攤平成一條 phoneme sequence。

    Example:

        [
            "k",
            "a",
            "z",
            "e",
            ...
        ]
    """

    sequence = []

    for text in lines:

        tokens = phoneme_tokens(
            text
        )

        sequence.extend(
            tokens
        )

    return sequence


# ============================================================
# SUBSTITUTION COST
# ============================================================

def get_matrix_score(
    lyrics_token,
    whisper_token
):
    """
    回傳 learned score。

    Matrix 沒有：
        0

    Negative score 第一版：
        可設定是否使用。
    """

    score = (
        SUBSTITUTION_SCORES.get(
            (
                lyrics_token,
                whisper_token
            ),
            0.0
        )
    )

    if not USE_NEGATIVE_SCORE:

        score = max(
            0.0,
            score
        )

    return score


def get_substitution_cost(
    lyrics_token,
    whisper_token,
    use_matrix
):
    """
    Match:

        cost = 0


    Baseline mismatch:

        cost = 1


    Matrix mismatch:

        cost =
            1 - lambda * score
    """

    # --------------------------------------------------------
    # MATCH
    # --------------------------------------------------------

    if (
        lyrics_token
        == whisper_token
    ):
        return 0.0

    # --------------------------------------------------------
    # BASELINE
    # --------------------------------------------------------

    if not use_matrix:
        return 1.0

    # --------------------------------------------------------
    # MATRIX
    # --------------------------------------------------------

    score = get_matrix_score(
        lyrics_token,
        whisper_token
    )

    cost = (
        1.0
        - LAMBDA_SCORE
        * score
    )

    # Edit cost 不允許小於 0
    return max(
        0.0,
        cost
    )


# ============================================================
# EDIT DISTANCE
# ============================================================
#
# Traceback code:
#
# 0 = diagonal
# 1 = delete / up
# 2 = insert / left
#
# ============================================================

DIAGONAL = 0
DELETE = 1
INSERT = 2


def edit_distance(
    lyrics_tokens,
    whisper_tokens,
    use_matrix=False,
    return_traceback=False
):
    """
    Phoneme-level Levenshtein Distance.

    Baseline:
        Match = 0
        Sub   = 1
        Ins   = 1
        Del   = 1

    Matrix:
        Match = 0
        Sub   = 1 - score
        Ins   = 1
        Del   = 1

    注意：

    這裡絕對不能交換 Lyrics / Whisper。

    Matrix 是：

        Lyrics -> Whisper

    有方向性的。
    """

    n = len(
        lyrics_tokens
    )

    m = len(
        whisper_tokens
    )

    # --------------------------------------------------------
    # DP only uses 2 rows
    # --------------------------------------------------------

    previous_row = [
        float(j)
        for j in range(
            m + 1
        )
    ]

    # --------------------------------------------------------
    # Traceback matrix
    #
    # bytearray 比 full float matrix 省很多記憶體
    # --------------------------------------------------------

    trace = None

    if return_traceback:

        trace = [
            bytearray(
                m + 1
            )
            for _ in range(
                n + 1
            )
        ]

        # 第一列只能 INSERT
        for j in range(
            1,
            m + 1
        ):
            trace[0][j] = INSERT

        # 第一欄只能 DELETE
        for i in range(
            1,
            n + 1
        ):
            trace[i][0] = DELETE

    # --------------------------------------------------------
    # DP
    # --------------------------------------------------------

    for i in range(
        1,
        n + 1
    ):

        lyrics_token = (
            lyrics_tokens[
                i - 1
            ]
        )

        current_row = [
            float(i)
        ]

        for j in range(
            1,
            m + 1
        ):

            whisper_token = (
                whisper_tokens[
                    j - 1
                ]
            )

            # ------------------------------------------------
            # DELETE
            # ------------------------------------------------

            delete_cost = (
                previous_row[j]
                + 1.0
            )

            # ------------------------------------------------
            # INSERT
            # ------------------------------------------------

            insert_cost = (
                current_row[
                    j - 1
                ]
                + 1.0
            )

            # ------------------------------------------------
            # MATCH / SUBSTITUTE
            # ------------------------------------------------

            sub_cost = (
                get_substitution_cost(
                    lyrics_token,
                    whisper_token,
                    use_matrix
                )
            )

            diagonal_cost = (
                previous_row[
                    j - 1
                ]
                + sub_cost
            )

            # ------------------------------------------------
            # Tie-breaking
            #
            # 優先 diagonal。
            #
            # 對 phoneme alignment 比較合理，
            # 且可以避免 equal cost 時亂拆成
            # INSERT + DELETE。
            # ------------------------------------------------

            best_cost = (
                diagonal_cost
            )

            move = DIAGONAL

            if (
                delete_cost
                < best_cost
            ):
                best_cost = (
                    delete_cost
                )

                move = DELETE

            if (
                insert_cost
                < best_cost
            ):
                best_cost = (
                    insert_cost
                )

                move = INSERT

            current_row.append(
                best_cost
            )

            if return_traceback:

                trace[i][j] = (
                    move
                )

        previous_row = (
            current_row
        )

    distance = (
        previous_row[-1]
    )

    # --------------------------------------------------------
    # No traceback requested
    # --------------------------------------------------------

    if not return_traceback:

        return {
            "distance": distance
        }

    # --------------------------------------------------------
    # TRACEBACK
    # --------------------------------------------------------

    i = n
    j = m

    alignment = []

    matrix_hits = defaultdict(
        int
    )

    matrix_discount_total = 0.0

    match_count = 0
    substitution_count = 0
    insertion_count = 0
    deletion_count = 0

    while (
        i > 0
        or j > 0
    ):

        # ----------------------------------------------------
        # First column
        # ----------------------------------------------------

        if j == 0:

            lyrics_token = (
                lyrics_tokens[
                    i - 1
                ]
            )

            alignment.append({
                "lyrics": lyrics_token,
                "whisper": "-",
                "op": "DELETE",
                "matrix_score": 0.0
            })

            deletion_count += 1

            i -= 1

            continue

        # ----------------------------------------------------
        # First row
        # ----------------------------------------------------

        if i == 0:

            whisper_token = (
                whisper_tokens[
                    j - 1
                ]
            )

            alignment.append({
                "lyrics": "-",
                "whisper": whisper_token,
                "op": "INSERT",
                "matrix_score": 0.0
            })

            insertion_count += 1

            j -= 1

            continue

        move = (
            trace[i][j]
        )

        # ----------------------------------------------------
        # DIAGONAL
        # ----------------------------------------------------

        if move == DIAGONAL:

            lyrics_token = (
                lyrics_tokens[
                    i - 1
                ]
            )

            whisper_token = (
                whisper_tokens[
                    j - 1
                ]
            )

            if (
                lyrics_token
                == whisper_token
            ):

                op = "MATCH"

                score = 0.0

                match_count += 1

            else:

                op = "SUB"

                substitution_count += 1

                if use_matrix:

                    score = (
                        get_matrix_score(
                            lyrics_token,
                            whisper_token
                        )
                    )

                    if score > 0:

                        pair = (
                            lyrics_token,
                            whisper_token
                        )

                        matrix_hits[
                            pair
                        ] += 1

                        matrix_discount_total += (
                            LAMBDA_SCORE
                            * score
                        )

                else:
                    score = 0.0

            alignment.append({
                "lyrics": lyrics_token,
                "whisper": whisper_token,
                "op": op,
                "matrix_score": score
            })

            i -= 1
            j -= 1

        # ----------------------------------------------------
        # DELETE
        # ----------------------------------------------------

        elif move == DELETE:

            lyrics_token = (
                lyrics_tokens[
                    i - 1
                ]
            )

            alignment.append({
                "lyrics": lyrics_token,
                "whisper": "-",
                "op": "DELETE",
                "matrix_score": 0.0
            })

            deletion_count += 1

            i -= 1

        # ----------------------------------------------------
        # INSERT
        # ----------------------------------------------------

        else:

            whisper_token = (
                whisper_tokens[
                    j - 1
                ]
            )

            alignment.append({
                "lyrics": "-",
                "whisper": whisper_token,
                "op": "INSERT",
                "matrix_score": 0.0
            })

            insertion_count += 1

            j -= 1

    alignment.reverse()

    return {
        "distance": distance,

        "alignment": alignment,

        "matrix_hits":
            dict(matrix_hits),

        "matrix_hit_count":
            sum(
                matrix_hits.values()
            ),

        "matrix_discount_total":
            matrix_discount_total,

        "counts": {
            "MATCH":
                match_count,

            "SUB":
                substitution_count,

            "INSERT":
                insertion_count,

            "DELETE":
                deletion_count,
        }
    }


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(
    lyrics_tokens,
    whisper_tokens,
    use_matrix=False,
    traceback=False
):

    result = edit_distance(
        lyrics_tokens,
        whisper_tokens,
        use_matrix=use_matrix,
        return_traceback=traceback
    )

    distance = (
        result["distance"]
    )

    denominator = max(
        len(
            lyrics_tokens
        ),
        len(
            whisper_tokens
        )
    )

    if denominator == 0:

        normalized_distance = 0.0

    else:

        normalized_distance = (
            distance
            / denominator
        )

    similarity = (
        1.0
        - normalized_distance
    )

    result.update({
        "normalized_distance":
            normalized_distance,

        "similarity":
            similarity,

        "lyrics_length":
            len(
                lyrics_tokens
            ),

        "asr_length":
            len(
                whisper_tokens
            ),
    })

    return result


# ============================================================
# SINGLE SONG
# ============================================================

def run_song_test(
    song_name,
    lyrics_data,
    asr_data
):

    print(
        "\n"
        + "#" * 120
    )

    print(
        f"歌曲：{song_name}"
    )

    print(
        "#" * 120
    )

    # --------------------------------------------------------
    # SAME SEQUENCE FOR BOTH TESTS
    # --------------------------------------------------------

    lyrics_tokens = (
        flatten_phoneme_sequence(
            lyrics_data
        )
    )

    whisper_tokens = (
        flatten_phoneme_sequence(
            asr_data
        )
    )

    # --------------------------------------------------------
    # Token debug
    # --------------------------------------------------------

    if SHOW_TOKEN_PREVIEW:

        print(
            "\n[Lyrics phoneme preview]"
        )

        print(
            lyrics_tokens[
                :TOKEN_PREVIEW_COUNT
            ]
        )

        print(
            "\n[Whisper phoneme preview]"
        )

        print(
            whisper_tokens[
                :TOKEN_PREVIEW_COUNT
            ]
        )

    # --------------------------------------------------------
    # BASELINE
    # --------------------------------------------------------

    baseline = (
        calculate_metrics(
            lyrics_tokens,
            whisper_tokens,
            use_matrix=False,
            traceback=False
        )
    )

    # --------------------------------------------------------
    # MATRIX
    #
    # Weighted version needs traceback so that
    # we know whether learned pairs are actually used
    # in the optimal path.
    # --------------------------------------------------------

    weighted = (
        calculate_metrics(
            lyrics_tokens,
            whisper_tokens,
            use_matrix=True,
            traceback=True
        )
    )

    # --------------------------------------------------------
    # DIFFERENCE
    # --------------------------------------------------------

    similarity_improvement = (
        weighted["similarity"]
        - baseline["similarity"]
    )

    distance_reduction = (
        baseline["distance"]
        - weighted["distance"]
    )

    # --------------------------------------------------------
    # PRINT
    # --------------------------------------------------------

    print(
        "\n[Baseline]"
    )

    print(
        f"Edit Distance : "
        f"{baseline['distance']:.9f}"
    )

    print(
        f"NED           : "
        f"{baseline['normalized_distance']:.9f}"
    )

    print(
        f"Similarity    : "
        f"{baseline['similarity']:.9f}"
    )

    print(
        "\n[Weighted Matrix]"
    )

    print(
        f"Edit Distance : "
        f"{weighted['distance']:.9f}"
    )

    print(
        f"NED           : "
        f"{weighted['normalized_distance']:.9f}"
    )

    print(
        f"Similarity    : "
        f"{weighted['similarity']:.9f}"
    )

    print(
        "\n[Improvement]"
    )

    print(
        f"Distance Reduction      : "
        f"{distance_reduction:+.9f}"
    )

    print(
        f"Similarity Improvement : "
        f"{similarity_improvement:+.9f}"
    )

    print(
        "\n[Weighted optimal path]"
    )

    print(
        f"MATCH  : "
        f"{weighted['counts']['MATCH']}"
    )

    print(
        f"SUB    : "
        f"{weighted['counts']['SUB']}"
    )

    print(
        f"INSERT : "
        f"{weighted['counts']['INSERT']}"
    )

    print(
        f"DELETE : "
        f"{weighted['counts']['DELETE']}"
    )

    print(
        f"\nOptimal Matrix Hits : "
        f"{weighted['matrix_hit_count']}"
    )

    print(
        f"Total Matrix Discount : "
        f"{weighted['matrix_discount_total']:.9f}"
    )

    # --------------------------------------------------------
    # Actual Matrix pairs used by optimal path
    # --------------------------------------------------------

    if SHOW_MATRIX_HITS:

        print(
            "\n[Matrix pairs used in optimal path]"
        )

        if not weighted[
            "matrix_hits"
        ]:

            print(
                "NONE"
            )

        else:

            ordered_hits = sorted(
                weighted[
                    "matrix_hits"
                ].items(),

                key=lambda item: (
                    -item[1],
                    item[0][0],
                    item[0][1]
                )
            )

            for (
                lyrics_token,
                whisper_token
            ), count in ordered_hits:

                score = (
                    SUBSTITUTION_SCORES[
                        (
                            lyrics_token,
                            whisper_token
                        )
                    ]
                )

                print(
                    f"{lyrics_token:>5}"
                    f" -> "
                    f"{whisper_token:<5}"
                    f" | count={count:<3}"
                    f" | score={score:.6f}"
                    f" | sub_cost="
                    f"{1.0 - max(0.0, score):.6f}"
                )

    return {
        "song":
            song_name,

        "baseline":
            baseline,

        "weighted":
            weighted,

        "similarity_improvement":
            similarity_improvement,

        "distance_reduction":
            distance_reduction,
    }


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    all_results = []

    all_matrix_hits = defaultdict(
        int
    )

    # ========================================================
    # SONG LOOP
    # ========================================================

    for song_name in test_data:

        if (
            TARGET_SONGS is not None
            and song_name
            not in TARGET_SONGS
        ):
            continue

        (
            lyrics_data,
            asr_data
        ) = load_song(
            song_name
        )

        result = run_song_test(
            song_name,
            lyrics_data,
            asr_data
        )

        all_results.append(
            result
        )

        for (
            pair,
            count
        ) in result[
            "weighted"
        ][
            "matrix_hits"
        ].items():

            all_matrix_hits[
                pair
            ] += count

    # ========================================================
    # VALIDATION
    # ========================================================

    if not all_results:

        raise RuntimeError(
            "沒有歌曲被測試。"
        )

    # ========================================================
    # SUMMARY TABLE
    # ========================================================

    print(
        "\n"
        + "=" * 130
    )

    print(
        "ALL SONGS - BASELINE VS WEIGHTED SUBSTITUTION MATRIX"
    )

    print(
        "=" * 130
    )

    print(
        f"{'Song':<35}"
        f"{'Base Sim':>12}"
        f"{'Matrix Sim':>14}"
        f"{'Δ Sim':>14}"
        f"{'Base ED':>12}"
        f"{'Matrix ED':>14}"
        f"{'Hits':>8}"
    )

    print(
        "-" * 130
    )

    for result in all_results:

        print(
            f"{result['song']:<35}"

            f"{result['baseline']['similarity']:>12.6f}"

            f"{result['weighted']['similarity']:>14.6f}"

            f"{result['similarity_improvement']:>+14.9f}"

            f"{result['baseline']['distance']:>12.3f}"

            f"{result['weighted']['distance']:>14.6f}"

            f"{result['weighted']['matrix_hit_count']:>8}"
        )

    # ========================================================
    # AVERAGE
    # ========================================================

    count = len(
        all_results
    )

    avg_baseline_similarity = (
        sum(
            result[
                "baseline"
            ][
                "similarity"
            ]
            for result in all_results
        )
        / count
    )

    avg_weighted_similarity = (
        sum(
            result[
                "weighted"
            ][
                "similarity"
            ]
            for result in all_results
        )
        / count
    )

    avg_improvement = (
        sum(
            result[
                "similarity_improvement"
            ]
            for result in all_results
        )
        / count
    )

    avg_baseline_distance = (
        sum(
            result[
                "baseline"
            ][
                "distance"
            ]
            for result in all_results
        )
        / count
    )

    avg_weighted_distance = (
        sum(
            result[
                "weighted"
            ][
                "distance"
            ]
            for result in all_results
        )
        / count
    )

    improved_song_count = sum(
        1
        for result in all_results
        if (
            result[
                "similarity_improvement"
            ]
            > 1e-12
        )
    )

    unchanged_song_count = sum(
        1
        for result in all_results
        if abs(
            result[
                "similarity_improvement"
            ]
        )
        <= 1e-12
    )

    worsened_song_count = sum(
        1
        for result in all_results
        if (
            result[
                "similarity_improvement"
            ]
            < -1e-12
        )
    )

    total_matrix_hits = sum(
        result[
            "weighted"
        ][
            "matrix_hit_count"
        ]
        for result in all_results
    )

    total_matrix_discount = sum(
        result[
            "weighted"
        ][
            "matrix_discount_total"
        ]
        for result in all_results
    )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print(
        "\n"
        + "-" * 130
    )

    print(
        f"測試歌曲數："
        f"{count}"
    )

    print()

    print(
        f"Baseline Avg Similarity : "
        f"{avg_baseline_similarity:.9f}"
    )

    print(
        f"Matrix Avg Similarity   : "
        f"{avg_weighted_similarity:.9f}"
    )

    print(
        f"Average Improvement     : "
        f"{avg_improvement:+.9f}"
    )

    print()

    print(
        f"Baseline Avg ED         : "
        f"{avg_baseline_distance:.9f}"
    )

    print(
        f"Matrix Avg ED           : "
        f"{avg_weighted_distance:.9f}"
    )

    print()

    print(
        f"Improved songs  : "
        f"{improved_song_count}"
    )

    print(
        f"Unchanged songs : "
        f"{unchanged_song_count}"
    )

    print(
        f"Worsened songs  : "
        f"{worsened_song_count}"
    )

    print()

    print(
        f"Total optimal Matrix hits : "
        f"{total_matrix_hits}"
    )

    print(
        f"Total Matrix discount     : "
        f"{total_matrix_discount:.9f}"
    )

    # ========================================================
    # GLOBAL MATRIX HIT REPORT
    # ========================================================

    print(
        "\n"
        + "=" * 90
    )

    print(
        "GLOBAL MATRIX PAIRS USED IN OPTIMAL PATHS"
    )

    print(
        "=" * 90
    )

    if not all_matrix_hits:

        print(
            "NONE"
        )

        print()

        print(
            "WARNING:"
        )

        print(
            "Matrix 完全沒有出現在任何最佳 Edit Distance 路徑中。"
        )

        print(
            "如果這裡是 NONE，優先檢查上方 Lyrics / Whisper phoneme preview。"
        )

    else:

        ordered_global_hits = sorted(
            all_matrix_hits.items(),

            key=lambda item: (
                -item[1],
                item[0][0],
                item[0][1]
            )
        )

        print(
            f"{'Lyrics':>10}"
            f"{'Whisper':>12}"
            f"{'Hits':>10}"
            f"{'Score':>14}"
            f"{'SUB Cost':>14}"
        )

        print(
            "-" * 60
        )

        for (
            lyrics_token,
            whisper_token
        ), hit_count in ordered_global_hits:

            score = (
                SUBSTITUTION_SCORES[
                    (
                        lyrics_token,
                        whisper_token
                    )
                ]
            )

            sub_cost = (
                1.0
                - max(
                    0.0,
                    score
                )
            )

            print(
                f"{lyrics_token:>10}"
                f"{whisper_token:>12}"
                f"{hit_count:>10}"
                f"{score:>14.6f}"
                f"{sub_cost:>14.6f}"
            )