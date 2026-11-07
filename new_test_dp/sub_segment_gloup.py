
import csv
import math
import json
from collections import defaultdict
from pathlib import Path

# ==========================================
# 1. 讀取與階層化資料
# ==========================================
def load_and_parse_csv(filepath):
    """
    讀取扁平的 CSV 資料，並轉換為 歌曲 > 段落 > Match/Miss 的階層結構。
    """
    parsed_data = {}
    
    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            song_name = row["song"]
            song_score = float(row["song_score"])
            line_id = row["line_id"]
            line_score = float(row["line_score"])
            tar = row["tar"]
            obs = row["obs"]
            stat = row["stat"]

            if song_name not in parsed_data:
                parsed_data[song_name] = {
                    "song_score": song_score,
                    "segments": {}
                }
                
            song_segments = parsed_data[song_name]["segments"]

            if line_id not in song_segments:
                song_segments[line_id] = {
                    "line_score": line_score,
                    "misses": [],
                    "match": [],
                    "total_tokens": 0
                }
            
            # 統計 Token
            if stat == "miss":
                song_segments[line_id]["misses"].append((tar, obs))
                song_segments[line_id]["total_tokens"] += 1
            elif stat == "match":
                song_segments[line_id]["match"].append((tar, obs))
                song_segments[line_id]["total_tokens"] += 1
            elif stat.startswith("gap"):
                # 將 Gap 也納入段落長度計算 (視為背景雜訊的一部分)
                song_segments[line_id]["total_tokens"] += 1

    return parsed_data


# ==========================================
# 2. Segment 多重分群
# ==========================================
def cluster_segments(parsed_data, song_threshold=85.0):
    """
    過濾低分歌曲，並將剩餘歌曲的段落依照分數裝入對應的多個群組箱子中。
    """
    # 定義所有測試區間
    target_groups = [
        "100_90", "89_80", "79_70", "69_60", "59_40", "39_0",
        "100_80", "100_70", "100_60", "100_40", 
        "90_70", "90_60", "90_40", 
        "80_70", "80_60", "80_40"
    ]
    
    clusters = {
        name: {"misses": [], "match": [], "total_tokens": 0} 
        for name in target_groups
    }

    for song_name, song_info in parsed_data.items():
        song_score = song_info.get("song_score", 0.0)
        
        if song_score < song_threshold:
            continue
            
        for line_id, segment in song_info.get("segments", {}).items():
            line_score = segment.get("line_score", 0.0)
            misses = segment.get("misses", [])
            match = segment.get("match", [])
            seg_total = segment.get("total_tokens", 0) 
            
            if 90.0 <= line_score <= 100.0:
                target_boxes = ["100_90", "100_80", "100_70", "100_60", "100_40"]
            elif 80.0 <= line_score < 90.0:
                target_boxes = ["89_80", "100_80", "100_70", "100_60", "100_40", "90_70", "90_60", "90_40"]
            elif 70.0 <= line_score < 80.0:
                target_boxes = ["79_70", "100_70", "100_60", "100_40", "90_70", "90_60", "90_40", "80_70", "80_60", "80_40"]
            elif 60.0 <= line_score < 70.0:
                target_boxes = ["69_60", "100_60", "100_40", "90_60", "90_40", "80_60", "80_40"]
            elif 40.0 <= line_score < 60.0:
                target_boxes = ["59_40", "100_40", "90_40", "80_40"]
            else:
                target_boxes = ["39_0"]
                
            for box in target_boxes:
                clusters[box]["misses"].extend(misses)
                clusters[box]["match"].extend(match)
                clusters[box]["total_tokens"] += seg_total

    return clusters


