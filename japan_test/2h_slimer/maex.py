import json
from collections import defaultdict
from pathlib import Path


# ============================================================
# CONFIG
# ============================================================

BASE_PATH = Path("sandbox/japan_test/2h_slimer/debug-4/_phoneme_dataset")

REVIEWED_ERROR_FILE = BASE_PATH / "reviewed_error_units.json"

SAVE_TXT = True
OUTPUT_TXT = BASE_PATH / "phoneme_confusion_with_background_report.txt"

INCLUDE_VOWELS = False
INCLUDE_Q = False

VOWELS = {"a", "i", "u", "e", "o"}


# ============================================================
# HELPERS
# ============================================================

def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"找不到檔案：{path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def token_allowed(token):
    if not token or token == "-":
        return False

    if not INCLUDE_VOWELS and token in VOWELS:
        return False

    if not INCLUDE_Q and token == "q":
        return False

    return True


# ============================================================
# LOAD REVIEWED SUBSTITUTIONS
# ============================================================

def load_reviewed_substitutions():
    """
    只使用人工 Review 後：
        review.use_for_matrix == True
    的 substitution。

    統計：
        1. 每個 Lyrics -> ASR substitution 出現幾次
        2. 每個 substitution 出現在幾首不同歌曲

    注意：
        這裡只統計錯誤 substitution，
        不把 MATCH 放進來。
    """
    reviewed = load_json(REVIEWED_ERROR_FILE)

    sub_counts = defaultdict(int)
    pair_songs = defaultdict(set)
    accepted_units = 0

    for item in reviewed:
        review = item.get("review", {})

        if not review.get("use_for_matrix", False):
            continue

        song = item.get("song", "UNKNOWN")
        substitutions = item.get("substitutions", [])

        # 舊資料若沒有 substitutions，就從 alignment 找 SUB
        if not substitutions:
            substitutions = [
                {
                    "l": row.get("l"),
                    "w": row.get("w"),
                }
                for row in item.get("alignment", [])
                if row.get("op") == "SUB"
            ]

        unit_used = False

        for pair in substitutions:
            lyrics_token = pair.get("l")
            asr_token = pair.get("w")

            if not token_allowed(lyrics_token):
                continue

            if not token_allowed(asr_token):
                continue

            if lyrics_token == asr_token:
                continue

            key = (lyrics_token, asr_token)

            sub_counts[key] += 1
            pair_songs[key].add(song)
            unit_used = True

        if unit_used:
            accepted_units += 1

    pair_song_counts = {
        pair: len(songs)
        for pair, songs in pair_songs.items()
    }

    return sub_counts, pair_song_counts, accepted_units


def get_involved_phonemes(sub_counts):
    phonemes = set()

    for lyrics_token, asr_token in sub_counts:
        phonemes.add(lyrics_token)
        phonemes.add(asr_token)

    return sorted(phonemes)


# ============================================================
# SOURCE-CONDITIONED ERROR PROBABILITY
# ============================================================

def calculate_source_error_totals(sub_counts):
    """
    每個 Lyrics phoneme 總共有多少 substitution error。

    例如：
        d -> t = 6
        d -> b = 1
        d -> n = 1

    則：
        d 的總 substitution error = 8
    """
    source_error_totals = defaultdict(int)

    for (lyrics_token, _), count in sub_counts.items():
        source_error_totals[lyrics_token] += count

    return dict(source_error_totals)


def calculate_error_probabilities(
    phonemes,
    sub_counts,
    source_error_totals,
):
    """
    計算：

        Pair Probability
        = 某 Lyrics phoneme 發生錯誤後，
          錯成某 ASR phoneme 的比例。

    例如：
        d -> t = 6
        d 的總錯誤 = 8

        d -> t = 6 / 8 = 0.750
    """
    matrix = {
        lyrics_token: {
            asr_token: 0.0
            for asr_token in phonemes
        }
        for lyrics_token in phonemes
    }

    for (lyrics_token, asr_token), count in sub_counts.items():
        total_errors = source_error_totals.get(
            lyrics_token,
            0,
        )

        if total_errors <= 0:
            continue

        matrix[lyrics_token][asr_token] = (
            count / total_errors
        )

    return matrix


