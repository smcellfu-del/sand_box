import json
from sandbox.new_test_dp.file_process import jp_tool as jp

def open_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def process_file(file_path):
    data = open_file(file_path)
    
    romaji_parts = []
    line_boundaries = []
    current_pos = 0
    
    for item in data:
        line_text = item.get("line", "")
        
        # 透過 jp 工具將該行轉為羅馬字
        # separator="" 代表字與字之間不加額外空格，若需要空格可以改成 separator=" "
        roma = jp.analyze_japanese_phonetics(line_text, mode="roma", separator="")
        
        romaji_parts.append(roma)
        
        # 計算這一句結束時，在整串羅馬字中的結束字元位置（index）
        current_pos += len(roma)
        line_boundaries.append(current_pos)
        
    # 組合成一長串的羅馬字序列
    full_romaji = "".join(romaji_parts)
    
    # 依需求回傳結果（包含整串羅馬字、座標陣列，以及原本的資料）
    return {
        "full_romaji": full_romaji,
        "boundaries": line_boundaries,
        "data": data
    }

if __name__ == "__main__":
    # 建議路徑開頭加上 r 避免跳脫字元問題（例如 \n）
    test_file = r"sandbox\new_test_dp\data\debug-4\ヨルシカ_八月、某、月明かり\lyrics_roma.json"
    test_file2 = r"sandbox\new_test_dp\data\debug-4\ヨルシカ_八月、某、月明かり\whisper_roma.json"

    r1 = process_file(test_file)
    r2 = process_file(test_file2)
    
    print("=== r1 full_romaji ===")
    print(r1["full_romaji"])
    print("r1 boundaries:", r1["boundaries"])
    
    print("\n=== r2 full_romaji ===")
    print(r2["full_romaji"])
    print("r2 boundaries:", r2["boundaries"])


    # python -m sandbox.new_test_dp.file_process.open_file