# ==========================================
# 3. 計算並轉換成指定的 JSON 格式
# ==========================================
def build_all_substitution_matrices_to_json_format(clusters, min_occurrence=2):
    """
    為每個群組計算 Match 與 Miss 的 Substitution Matrix，
    並轉成指定的 List of Dicts JSON 格式。
    """
    json_matrices = {}

    for cluster_name, cluster_data in clusters.items():
        # 【關鍵改動】：將 match 和 misses 合併，一起計算機率與打分
        all_pairs = cluster_data.get("misses", []) + cluster_data.get("match", [])
        total_tokens = cluster_data.get("total_tokens", 0)
        
        if total_tokens == 0 or not all_pairs:
            json_matrices[cluster_name] = []
            continue
            
        pair_counts = defaultdict(lambda: defaultdict(int))
        tar_freq = defaultdict(int)
        obs_freq = defaultdict(int)
        
        # 統計字元與配對頻率
        for tar, obs in all_pairs:
            pair_counts[tar][obs] += 1
            tar_freq[tar] += 1
            obs_freq[obs] += 1
            
        total_pairs_count = sum(count for obs_dict in pair_counts.values() for count in obs_dict.values())
        
        cluster_result_list = []
        
        for tar, obs_dict in pair_counts.items():
            for obs, count in obs_dict.items():
                
                # 若出現次數達標才採納 (包含 Match 和 Miss)
                if count >= min_occurrence:
                    # A. 觀測機率 (q_ij)
                    q_ij = count / total_pairs_count if total_pairs_count > 0 else 0
                    
                    # B. 背景機率 (p_i, p_j) - 加入 Laplace 平滑
                    p_i = (tar_freq.get(tar, 0) + 1) / (total_tokens + 1)
                    p_j = (obs_freq.get(obs, 0) + 1) / (total_tokens + 1)
                    
                    expected_prob = p_i * p_j
                    
                    # C. 算分
                    if expected_prob > 0 and q_ij > 0:
                        score = math.log2(q_ij / expected_prob)
                    else:
                        score = -1.0
                        
                    # D. 組裝成你要的格式 (無論大於小於 0 都先記下來)
                    cluster_result_list.append({
                        "tar": tar,
                        "obs": obs,
                        "score": round(score, 3)
                    })
                    
        # 按照分數高低排序，讓 JSON 比較好看
        cluster_result_list.sort(key=lambda x: x["score"], reverse=True)
        json_matrices[cluster_name] = cluster_result_list
        
    return json_matrices


# ==========================================
# 執行區
# ==========================================
if __name__ == "__main__":
    # 1. 設定路徑
    csv_filepath = r"sandbox\new_test_dp\data\alignment_database.csv"
    output_json_path = r"sandbox\new_test_dp\data\substitution_matrices.json"
    
    # 若有自訂 log 模組，可依需求在此加上 with lg.Log(...):
    print("1. 正在讀取並解析 CSV...")
    parsed_data = load_and_parse_csv(csv_filepath)
    
    print("2. 執行段落多重分群投放 (門檻: 歌曲 Score >= 85.0)...")
    clusters = cluster_segments(parsed_data, song_threshold=85.0)
    
    print("3. 計算包含 Match 與 Miss 的 Log-Odds 矩陣...")
    json_formatted_matrices = build_all_substitution_matrices_to_json_format(clusters, min_occurrence=2)
    
    # 4. 將結果儲存為 JSON 檔案
    # 確保資料夾存在
    Path(output_json_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_json_path, "w", encoding="utf-8") as f:
        # indent=4 讓 JSON 排版漂亮易讀，ensure_ascii=False 確保印出日文字元而不是編碼
        json.dump(json_formatted_matrices, f, indent=4, ensure_ascii=False)
        
    print(f"4. 矩陣 JSON 已成功匯出至: {output_json_path}")
    
    # --- (可選) 稍微印出幾個高分群組的前幾筆確認格式 ---
    test_clusters = ["100_90", "89_80", "79_70", "69_60", "59_40", "39_0",
            "100_80", "100_70", "100_60", "100_40", 
            "90_70", "90_60", "90_40", 
            "80_70", "80_60", "80_40"]
    for cluster_name in test_clusters:
        matrix_list = json_formatted_matrices.get(cluster_name, [])
        print(f"\n=== {cluster_name} (總共 {len(matrix_list)} 筆) ===")
        for item in matrix_list[:5]: # 只印前 5 筆 Match/Miss
            print(f"  {item}")
# python -m sandbox.new_test_dp.sub_segment_gloup