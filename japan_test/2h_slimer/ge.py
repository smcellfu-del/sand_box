import json
from collections import defaultdict
from pathlib import Path


BASE_PATH = Path("sandbox/japan_test/2h_slimer/debug-4/_phoneme_dataset")
INPUT_FILE = BASE_PATH / "reviewed_error_units.json"

MIN_PAIR_COUNT = 2
MIN_SONG_COUNT = 2
MAX_EXAMPLES_PER_PAIR = 4

INCLUDE_VOWELS = False
INCLUDE_Q = False

VOWELS = {"a", "i", "u", "e", "o"}


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


def normalize_lines(lines):
    if isinstance(lines, list):
        return " / ".join(str(line) for line in lines)

    return str(lines or "")


def collect_pairs(items):
    pair_data = defaultdict(
        lambda: {
            "count": 0,
            "songs": set(),
            "examples": [],
        }
    )

    for item in items:
        review = item.get("review", {})

        if not review.get("use_for_matrix", False):
            continue

        song = item.get("song", "UNKNOWN")
        l_line = normalize_lines(item.get("l_line", ""))
        w_line = normalize_lines(item.get("w_line", ""))

        substitutions = item.get("substitutions", [])

        if not substitutions:
            substitutions = [
                {
                    "l": row.get("l"),
                    "w": row.get("w"),
                }
                for row in item.get("alignment", [])
                if row.get("op") == "SUB"
            ]

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
            pair_data[key]["count"] += 1
            pair_data[key]["songs"].add(song)

            example = {
                "song": song,
                "lyrics": l_line,
                "asr": w_line,
            }

            if example not in pair_data[key]["examples"]:
                pair_data[key]["examples"].append(example)

    return pair_data


def print_report(pair_data):
    selected = []

    for pair, data in pair_data.items():
        song_count = len(data["songs"])

        if data["count"] < MIN_PAIR_COUNT:
            continue

        if song_count < MIN_SONG_COUNT:
            continue

        selected.append((pair, data))

    selected.sort(
        key=lambda item: (
            -len(item[1]["songs"]),
            -item[1]["count"],
            item[0][0],
            item[0][1],
        )
    )

    print("=" * 90)
    print("REPEATED SUBSTITUTION EXAMPLES FOR REPORT")
    print("=" * 90)
    print(
        f"Condition: count >= {MIN_PAIR_COUNT}, "
        f"song_count >= {MIN_SONG_COUNT}"
    )

    if not selected:
        print("\n沒有符合條件的 substitution。")
        return

    for (lyrics_token, asr_token), data in selected:
        print("\n" + "=" * 90)
        print(
            f"{lyrics_token} -> {asr_token} | "
            f"count={data['count']} | "
            f"songs={len(data['songs'])}"
        )
        print("=" * 90)

        shown_songs = set()
        shown_count = 0

        for example in data["examples"]:
            if example["song"] in shown_songs:
                continue

            shown_songs.add(example["song"])
            shown_count += 1

            print(f"\n[{shown_count}] Song   : {example['song']}")
            print(f"    Lyrics : {example['lyrics']}")
            print(f"    ASR    : {example['asr']}")

            if shown_count >= MAX_EXAMPLES_PER_PAIR:
                break


def main():
    items = load_json(INPUT_FILE)
    pair_data = collect_pairs(items)
    print_report(pair_data)


if __name__ == "__main__":
    main()