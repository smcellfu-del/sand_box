import json
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from sandbox.new_test_dp.file_process import jp_tool as jp
from sandbox.new_test_dp import base_algorithm as ba

WHISPER_PATH = Path(r"G:\我的雲端硬碟\100_song\whisper_json")
LYRICS_PATH = Path(
    r"C:\Users\kniou\Documents\project_in_1141\fianl\backend\web_crawler\lyrics_output.json"
)
OUTPUT_LOG_PATH = Path(__file__).resolve().parent / "file_process" / "log" / "ai_compact_alignment.log"

MATCH = 1.0
MISMATCH = -1.0
GAP = -2.0
SCORE_THRESHOLD = 80.0  # 過濾門檻，僅輸出 80 分以上歌曲

MULTI = sorted(
    (
        "tch", "sh", "ch", "ts", "ky", "gy",
        "ny", "hy", "by", "py", "my", "ry",
        "dy", "ty", "jy"
    ),
    key=len,
    reverse=True
)
CONSONANTS = set("bcdfghjklmnpqrstvwxyz")


def title_key(text):
    return "".join(unicodedata.normalize("NFKC", text).split()).casefold()


def load_lyrics():
    data = json.loads(LYRICS_PATH.read_text(encoding="utf-8-sig"))
    return {
        title_key(row["Song_Name"]): row["Lyrics"]
        for row in data
        if row.get("Song_Name")
        and row.get("Lyrics")
        and not str(row["Lyrics"]).strip().startswith(("http://", "https://"))
    }


def load_whisper(path):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        data = data.get("segments", [])
    return [
        item.get("line") or item.get("light") or item.get("text") or ""
        for item in data
    ]


def split_lines(lines):
    return [line.strip() for line in lines if line and line.strip()]


def tokenize(roma):
    result = []
    i = 0
    while i < len(roma):
        if roma.startswith("tch", i):
            token, width = "Q", 1
        elif (
            i + 1 < len(roma)
            and roma[i] == roma[i + 1]
            and roma[i] in CONSONANTS
            and roma[i] != "n"
        ):
            token, width = "Q", 1
        else:
            token = next((s for s in MULTI if roma.startswith(s, i)), roma[i])
            width = len(token)
        result.append(token)
        i += width
    return result


def reading_to_tokens(reading):
    has_sokuon = reading.endswith(("っ", "ッ"))
    if has_sokuon:
        reading = reading[:-1]
    roma = jp.to_romaji(reading)
    if has_sokuon:
        roma += "Q"
    return tokenize(roma)


def process_lines(lines):
    tokens = []
    for line in lines:
        parts = jp.analyze_japanese_phonetics(line, mode="tokens")
        readings = [part["hira"] for part in parts if part.get("hira")]
        tokens.extend(reading_to_tokens(reading) for reading in readings)
    return [token for group in tokens for token in group]


def build_segments(lines):
    segments = []
    all_tokens = []
    token_segment_ids = []
    for i, line in enumerate(lines):
        tokens = process_lines([line])
        segments.append(tokens)
        all_tokens.extend(tokens)
        token_segment_ids.extend([i] * len(tokens))
    return segments, all_tokens, token_segment_ids


