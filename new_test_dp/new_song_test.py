import json
import unicodedata
from pathlib import Path

from sandbox.new_test_dp.file_process import jp_tool as jp
from sandbox.new_test_dp import base_algorithm as ba
from services.other import log as lg


WHISPER_PATH = Path(r"G:\我的雲端硬碟\100_song\whisper_json")
LYRICS_PATH = Path(
    r"C:\Users\kniou\Documents\project_in_1141\fianl\backend\web_crawler\lyrics_output.json"
)

MATCH = 1.0
MISMATCH = -1.0
GAP = -2.0

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


# ==========================================
# 1. 讀取資料
# ==========================================

def title_key(text):
    return "".join(
        unicodedata.normalize("NFKC", text).split()
    ).casefold()


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
    """移除頭尾空白並過濾空句"""
    return [line.strip() for line in lines if line and line.strip()]


# ==========================================
# 2. Romaji -> Token
# ==========================================

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


# ==========================================
# 3. 日文 -> Token & Segment 處理
# ==========================================

def process_lines(lines):
    tokens = []
    for line in lines:
        parts = jp.analyze_japanese_phonetics(line, mode="tokens")
        readings = [part["hira"] for part in parts if part.get("hira")]
        tokens.extend(reading_to_tokens(reading) for reading in readings)
    return [token for group in tokens for token in group]


def build_segments(lines):
    """
    接收切割好的句子列表 (Lyrics: 依換行分; Whisper: 依 JSON 區塊分)
    回傳：
      - segments: 每個段落的 tokens
      - all_tokens: 展平後的所有 tokens
      - token_segment_ids: 標註每個 token 屬於第幾個 segment
    """
    segments = []
    all_tokens = []
    token_segment_ids = []
    for i, line in enumerate(lines):
        tokens = process_lines([line])
        segments.append(tokens)
        all_tokens.extend(tokens)
        token_segment_ids.extend([i] * len(tokens))
    return segments, all_tokens, token_segment_ids


# ==========================================
# 4. 核心對齊管線 (抽出共用)
# ==========================================
def align_single_song(lyrics_raw_text, whisper_raw_list):
    """
    處理單首歌曲的對齊與統計計算
    """
    lyrics_lines = split_lines(lyrics_raw_text.splitlines())
    whisper_lines = split_lines(whisper_raw_list)

    _, lyrics_tokens, lyrics_ids = build_segments(lyrics_lines)
    _, whisper_tokens, whisper_ids = build_segments(whisper_lines)

    if not lyrics_tokens or not whisper_tokens:
        return None

    aligned_l, aligned_w, _ = ba.needleman_wunsch(
        lyrics_tokens,
        whisper_tokens,
        match=MATCH,
        mismatch=MISMATCH,
        gap=GAP
    )

    # 計算統計數據
    match_count = 0
    miss_count = 0
    gap_count = 0
    for l, w in zip(aligned_l, aligned_w):
        if l == "-" or w == "-":
            gap_count += 1
        elif l == w:
            match_count += 1
        else:
            miss_count += 1

    total = match_count + miss_count + gap_count
    score = (match_count / total * 100) if total else 0.0

    stats = {
        "score": score,
        "match": match_count,
        "miss": miss_count,
        "gap": gap_count,
        "total": total
    }

    blocks = build_alignment_blocks(aligned_l, aligned_w, lyrics_ids, whisper_ids)

    return {
        "stats": stats,
        "blocks": blocks,
        "aligned_lyrics": aligned_l,
        "aligned_whisper": aligned_w,
        "lyrics_lines": lyrics_lines,      # 新增：保留切句後的歌詞原句
        "whisper_lines": whisper_lines     # 新增：保留切句後的 Whisper 原句
    }


