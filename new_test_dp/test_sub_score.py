'''
song: Clap Clap
score: 77.586

song: Finder
score: 80.728

song: FIRE GROUND
score: 79.778

song: Get Back To 人生
score: 88.971

song: Lost In My Room
score: 73.253
gap: 115
match: 608
miss: 107


song: New me
score: 82.155
gap: 171
match: 1197
miss: 89
'''




import json
import unicodedata
from pathlib import Path

from sandbox.new_test_dp.file_process import jp_tool as jp
from sandbox.new_test_dp import base_algorithm as ba
from services.other import log as lg
from sandbox.new_test_dp import new_song_test as nst
song_list =[
    "Clap Clap",
    "Finder",
    "FIRE GROUND",
    "Get Back To 人生",
    "Lost In My Room",
    "New me"
]

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


if __name__ == "__main__":
    lyrics_songs = nst.load_lyrics()
    
    for whisper_path in sorted(WHISPER_PATH.glob("*.json")):
        song_name = whisper_path.stem
        
        # 1. 先判斷是否為目標歌曲，節省不必要的處理時間
        if song_name in song_list:
            # 2. 獲取並檢查歌詞
            lyrics_raw = lyrics_songs.get(nst.title_key(song_name))
            if not lyrics_raw:
                print(f"[❌] 歌詞資料缺失: {song_name}")
                continue

            print(f"==================== {song_name} ====================")
            
            # 3. 讀取 Whisper 檔案並執行對齊
            whisper_raw = nst.load_whisper(whisper_path)
            res = nst.align_single_song(lyrics_raw, whisper_raw)
            
            if not res:
                continue
            
            # 4. 直接從回傳的 dictionary 中提取並印出 stats
            stats = res["stats"]
            print(f"score: {stats['score']:.3f}")
            print(f"gap: {stats['gap']}")
            print(f"match: {stats['match']}")
            print(f"miss: {stats['miss']}")