def export_ai_friendly_log():
    OUTPUT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lyrics_songs = load_lyrics()

    with open(OUTPUT_LOG_PATH, "w", encoding="utf-8") as f:
        # 1. 寫入 AI 專用閱讀引導
        f.write("# [AI PARSER GUIDE]\n")
        f.write("# FORMAT OVERVIEW:\n")
        f.write("# @@ SONG: <name> | SCORE: <score>% | MATCH: <m> | MISS: <x> | GAP: <g>\n")
        f.write("#   - SEG_<idx> (L:<lyric_id>, W:<whisper_id>): SCORE=<score>% | M=<m> X=<x> G=<g>\n")
        f.write("#     [Non-100% Segments Only]:\n")
        f.write("#     L_TOK: <tokens separated by space>\n")
        f.write("#     W_TOK: <tokens separated by space>\n")
        f.write("#   - MISS_DETAILS: <lyric_tok>-><whisper_tok> | COUNT: <n> | AT_SEGS: [L<id>_W<id>, ...]\n")
        f.write("# --------------------------------------------------------------------\n\n")

        for whisper_path in sorted(WHISPER_PATH.glob("*.json")):
            song_name = whisper_path.stem
            lyrics_raw = lyrics_songs.get(title_key(song_name))
            if not lyrics_raw:
                continue

            lyrics_lines = split_lines(lyrics_raw.splitlines())
            whisper_lines = split_lines(load_whisper(whisper_path))

            _, lyrics_tokens, lyrics_ids = build_segments(lyrics_lines)
            _, whisper_tokens, whisper_ids = build_segments(whisper_lines)

            if not lyrics_tokens or not whisper_tokens:
                continue

            aligned_l, aligned_w, _ = ba.needleman_wunsch(
                lyrics_tokens, whisper_tokens, match=MATCH, mismatch=MISMATCH, gap=GAP
            )

            # 統計全曲數據與分塊
            blocks = []
            li = 0
            wi = 0
            current_block = None

            for l, w in zip(aligned_l, aligned_w):
                l_id = lyrics_ids[li] if l != "-" else None
                w_id = whisper_ids[wi] if w != "-" else None
                if l != "-":
                    li += 1
                if w != "-":
                    wi += 1

                key = (l_id, w_id)
                if current_block is None or current_block["key"] != key:
                    current_block = {"key": key, "l": [], "w": []}
                    blocks.append(current_block)

                current_block["l"].append(l)
                current_block["w"].append(w)

            total_m = sum(1 for l, w in zip(aligned_l, aligned_w) if l == w and l != "-")
            total_g = sum(1 for l, w in zip(aligned_l, aligned_w) if l == "-" or w == "-")
            total_x = sum(1 for l, w in zip(aligned_l, aligned_w) if l != "-" and w != "-" and l != w)
            total = total_m + total_x + total_g
            score = (total_m / total * 100) if total else 0.0

            # 依門檻過濾
            if score < SCORE_THRESHOLD:
                continue

            f.write(f"@@ SONG: {song_name} | SCORE: {score:.2f}% | MATCH: {total_m} | MISS: {total_x} | GAP: {total_g}\n")

            miss_locations = defaultdict(list)
            miss_counter = Counter()

            # 逐段輸出
            for idx, block in enumerate(blocks, start=1):
                l_id, w_id = block["key"]
                b_l = block["l"]
                b_w = block["w"]

                m_cnt = sum(1 for l, w in zip(b_l, b_w) if l == w and l != "-")
                g_cnt = sum(1 for l, w in zip(b_l, b_w) if l == "-" or w == "-")
                x_cnt = sum(1 for l, w in zip(b_l, b_w) if l != "-" and w != "-" and l != w)
                seg_total = m_cnt + g_cnt + x_cnt
                seg_score = (m_cnt / seg_total * 100) if seg_total else 0.0

                l_lbl = f"L{l_id + 1}" if l_id is not None else "L_NONE"
                w_lbl = f"W{w_id + 1}" if w_id is not None else "W_NONE"
                seg_tag = f"{l_lbl}_{w_lbl}"

                # 收集該 Segment 內的 Miss 詳情
                for l, w in zip(b_l, b_w):
                    if l != "-" and w != "-" and l != w:
                        pair = f"{l}->{w}"
                        miss_counter[pair] += 1
                        miss_locations[pair].append(seg_tag)

                # 寫入 Segment 精簡摘要
                f.write(f"  SEG_{idx:03d} ({seg_tag}): SCORE={seg_score:.1f}% | M={m_cnt} X={x_cnt} G={g_cnt}\n")

                # 若不是 100% 匹配，才印出 Token 供追蹤（大幅節省體積）
                if seg_score < 100.0:
                    f.write(f"    L_TOK: {' '.join(b_l)}\n")
                    f.write(f"    W_TOK: {' '.join(b_w)}\n")

            # 歌曲末端：匯總該曲的 Miss 及所屬 Segment
            f.write("  [MISS_DETAILS]\n")
            if not miss_counter:
                f.write("    NONE\n")
            else:
                for pair, count in miss_counter.most_common():
                    locs = sorted(list(set(miss_locations[pair])))
                    f.write(f"    {pair:<10} | COUNT: {count:<3} | AT_SEGS: {locs}\n")

            f.write("\n" + "=" * 60 + "\n\n")

    print(f"Log generated successfully: {OUTPUT_LOG_PATH}")


if __name__ == "__main__":
    export_ai_friendly_log()


    #python sandbox.new_test_dp.for_ai_log