# ============================================================
# BACKGROUND ERROR DISTRIBUTION
# ============================================================

def calculate_background_error_distribution(
    phonemes,
    sub_counts,
):
    """
    Background Error Frequency（背景錯誤頻率）

    不管 Lyrics 原本是哪個 phoneme，
    只看全部人工 Review 的 substitution error，
    最後 ASR target 是某 phoneme 的比例。

    例如全部 reviewed substitution 共 60 筆：

        d -> t = 6
        p -> t = 2
        k -> t = 1
        ... -> t = 1

    則：
        ASR target = t 共 10 筆

        Background(t)
        = 10 / 60
        = 0.1667
    """
    target_error_counts = {
        phoneme: 0
        for phoneme in phonemes
    }

    total_substitution_errors = sum(
        sub_counts.values()
    )

    for (_, asr_token), count in sub_counts.items():
        target_error_counts[asr_token] += count

    if total_substitution_errors <= 0:
        background_probabilities = {
            phoneme: 0.0
            for phoneme in phonemes
        }
    else:
        background_probabilities = {
            phoneme: (
                target_error_counts[phoneme]
                / total_substitution_errors
            )
            for phoneme in phonemes
        }

    return (
        target_error_counts,
        background_probabilities,
        total_substitution_errors,
    )


# ============================================================
# PAIR VS BACKGROUND
# ============================================================

def calculate_lift(
    phonemes,
    sub_counts,
    probability_matrix,
    background_probabilities,
):
    """
    Lift（倍率）只是目前的描述統計，不是最終 DP score。

    Lift =
        Pair Probability / Background Probability

    例如：
        d -> t = 0.750
        Background(t) = 0.167

        Lift = 0.750 / 0.167 ~= 4.49

    意思：
        當來源特別是 d 時，
        錯成 t 的比例約為一般錯誤變成 t 的 4.49 倍。
    """
    lift_matrix = {
        lyrics_token: {
            asr_token: 0.0
            for asr_token in phonemes
        }
        for lyrics_token in phonemes
    }

    for (lyrics_token, asr_token), _ in sub_counts.items():
        pair_probability = probability_matrix[
            lyrics_token
        ][asr_token]

        background_probability = (
            background_probabilities.get(
                asr_token,
                0.0,
            )
        )

        if background_probability <= 0:
            continue

        lift_matrix[lyrics_token][asr_token] = (
            pair_probability
            / background_probability
        )

    return lift_matrix


# ============================================================
# REPORT FORMAT
# ============================================================

def format_observed_report(
    sub_counts,
    pair_song_counts,
    source_error_totals,
    probability_matrix,
    target_error_counts,
    background_probabilities,
    lift_matrix,
):
    lines = [
        "",
        "=" * 126,
        "REVIEWED SUBSTITUTION STATISTICS",
        "=" * 126,
        f"{'Lyrics':>8} "
        f"{'ASR':>8} "
        f"{'Count':>8} "
        f"{'Songs':>8} "
        f"{'SourceErr':>10} "
        f"{'PairProb':>12} "
        f"{'TargetErr':>10} "
        f"{'BgProb':>12} "
        f"{'Lift':>12}",
        "-" * 126,
    ]

    ordered_pairs = sorted(
        sub_counts.items(),
        key=lambda item: (
            item[0][0],
            -item[1],
            item[0][1],
        ),
    )

    for pair, count in ordered_pairs:
        lyrics_token, asr_token = pair

        song_count = pair_song_counts.get(
            pair,
            0,
        )

        source_error_total = source_error_totals.get(
            lyrics_token,
            0,
        )

        pair_probability = probability_matrix[
            lyrics_token
        ][asr_token]

        target_error_count = target_error_counts.get(
            asr_token,
            0,
        )

        background_probability = (
            background_probabilities.get(
                asr_token,
                0.0,
            )
        )

        lift = lift_matrix[
            lyrics_token
        ][asr_token]

        lines.append(
            f"{lyrics_token:>8} "
            f"{asr_token:>8} "
            f"{count:>8} "
            f"{song_count:>8} "
            f"{source_error_total:>10} "
            f"{pair_probability:>12.4f} "
            f"{target_error_count:>10} "
            f"{background_probability:>12.4f} "
            f"{lift:>12.4f}"
        )

    return "\n".join(lines)