def build_alignment_blocks(aligned_l, aligned_w, lyric_ids, whisper_ids):
    arr = []
    li = 0
    wi = 0
    current = None

    for l, w in zip(aligned_l, aligned_w):
        l_id = lyric_ids[li] if l != "-" else None
        w_id = whisper_ids[wi] if w != "-" else None

        if l != "-":
            li += 1
        if w != "-":
            wi += 1

        key = (l_id, w_id)
        if current is None or current["key"] != key:
            current = {
                "key": key,
                "lyrics": [],
                "whisper": []
            }
            arr.append(current)

        current["lyrics"].append(l)
        current["whisper"].append(w)

    return arr


# ==========================================
# 5. 輸出排版 (解決不等寬錯位問題)
# ==========================================
def print_alignment_blocks(song_name, blocks, lyrics_lines, whisper_lines):
    print(f"\nsong : {song_name}")
    for block in blocks:
        l_id, w_id = block["key"]
        lyric_label = f"第 {l_id + 1} 句歌詞區塊" if l_id is not None else "無對應歌詞"
        whisper_label = f"whisper {w_id + 1} 區塊" if w_id is not None else "無對應 whisper"

        lyrics = block["lyrics"]
        whisper = block["whisper"]

        # 取得原句文字
        raw_lyric_str = lyrics_lines[l_id] if l_id is not None else "（無）"
        raw_whisper_str = whisper_lines[w_id] if w_id is not None else "（無）"

        # Token 欄位寬度對齊
        formatted_l = []
        formatted_m = []
        formatted_w = []

        for l, w in zip(lyrics, whisper):
            width = max(len(l), len(w), 1)
            formatted_l.append(l.ljust(width))
            formatted_w.append(w.ljust(width))
            marker = "|" if l == w and l != "-" else " "
            formatted_m.append(marker.center(width))

        print(f"\n--- {lyric_label} (對應 {whisper_label}) ---")
        print(f"原句 (Lyrics)  : {raw_lyric_str}")
        print(f"原句 (Whisper) : {raw_whisper_str}")
        print("tokens (lyr)   : " + " ".join(formatted_l))
        print("                 " + " ".join(formatted_m))
        print("tokens (whs)   : " + " ".join(formatted_w))


# ==========================================
# 6. 兩種運行模式
# ==========================================

def run_alignment_pipeline(mode="inspect"):
    """
    mode:
      - 'summary': 僅輸出分數與統計 (原 main)
      - 'inspect': 輸出人工審核對齊圖 (原 main2)
    """
    log_file_name = (
        "needlment_all_song_socre" if mode == "summary" 
        else "needlment_all_song_humen_look"
    )
    log_path = Path(__file__).resolve().parent / "file_process" / "log"

    with lg.Log(log_path, log_file_name):
        lyrics_songs = load_lyrics()

        for whisper_path in sorted(WHISPER_PATH.glob("*.json")):
            song_name = whisper_path.stem
            lyrics_raw = lyrics_songs.get(title_key(song_name))

            if not lyrics_raw:
                continue

            whisper_raw = load_whisper(whisper_path)
            res = align_single_song(lyrics_raw, whisper_raw)

            if not res:
                continue

            stats = res["stats"]

            if mode == "summary":
                print(f"song: {song_name}")
                print(f"score: {stats['score']:.3f}")
                print(f"gap: {stats['gap']}")
                print(f"match: {stats['match']}")
                print(f"miss: {stats['miss']}")
                print("-" * 55)

            elif mode == "inspect":
                print_alignment_blocks(
                    song_name=song_name,
                    blocks=res["blocks"],
                    lyrics_lines=res["lyrics_lines"],
                    whisper_lines=res["whisper_lines"]
                )
                print("\n" + "=" * 70)


def main():
    run_alignment_pipeline(mode="summary")


def main2():
    run_alignment_pipeline(mode="inspect")


# ==========================================
# 7. 執行入口
# ==========================================

if __name__ == "__main__":
    main()
    # main()  # 統計模式



    # python -m sandbox.new_test_dp.new_song_test
