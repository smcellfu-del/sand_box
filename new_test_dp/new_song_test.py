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





#這裡的目標是把歌曲資料處理成csv檔案 
# tar 是 lyrics 的 羅馬拼音 # obs 是 whisper 的 羅馬拼音
#然後這個csv 應該是要一直蒐集資料的 就是說 我會一直丟資料近來 前面的資料不能被蓋掉
#除非這個csv太大了 但目前先不考慮這個問題 
#傳進align_single_song 處理好的資料 然後應該也需要用到 build_alignment_blocks
#csv
#tar obs stat line line_id line_score song song_id song_score 
import csv
import os
def build_matrix_data_frame(song_id, song_name, align_result):
    if not align_result:
        return []
    
    song_score = align_result["stats"]["score"]
    blocks = align_result["blocks"]

    rows = []

    # 遍歷每一個 Segment (Block)
    for block in blocks:
        l_id, w_id = block["key"]
        b_l = block["lyrics"]
        b_w = block["whisper"]

        # 1. 計算這個 Segment (Line) 的分數
        m_cnt = sum(1 for l, w in zip(b_l, b_w) if l == w and l != "-")
        x_cnt = sum(1 for l, w in zip(b_l, b_w) if l != w and l != "-" and w != "-")
        g_cnt = sum(1 for l, w in zip(b_l, b_w) if l == "-" or w == "-")
        seg_total = m_cnt + x_cnt + g_cnt
        line_score = (m_cnt / seg_total * 100) if seg_total else 0.0
        
        # 處理 None 的情況 (有時候一整段都是 Gap)
        l_label = f"L{l_id}" if l_id is not None else "L_NONE"
        w_label = f"W{w_id}" if w_id is not None else "W_NONE"
        line_id_str = f"{l_label}_{w_label}"
        
        # 2. 將這個 Segment 裡面的每一個 Token 對齊結果轉換成 Row
        for tar, obs in zip(b_l, b_w):
            # 判斷狀態 (stat)
            if tar == obs and tar != "-":
                stat = "match"
            elif tar == "-":
                stat = "gap_obs"   # Lyrics是空缺，代表 Whisper 多辨識了(贅字)
            elif obs == "-":
                stat = "gap_tar"   # Whisper是空缺，代表 Whisper 漏辨識了(漏字)
            else:
                stat = "miss"      # 兩者都有，但不一樣
            
            # 建立該筆資料
            row = {
                "song_id": song_id,             # 從參數直接接過來
                "song": song_name,
                "song_score": round(song_score, 2),
                "line_id": line_id_str,
                "line_score": round(line_score, 2),
                "tar": tar,
                "obs": obs,
                "stat": stat
            }
            rows.append(row)
            
    return rows


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


import csv
import os

def save_to_csv(rows, csv_path="alignment_database.csv"):
    if not rows:
        return
        
    # 定義 CSV 的欄位名稱
    fieldnames = ["song_id", "song", "song_score", "line_id", "line_score", "tar", "obs", "stat"]
    
    # 判斷檔案是否已存在且有內容
    file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
    
    # 使用 'a' (append) 模式，資料會一直疊加在檔案最後面
    with open(csv_path, 'a', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        # 如果檔案是空的，第一步先寫入表頭 (欄位名稱)
        if not file_exists:
            writer.writeheader()
            
        # 接著寫入這首歌所有的 tokens 資料
        writer.writerows(rows)

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

def align_and_save_all():
    # 1. 讀取所有歌詞
    # 回傳的是 Dictionary: {"正規化歌名": "歌詞原文"}
    lyrics_dict = load_lyrics()
    
    # 2. 抓出 Whisper 資料夾底下所有的 .json 檔案
    whisper_files = sorted(WHISPER_PATH.glob("*.json"))
    
    # 3. 使用 enumerate 自動產生 song_id (從 1 開始遞增)
    for song_id, whisper_path in enumerate(whisper_files, start=1):
        
        # 取得不含副檔名的檔案名稱 (例如: "優しい彗星.json" -> "優しい彗星")
        song_name = whisper_path.stem 
        
        # 將檔名轉成小寫與去空白 (對應你在 load_lyrics 裡的 title_key 邏輯)
        normalized_name = title_key(song_name)
        
        # 判斷這首 Whisper 的歌，有沒有在我們的 Lyrics 字典裡
        if normalized_name in lyrics_dict:
            # 兩邊都有！把原始文字與列表抓出來
            lyrics_raw_text = lyrics_dict[normalized_name]
            whisper_raw_list = load_whisper(whisper_path)
            
            # 開始跑 DP 對齊
            align_result = align_single_song(lyrics_raw_text, whisper_raw_list)
            
            if align_result:
                # 轉成 CSV 的行資料
                rows = build_matrix_data_frame(
                    song_id=song_id, 
                    song_name=song_name, 
                    align_result=align_result
                )
                
                # 存入 CSV (你寫好的 save_to_csv 會自動判斷要不要加表頭，且採用 append)
                save_to_csv(rows)
                print(f"[{song_id}] {song_name} 處理並儲存完畢！寫入 {len(rows)} 筆 Tokens。")
        else:
            print(f"[警告] 找不到 {song_name} 的歌詞，跳過處理。")

# 執行主程式
if __name__ == "__main__":
    align_and_save_all()

def main():
    run_alignment_pipeline(mode="summary")


def main2():
    run_alignment_pipeline(mode="inspect")


    # main()  # 統計模式



    # python -m sandbox.new_test_dp.new_song_test