def format_background_report(
    phonemes,
    target_error_counts,
    background_probabilities,
    total_substitution_errors,
):
    lines = [
        "",
        "=" * 72,
        "BACKGROUND ERROR DISTRIBUTION",
        "=" * 72,
        f"Total reviewed substitution errors : "
        f"{total_substitution_errors}",
        "",
        f"{'ASR Target':>12} "
        f"{'Error Count':>14} "
        f"{'Background Prob':>18}",
        "-" * 52,
    ]

    ordered = sorted(
        phonemes,
        key=lambda token: (
            -target_error_counts.get(token, 0),
            token,
        ),
    )

    for token in ordered:
        lines.append(
            f"{token:>12} "
            f"{target_error_counts.get(token, 0):>14} "
            f"{background_probabilities.get(token, 0.0):>18.4f}"
        )

    return "\n".join(lines)


def format_probability_matrix(
    phonemes,
    probability_matrix,
    sub_counts,
):
    width = max(
        7,
        max(len(token) for token in phonemes) + 2,
    )

    lines = [
        "",
        "=" * 100,
        "PHONEME CONFUSION PROBABILITY MATRIX",
        "Row = Lyrics / Column = ASR",
        "",
        "Value = P(ASR target | Lyrics source, substitution error)",
        "Range = 0.0 ~ 1.0",
        "NOTE: This is NOT the final Needleman-Wunsch substitution score.",
        "=" * 100,
    ]

    row_label = "L\\ASR"

    header = f"{row_label:>{width}}"
    header += "".join(
        f"{token:>{width}}"
        for token in phonemes
    )
    lines.append(header)

    for lyrics_token in phonemes:
        row = [f"{lyrics_token:>{width}}"]

        for asr_token in phonemes:
            pair = (lyrics_token, asr_token)

            if lyrics_token == asr_token:
                value_text = "-"

            elif sub_counts.get(pair, 0) == 0:
                value_text = "-"

            else:
                value = probability_matrix[
                    lyrics_token
                ][asr_token]

                value_text = f"{value:.3f}"

            row.append(
                f"{value_text:>{width}}"
            )

        lines.append(
            "".join(row)
        )

    return "\n".join(lines)


def format_lift_matrix(
    phonemes,
    lift_matrix,
    sub_counts,
):
    """
    這張 Matrix 只是方便觀察：

        Pair Probability / Background Probability

    不代表最終 DP score。
    """
    width = max(
        8,
        max(len(token) for token in phonemes) + 2,
    )

    lines = [
        "",
        "=" * 100,
        "PAIR / BACKGROUND LIFT MATRIX",
        "Row = Lyrics / Column = ASR",
        "",
        "Value = Pair Probability / Background Probability",
        "NOTE: This is descriptive evidence, NOT the final DP score.",
        "=" * 100,
    ]

    row_label = "L\\ASR"

    header = f"{row_label:>{width}}"
    header += "".join(
        f"{token:>{width}}"
        for token in phonemes
    )
    lines.append(header)

    for lyrics_token in phonemes:
        row = [f"{lyrics_token:>{width}}"]

        for asr_token in phonemes:
            pair = (lyrics_token, asr_token)

            if lyrics_token == asr_token:
                value_text = "-"

            elif sub_counts.get(pair, 0) == 0:
                value_text = "-"

            else:
                value = lift_matrix[
                    lyrics_token
                ][asr_token]

                value_text = f"{value:.3f}"

            row.append(
                f"{value_text:>{width}}"
            )

        lines.append(
            "".join(row)
        )

    return "\n".join(lines)


