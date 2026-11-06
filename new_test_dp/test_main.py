from __future__ import annotations

import io
import json
import os
import re
from collections import Counter
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path


def test_main():
    """原本第一階段：全曲 NW 對齊，輸出 TXT 與原始 JSON。"""
    # 第一階段需要的模組；執行第二階段時不需要重新計算 NW。
    from sandbox.new_test_dp.file_process import open_file as of
    from sandbox.new_test_dp import base_algorithm as ba
    from sandbox.new_test_dp.file_process import export_alignment_json as ea

    folders = [
        "ヨルシカ_八月、某、月明かり", "ヨルシカ_又三郎", "ヨルシカ_千鳥",
        "ヨルシカ_五月は花緑青の窓辺から", "ヨルシカ_左右盲", "ヨルシカ_忘れてください", "ヨルシカ_夜行",
        "ヨルシカ_思想犯", "ヨルシカ_春泥棒", "ヨルシカ_春ひさぎ", "ヨルシカ_昼鳶", "ヨルシカ_斜陽",
        "ヨルシカ_嘘月", "ヨルシカ_あの夏に咲け", "ヨルシカ_あの夏に咲け copy", "ヨルシカ_あぶく", "ヨルシカ_アポリア(", "ヨルシカ_アルジャーノン",
        "ヨルシカ_だから僕は音楽を辞めた", "ヨルシカ_ただ君に晴れ", "ヨルシカ_チノカテ", "ヨルシカ_ノーチラス", "ヨルシカ_ヒッチコック",
        "ヨルシカ_ブレーメン", "ヨルシカ_へび", "ヨルシカ_ルバート",
    ]

    # ================= 第一階段參數設定區 =================
    # True: 檔名包含時分秒；False: 只有日期，當天重跑會覆蓋第一階段輸出。
    INCLUDE_TIME_PRECISION = False
    MATCH = 1
    MISMATCH = -1
    GAP = -2

    txt_log_dir = r"sandbox\new_test_dp\file_process\log\first_test_alg_needleman"
    json_log_dir = r"sandbox\new_test_dp\file_process\json_logs"

    os.makedirs(txt_log_dir, exist_ok=True)
    os.makedirs(json_log_dir, exist_ok=True)
    # ========================================================

    for folder in folders:
        test_file = fr"sandbox\new_test_dp\data\debug-4\{folder}\lyrics_roma.json"
        test_file2 = fr"sandbox\new_test_dp\data\debug-4\{folder}\whisper_roma.json"
        try:
            r1 = of.process_file(test_file)
            r2 = of.process_file(test_file2)
        except FileNotFoundError:
            print(f"找不到檔案，跳過: {folder}")
            continue

        lyrics_romaji = r1["full_romaji"]
        whisper_romaji = r2["full_romaji"]
        a_l, a_w, s = ba.needleman_wunsch(
            lyrics_romaji, whisper_romaji,
            match=MATCH, mismatch=MISMATCH, gap=GAP,
        )
        print(f"[{folder}] 全域對齊總分數: {s}")

        if INCLUDE_TIME_PRECISION:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d")

        safe_folder_name = folder.replace("(", "_").replace(")", "_")
        base_filename = f"{safe_folder_name}_{timestamp}"

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            ba.print_lyrics_driven_alignment_with_whisper_mapping(
                a_l, r1["boundaries"], a_w, r2["boundaries"], width=40,
            )
        txt_output = buffer.getvalue()
        txt_path = os.path.join(txt_log_dir, f"{base_filename}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(txt_output)

        json_output_data = ea.generate_alignment_json(
            folder_name=folder,
            aligned_lyrics=a_l,
            lyrics_boundaries=r1["boundaries"],
            aligned_whisper=a_w,
            whisper_boundaries=r2["boundaries"],
            match=MATCH,
            mismatch=MISMATCH,
            gap=GAP,
        )
        json_path = os.path.join(json_log_dir, f"{base_filename}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_output_data, f, ensure_ascii=False, indent=2)

        print(f"   -> TXT 已存至: {txt_path}")
        print(f"   -> JSON 已存至: {json_path}\n" + "-" * 40)


# ================= 第二階段設定區（直接在程式內修改） =================
# 這裡是第一階段 JSON 的來源資料夾
STAGE2_INPUT_DIR = r"sandbox\new_test_dp\file_process\json_logs\first_test_alg_needleman"

# 這裡是你自行指定的第二階段 JSON 輸出資料夾
STAGE2_OUTPUT_DIR = r"sandbox\new_test_dp\file_process\json_logs\analysis_reports"

# False: YYYY-MM-DD_歌名_analysis.json（同日同歌重跑會更新同一檔）
# True:  YYYY-MM-DD_HH-MM-SS_歌名_analysis.json（保留每次實驗的版本）
STAGE2_INCLUDE_TIME_PRECISION = False

# True：只處理每首歌「最後修改」的第一階段 JSON。
# 避免 json_logs 累積多次相同歌曲的舊版本後，一次跑出重複報告。
STAGE2_LATEST_ONLY_PER_SONG = True

# True：先執行原本 test_main() 再分析；False：只分析既有第一階段 JSON。
RUN_TEST_MAIN = False
# =======================================================================

VALID_REVIEW_STATUSES = {"unreviewed", "accepted", "rejected", "uncertain"}
GROUP_DESCRIPTIONS = {
    "G1": "100 分（完全一致區）",
    "G2": "80 <= Q < 100（高相似度區）",
    "G3": "60 <= Q < 80（中低相似度區）",
    "G4": "Q < 60（低相似度區）",
}


def levenshtein_distance(a: str, b: str) -> int:
    """標準 Levenshtein 距離；只保留一列 DP，節省記憶體。"""
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            current.append(min(
                previous[j] + 1,                  # 刪除
                current[j - 1] + 1,               # 插入
                previous[j - 1] + (char_a != char_b),  # 替換
            ))
        previous = current
    return previous[-1]


def classify_similarity(reference: str, whisper: str, score_raw: float) -> str:
    """使用原始精度分組，避免 99.996 因 round 變成假 100。"""
    if reference == whisper and reference:
        return "G1"
    if score_raw >= 80:
        return "G2"
    if score_raw >= 60:
        return "G3"
    return "G4"


def safe_song_filename(song_name: str) -> str:
    """清除 Windows 檔名不可使用字元；保留日文歌名。"""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", song_name)
    cleaned = cleaned.replace("(", "_").replace(")", "_")
    return cleaned.strip(" .") or "Unknown"


def review_key(seg: dict) -> tuple:
    """只有歌詞行編號與 NW 配對字串都沒變，才沿用人工審核。"""
    return (seg.get("line_id"), seg.get("lyrics_aligned"), seg.get("whisper_aligned"))


def load_previous_reviews(destination: Path) -> dict:
    """日期模式重跑時，保留同一份分析檔裡的人工標註。"""
    if not destination.exists():
        return {}
    with destination.open("r", encoding="utf-8") as f:
        old_data = json.load(f)

    old_segments = old_data.get("segments", [])
    if not old_segments:
        old_segments = [
            s for group in old_data.get("similarity_groups", {}).values()
            for s in group.get("segments", [])
        ]

    reviews = {}
    for seg in old_segments:
        status = seg.get("review_status", "unreviewed")
        if status in VALID_REVIEW_STATUSES:
            reviews[review_key(seg)] = {
                "review_status": status,
                "review_note": seg.get("review_note", ""),
            }
    return reviews


def extract_phonemes(text: str) -> dict:
    """保留你原本的探索性 sh/ch/ts 等字母群統計（非替換矩陣）。"""
    combinations = {"sh", "ch", "ts", "ky", "gy", "ny", "hy", "my", "ry", "py", "by"}
    text = text.replace("-", "")
    phonemes = []
    i = 0
    while i < len(text):
        if i + 1 < len(text) and text[i:i + 2] in combinations:
            phonemes.append(text[i:i + 2])
            i += 2
        else:
            phonemes.append(text[i])
            i += 1
    return dict(Counter(phonemes))


def _collect_sources(input_dir: Path) -> list[tuple[Path, dict]]:
    """讀取所有第一階段 JSON；可依歌曲只保留最新版。"""
    items = []
    for source in sorted(input_dir.glob("*.json")):
        try:
            with source.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or not isinstance(data.get("segments"), list):
                print(f"[跳過] 不是第一階段格式: {source.name}")
                continue
            items.append((source, data))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[跳過] 無法讀取 {source.name}: {exc}")

    if not STAGE2_LATEST_ONLY_PER_SONG:
        return items

    latest = {}
    for source, data in items:
        song = data.get("song_name") or source.stem
        if not isinstance(song, str):
            song = str(song)
        previous = latest.get(song)
        if previous is None or (source.stat().st_mtime_ns, source.name) > (
            previous[0].stat().st_mtime_ns, previous[0].name
        ):
            latest[song] = (source, data)
    return sorted(latest.values(), key=lambda item: str(item[0]))


def _output_path(output_dir: Path, song_name: str, run_time: datetime) -> Path:
    """檔名：時間＋歌名；秒數模式遇到同秒重名會自動加流水號。"""
    if STAGE2_INCLUDE_TIME_PRECISION:
        stamp = run_time.strftime("%Y-%m-%d_%H-%M-%S")
    else:
        stamp = run_time.strftime("%Y-%m-%d")

    base_name = f"{stamp}_{safe_song_filename(song_name)}_analysis"
    destination = output_dir / f"{base_name}.json"
    if STAGE2_INCLUDE_TIME_PRECISION:
        index = 1
        while destination.exists():
            destination = output_dir / f"{base_name}_{index:02d}.json"
            index += 1
    return destination


def analyze_songs_and_export() -> None:
    """第二階段：計算逐句分數、G1～G4 分組並輸出可人工標註的 JSON。"""
    input_dir = Path(STAGE2_INPUT_DIR)
    output_dir = Path(STAGE2_OUTPUT_DIR)

    if not input_dir.is_dir():
        print(f"[錯誤] 第一階段 JSON 目錄不存在: {input_dir}")
        return
    if input_dir.resolve() == output_dir.resolve():
        print("[錯誤] 輸入與輸出資料夾不能相同，以免覆蓋原始 NW JSON")
        return

    sources = _collect_sources(input_dir)
    if not sources:
        print(f"沒有可分析的第一階段 JSON: {input_dir}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    run_time = datetime.now(timezone(timedelta(hours=8)))  # 台灣時間，同批使用同一時間戳記

    print("=" * 65)
    print(f"第二階段開始：{len(sources)} 首歌曲")
    print(f"讀取: {input_dir}")
    print(f"輸出: {output_dir}")
    print(f"檔名精度: {'時分秒' if STAGE2_INCLUDE_TIME_PRECISION else '日期'}")
    print("=" * 65)

    success_count = 0
    for source, data in sources:
        song_name = str(data.get("song_name") or source.stem)
        segments = data["segments"]
        destination = _output_path(output_dir, song_name, run_time)

        try:
            old_reviews = load_previous_reviews(destination)
            groups = {
                name: {"description": desc, "segments": []}
                for name, desc in GROUP_DESCRIPTIONS.items()
            }
            scores_raw = []
            reference_full = []
            whisper_full = []
            review_counts = Counter()

            for seg in segments:
                if not isinstance(seg, dict):
                    raise ValueError("segments 中有非物件資料")
                line_id = seg.get("line_id")
                aligned_l = seg.get("lyrics_aligned")
                aligned_w = seg.get("whisper_aligned")
                if not isinstance(aligned_l, str) or not isinstance(aligned_w, str):
                    raise ValueError(f"Line {line_id}: 對齊字串不是文字")
                if len(aligned_l) != len(aligned_w):
                    raise ValueError(f"Line {line_id}: NW 兩側欄位長度不同")

                clean_l = aligned_l.replace("-", "")
                clean_w = aligned_w.replace("-", "")
                if not clean_l and not clean_w:
                    raise ValueError(f"Line {line_id}: 歌詞與語音都為空")

                distance = levenshtein_distance(clean_l, clean_w)
                raw_score = 100.0 * (1 - distance / max(len(clean_l), len(clean_w)))
                group = classify_similarity(clean_l, clean_w, raw_score)
                scores_raw.append(raw_score)
                reference_full.append(clean_l)
                whisper_full.append(clean_w)

                # False（日期檔名）重跑時，只沿用「對齊內容未改變」的舊人工標記。
                old_review = old_reviews.get(review_key(seg), {})
                review_status = old_review.get("review_status", seg.get("review_status", "unreviewed"))
                review_note = old_review.get("review_note", seg.get("review_note", ""))
                if review_status not in VALID_REVIEW_STATUSES:
                    raise ValueError(f"Line {line_id}: 無效的人工標註 {review_status!r}")

                item = {
                    **seg,  # 保留所有第一階段欄位（含 Gap 與 Whisper 區塊）
                    "edit_distance": distance,
                    "reference_length": len(clean_l),
                    "whisper_length": len(clean_w),
                    "similarity": round(raw_score, 2),
                    "score_group": group,
                    "review_status": review_status,
                    "review_note": review_note,
                }
                groups[group]["segments"].append(item)
                review_counts[review_status] += 1

            counts = {name: len(group["segments"]) for name, group in groups.items()}
            avg = round(sum(scores_raw) / len(scores_raw), 2) if scores_raw else None
            lyric_text = "".join(reference_full)
            whisper_text = "".join(whisper_full)

            report = {
                "song_name": song_name,
                "source_file": source.name,
                "generated_at": run_time.isoformat(timespec="seconds"),
                "alignment_params": data.get("alignment_params", {}),
                "summary": {
                    "total_segments": len(segments),
                    "average_similarity": avg,
                    "group_counts": counts,
                    "review_counts": {s: review_counts[s] for s in sorted(VALID_REVIEW_STATUSES)},
                },
                "similarity_groups": groups,
                # 全部 raw Reference 字母次數供 Coverage 使用；非 Substitution 分母。
                "raw_reference_character_counts": dict(sorted(Counter(lyric_text).items())),
                "phoneme_statistics": {
                    "lyrics_phonemes": extract_phonemes(lyric_text),
                    "whisper_phonemes": extract_phonemes(whisper_text),
                },
            }
            # 先寫暫存檔，成功後才替換：中途出錯時保留舊人工標註。
            tmp = destination.with_suffix(".json.tmp")
            try:
                with tmp.open("w", encoding="utf-8") as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)
                os.replace(tmp, destination)
            finally:
                if tmp.exists():
                    tmp.unlink()

            success_count += 1
            print(f"\n🎵 {song_name}  |  平均 {avg} 分  |  {len(segments)} 行")
            print("   " + "  ".join(f"{name}={counts[name]}" for name in ("G1", "G2", "G3", "G4")))
            print(f"   -> {destination}")

        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            print(f"[錯誤] {source.name}: {exc}")
            continue

    print(f"\n完成：{success_count}/{len(sources)} 首歌曲")






from bisect import bisect_right
from datetime import datetime
from pathlib import Path
import json

from sandbox.new_test_dp.file_process import open_file as of
from sandbox.new_test_dp.base_algorithm import semi_global_align_segment


FOLDERS = [
    "ヨルシカ_八月、某、月明かり", "ヨルシカ_又三郎", "ヨルシカ_千鳥",
    "ヨルシカ_五月は花緑青の窓辺から", "ヨルシカ_左右盲", "ヨルシカ_忘れてください", "ヨルシカ_夜行",
    "ヨルシカ_思想犯", "ヨルシカ_春泥棒", "ヨルシカ_春ひさぎ", "ヨルシカ_昼鳶", "ヨルシカ_斜陽",
    "ヨルシカ_嘘月", "ヨルシカ_あの夏に咲け", "ヨルシカ_あの夏に咲け copy", "ヨルシカ_あぶく",
    "ヨルシカ_アポリア(", "ヨルシカ_アルジャーノン", "ヨルシカ_だから僕は音楽を辞めた",
    "ヨルシカ_ただ君に晴れ", "ヨルシカ_チノカテ", "ヨルシカ_ノーチラス", "ヨルシカ_ヒッチコック",
    "ヨルシカ_ブレーメン", "ヨルシカ_へび", "ヨルシカ_ルバート",
]

MATCH = 1
MISMATCH = -1
GAP = -2
INCLUDE_TIME_PRECISION = False
ROOT = Path("sandbox") / "new_test_dp"
DATA_DIR = ROOT / "data" / "debug-4"
TXT_DIR = ROOT / "file_process" / "log" / "local_semi_global"
JSON_DIR = ROOT / "file_process" / "json_logs" / "local_semi_global"


def iter_processed_segments(processed):
    """Yield (1-based segment number, start, end, romaji, source JSON item).

    process_file() emits cumulative EXCLUSIVE character boundaries, e.g.
    full='abcde', boundaries=[2,5] -> ('ab', 'cde').
    """
    full = processed["full_romaji"]
    ends = processed["boundaries"]
    rows = processed["data"]
    if len(ends) != len(rows):
        raise ValueError("boundaries 數量與 JSON row 數量不同")
    if ends and ends[-1] != len(full):
        raise ValueError("最後一個 boundary 必須等於 full_romaji 長度")
    start = 0
    for segment_no, (end, row) in enumerate(zip(ends, rows), start=1):
        if not isinstance(end, int) or end < start or end > len(full):
            raise ValueError(f"segment {segment_no} 的 boundary 不合法: {end}")
        yield segment_no, start, end, full[start:end], row
        start = end


def lyric_line_for_position(lyrics_boundaries, char_pos):
    """1-based Lyrics line containing a 0-based romaji character index."""
    if not lyrics_boundaries:
        return None
    return bisect_right(lyrics_boundaries, char_pos) + 1


def aligned_text_block(aligned_lyrics, aligned_whisper, operations, width=70):
    marks = {"MATCH": "|", "SUB": "x", "INSERT": "+", "DELETE": "-"}
    output = []
    for start in range(0, len(operations), width):
        end = start + width
        output.append("Lyrics : " + aligned_lyrics[start:end])
        output.append("         " + "".join(marks[o] for o in operations[start:end]))
        output.append("Whisper: " + aligned_whisper[start:end])
        output.append("")
    return "\n".join(output)


def align_one_song(folder, lyrics_data, whisper_data):
    lyrics = lyrics_data["full_romaji"]
    lyrics_boundaries = lyrics_data["boundaries"]
    lyric_lines = lyrics_data["data"]
    if not lyrics:
        raise ValueError("Lyrics full_romaji 為空")

    records = []
    blocks = [f"歌曲：{folder}", "方法：Whisper Segment × 全曲 Lyrics (Semi-global DP)",
              f"Score: MATCH={MATCH}, MISMATCH={MISMATCH}, GAP={GAP}", "=" * 90]

    for seg_no, ws, we, whisper, source_row in iter_processed_segments(whisper_data):
        if not whisper:
            blocks.append(f"Segment {seg_no}: 空字串，跳過")
            continue

        a_l, a_w, score, detail = semi_global_align_segment(
            lyrics, whisper, match=MATCH, mismatch=MISMATCH,
            gap=GAP, return_details=True,
        )
        ls, le = detail["lyrics_start"], detail["lyrics_end"]
        if le > ls:
            line_start = lyric_line_for_position(lyrics_boundaries, ls)
            line_end = lyric_line_for_position(lyrics_boundaries, le - 1)
            excerpt = [x.get("line", "") for x in lyric_lines[line_start-1:line_end]]
        else:
            line_start = line_end = None
            excerpt = []

        record = {
            "segment_index": seg_no,
            "whisper_original_line": source_row.get("line", ""),
            "whisper_char_start": ws,
            "whisper_char_end": we,
            "whisper_romaji": whisper,
            "lyrics_char_start": ls,
            "lyrics_char_end": le,
            "lyrics_line_start": line_start,
            "lyrics_line_end": line_end,
            "lyrics_original_lines": excerpt,
            "score": score,
            "normalized_score": detail["normalized_score"],
            "counts": detail["counts"],
            "operations": detail["operations"],
            "aligned_lyrics": a_l,
            "aligned_whisper": a_w,
            "review_status": "UNREVIEWED",
        }
        records.append(record)
        blocks.extend([
            f"\nSegment #{seg_no} | Score={score} | Lyrics chars=[{ls},{le}) | "
            f"Lyrics lines={line_start}-{line_end}",
            f"Whisper 原文：{source_row.get('line', '')}",
            f"Lyrics 候選：{' / '.join(excerpt) if excerpt else '(沒有 Lyrics 字元參與對齊)'}",
            "counts: " + str(detail["counts"]),
            aligned_text_block(a_l, a_w, detail["operations"]),
            "-" * 90,
        ])

    return {"song_id": folder, "method": "semi_global_segment_to_full_lyrics",
            "unit": "romaji_character", "match": MATCH, "mismatch": MISMATCH,
            "gap": GAP, "segments": records}, "\n".join(blocks) + "\n"


def test_local_main(folders=None):
    folders = FOLDERS if folders is None else folders
    TXT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    fmt = "%Y-%m-%d_%H-%M-%S" if INCLUDE_TIME_PRECISION else "%Y-%m-%d"
    stamp = datetime.now().strftime(fmt)

    for folder in folders:
        song_dir = DATA_DIR / folder
        try:
            r1 = of.process_file(str(song_dir / "lyrics_roma.json"))
            r2 = of.process_file(str(song_dir / "whisper_roma.json"))
            result, report = align_one_song(folder, r1, r2)
        except FileNotFoundError:
            print(f"找不到檔案，跳過：{folder}")
            continue
        except (ValueError, KeyError, TypeError) as exc:
            print(f"[{folder}] 資料格式不合法：{exc}")
            continue

        safe_name = folder.replace("(", "_").replace(")", "_")
        base = f"{safe_name}_{stamp}"
        txt_path = TXT_DIR / f"{base}.txt"
        json_path = JSON_DIR / f"{base}.json"
        txt_path.write_text(report, encoding="utf-8")
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[{folder}] 完成 {len(result['segments'])} 個 Whisper Segment")
        print(f"  -> TXT:  {txt_path}")
        print(f"  -> JSON: {json_path}")


if __name__ == "__main__":
    test_local_main()





    


# python -m sandbox.new_test_dp.test_main