def build_report(
    phonemes,
    sub_counts,
    pair_song_counts,
    source_error_totals,
    probability_matrix,
    target_error_counts,
    background_probabilities,
    total_substitution_errors,
    lift_matrix,
    accepted_units,
):
    total_sub = sum(sub_counts.values())
    unique_pairs = len(sub_counts)

    lines = [
        "=" * 96,
        "PHONEME CONFUSION + BACKGROUND ERROR REPORT",
        "=" * 96,
        f"Reviewed phonemes       : {', '.join(phonemes)}",
        f"Accepted review units   : {accepted_units}",
        f"Selected SUB count      : {total_sub}",
        f"Unique SUB pairs        : {unique_pairs}",
        f"INCLUDE_VOWELS          : {INCLUDE_VOWELS}",
        f"INCLUDE_Q               : {INCLUDE_Q}",
        "",
        "STEP 1 - PAIR PROBABILITY",
        "-" * 96,
        "For each Lyrics phoneme:",
        "",
        "    Pair Probability",
        "    = pair_count / all substitution errors from that Lyrics phoneme",
        "",
        "Example:",
        "    d -> t = 6",
        "    d total substitution errors = 8",
        "    Pair Probability(d -> t) = 6 / 8 = 0.750",
        "",
        "STEP 2 - BACKGROUND ERROR",
        "-" * 96,
        "Ignore the Lyrics source and count only the ASR target",
        "across ALL reviewed substitution errors.",
        "",
        "    Background Probability(target)",
        "    = all errors ending at that ASR target",
        "      / all reviewed substitution errors",
        "",
        "STEP 3 - PAIR VS BACKGROUND",
        "-" * 96,
        "    Lift",
        "    = Pair Probability / Background Probability",
        "",
        "If Lift > 1:",
        "    the pair occurs more strongly than the general target background.",
        "",
        "If Lift ~= 1:",
        "    the pair is close to the general target background.",
        "",
        "If Lift < 1:",
        "    the pair is weaker than the general target background.",
        "",
        "IMPORTANT",
        "-" * 96,
        "Pair Probability, Background Probability, and Lift are",
        "descriptive statistics only.",
        "",
        "They are NOT yet the final Needleman-Wunsch substitution scores.",
        "Log-odds / smoothing / score scaling can be decided later.",
    ]

    lines.append(
        format_observed_report(
            sub_counts,
            pair_song_counts,
            source_error_totals,
            probability_matrix,
            target_error_counts,
            background_probabilities,
            lift_matrix,
        )
    )

    lines.append(
        format_background_report(
            phonemes,
            target_error_counts,
            background_probabilities,
            total_substitution_errors,
        )
    )

    lines.append(
        format_probability_matrix(
            phonemes,
            probability_matrix,
            sub_counts,
        )
    )

    lines.append(
        format_lift_matrix(
            phonemes,
            lift_matrix,
            sub_counts,
        )
    )

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def main():
    (
        sub_counts,
        pair_song_counts,
        accepted_units,
    ) = load_reviewed_substitutions()

    if not sub_counts:
        raise RuntimeError(
            "沒有可用的人工 Review substitution。"
        )

    phonemes = get_involved_phonemes(
        sub_counts
    )

    source_error_totals = (
        calculate_source_error_totals(
            sub_counts
        )
    )

    probability_matrix = (
        calculate_error_probabilities(
            phonemes,
            sub_counts,
            source_error_totals,
        )
    )

    (
        target_error_counts,
        background_probabilities,
        total_substitution_errors,
    ) = calculate_background_error_distribution(
        phonemes,
        sub_counts,
    )

    lift_matrix = calculate_lift(
        phonemes,
        sub_counts,
        probability_matrix,
        background_probabilities,
    )

    report = build_report(
        phonemes,
        sub_counts,
        pair_song_counts,
        source_error_totals,
        probability_matrix,
        target_error_counts,
        background_probabilities,
        total_substitution_errors,
        lift_matrix,
        accepted_units,
    )

    print(report)

    if SAVE_TXT:
        OUTPUT_TXT.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        OUTPUT_TXT.write_text(
            report,
            encoding="utf-8",
        )

        print(
            f"\nReport saved: {OUTPUT_TXT}"
        )


if __name__ == "__main__":
    main()