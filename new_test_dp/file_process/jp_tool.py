import re
from sudachipy import Dictionary, SplitMode
import pykakasi
from pykakasi.kanji import Kanwa

tokenizer = Dictionary(dict="full").create()
split_mode = SplitMode.C
kks = pykakasi.kakasi()
kanwa = Kanwa()

SKIP_POS = {"空白", "補助記号", "記号"}

def to_romaji(text: str) -> str:
    """日文 → Hepburn 羅馬字"""
    return "".join(item["hepburn"] for item in kks.convert(text))

def to_hiragana(text: str) -> str:
    """日文 / 片假名 → 平假名"""
    return "".join(item["hira"] for item in kks.convert(text))

def to_katakana(text: str) -> str:
    """日文 / 平假名 → 片假名"""
    return "".join(item["kana"] for item in kks.convert(text))

def romaji_to_vowel(romaji: str) -> str:
    """羅馬字 → 母音序列 (例如: watashi -> aai)"""
    return "".join(char for char in romaji.lower() if char in "aeiou")

# =========================================================
# 一字多音查詢 (利用 pykakasi Kanwa 辭典)
# =========================================================

def get_kanji_readings(char: str) -> list[str]:
    """查詢單一漢字的所有可能讀音 (平假名)"""
    data = kanwa.load(char)
    entries = data.get(char, [])
    return sorted(list({r[0] for r in entries}))

def get_all_readings_with_phonemes(char: str) -> list[dict]:
    """
    取得該漢字的所有候選讀音，並包含羅馬字與音素序列
    用於音素對齊 (DP alignment) 時處理多音字匹配
    """
    readings = get_kanji_readings(char)
    results = []
    for r in readings:
        p = hiragana_to_phonemes(r)
        results.append({
            "reading": r,
            "romaji": to_romaji(r),
            "phonemes": p,
            "phoneme_str": phonemes_to_string(p)
        })
    return results

# =========================================================
# 映射表 (平假名 / 拗音 / 外來語)
# =========================================================

PHONEME_MAP = {
    "あ": ["a"], "い": ["i"], "う": ["u"], "え": ["e"], "お": ["o"],
    "か": ["k", "a"], "き": ["k", "i"], "く": ["k", "u"], "け": ["k", "e"], "こ": ["k", "o"],
    "が": ["g", "a"], "ぎ": ["g", "i"], "ぐ": ["g", "u"], "げ": ["g", "e"], "ご": ["g", "o"],
    "さ": ["s", "a"], "し": ["sh", "i"], "す": ["s", "u"], "せ": ["s", "e"], "そ": ["s", "o"],
    "ざ": ["z", "a"], "じ": ["j", "i"], "ず": ["z", "u"], "ぜ": ["z", "e"], "ぞ": ["z", "o"],
    "た": ["t", "a"], "ち": ["ch", "i"], "つ": ["ts", "u"], "て": ["t", "e"], "と": ["t", "o"],
    "だ": ["d", "a"], "ぢ": ["j", "i"], "づ": ["z", "u"], "で": ["d", "e"], "ど": ["d", "o"],
    "な": ["n", "a"], "に": ["n", "i"], "ぬ": ["n", "u"], "ね": ["n", "e"], "の": ["n", "o"],
    "は": ["h", "a"], "ひ": ["h", "i"], "ふ": ["f", "u"], "へ": ["h", "e"], "ほ": ["h", "o"],
    "ば": ["b", "a"], "び": ["b", "i"], "ぶ": ["b", "u"], "べ": ["b", "e"], "ぼ": ["b", "o"],
    "ぱ": ["p", "a"], "ぴ": ["p", "i"], "ぷ": ["p", "u"], "ぺ": ["p", "e"], "ぽ": ["p", "o"],
    "ま": ["m", "a"], "み": ["m", "i"], "む": ["m", "u"], "め": ["m", "e"], "も": ["m", "o"],
    "や": ["y", "a"], "ゆ": ["y", "u"], "よ": ["y", "o"],
    "ら": ["r", "a"], "り": ["r", "i"], "る": ["r", "u"], "れ": ["r", "e"], "ろ": ["r", "o"],
    "わ": ["w", "a"], "を": ["o"], "ん": ["N"],
}

YOON_MAP = {
    "きゃ": ["k", "y", "a"], "きゅ": ["k", "y", "u"], "きょ": ["k", "y", "o"],
    "ぎゃ": ["g", "y", "a"], "ぎゅ": ["g", "y", "u"], "ぎょ": ["g", "y", "o"],
    "しゃ": ["sh", "a"], "しゅ": ["sh", "u"], "しょ": ["sh", "o"],
    "じゃ": ["j", "a"], "じゅ": ["j", "u"], "じょ": ["j", "o"],
    "ちゃ": ["ch", "a"], "ちゅ": ["ch", "u"], "ちょ": ["ch", "o"],
    "ぢゃ": ["j", "a"], "ぢゅ": ["j", "u"], "ぢょ": ["j", "o"],
    "にゃ": ["n", "y", "a"], "にゅ": ["n", "y", "u"], "にょ": ["n", "y", "o"],
    "ひゃ": ["h", "y", "a"], "ひゅ": ["h", "y", "u"], "ひょ": ["h", "y", "o"],
    "びゃ": ["b", "y", "a"], "びゅ": ["b", "y", "u"], "びょ": ["b", "y", "o"],
    "ぴゃ": ["p", "y", "a"], "ぴゅ": ["p", "y", "u"], "ぴょ": ["p", "y", "o"],
    "みゃ": ["m", "y", "a"], "みゅ": ["m", "y", "u"], "みょ": ["m", "y", "o"],
    "りゃ": ["r", "y", "a"], "りゅ": ["r", "y", "u"], "りょ": ["r", "y", "o"],
}

GAIRAIGO_MAP = {
    "ふぁ": ["f", "a"], "ふぃ": ["f", "i"], "ふぇ": ["f", "e"], "ふぉ": ["f", "o"],
    "うぃ": ["w", "i"], "うぇ": ["w", "e"], "うぉ": ["w", "o"],
    "ゔぁ": ["v", "a"], "ゔぃ": ["v", "i"], "ゔぇ": ["v", "e"], "ゔぉ": ["v", "o"], "ゔ": ["v", "u"],
    "てぃ": ["t", "i"], "でぃ": ["d", "i"], "とぅ": ["t", "u"], "どぅ": ["d", "u"],
    "しぇ": ["sh", "e"], "じぇ": ["j", "e"], "ちぇ": ["ch", "e"],
    "つぁ": ["ts", "a"], "つぃ": ["ts", "i"], "つぇ": ["ts", "e"], "つぉ": ["ts", "o"],
    "いぇ": ["y", "e"], "すぃ": ["s", "i"], "ずぃ": ["z", "i"],
}

# =========================================================
# Hiragana → 音素 / 母音
# =========================================================

def hiragana_to_phonemes(text: str):
    """平假名 → 音素列表 (っ->Q, ん->N, ー->:)"""
    text = to_hiragana(text)
    phonemes = []
    i = 0
    while i < len(text):
        char = text[i]
        if char == "っ":
            phonemes.append("Q")
            i += 1
            continue
        if char == "ー":
            phonemes.append(":")
            i += 1
            continue
        if i + 1 < len(text):
            pair = text[i:i + 2]
            if pair in GAIRAIGO_MAP:
                phonemes.extend(GAIRAIGO_MAP[pair])
                i += 2
                continue
            if pair in YOON_MAP:
                phonemes.extend(YOON_MAP[pair])
                i += 2
                continue
        if char in PHONEME_MAP:
            phonemes.extend(PHONEME_MAP[char])
        else:
            phonemes.append(char)  # 不認識的字元直接保留
        i += 1
    return phonemes

def phonemes_to_string(phonemes):
    """音素列表 → 空格分隔字串"""
    return " ".join(phonemes)

def phonemes_to_vowels(phonemes):
    """從音素中抽出母音"""
    vowels = {"a", "i", "u", "e", "o"}
    return [p for p in phonemes if p in vowels]

def phonemes_to_vowel_string(phonemes):
    """音素 → 母音字串"""
    return "".join(phonemes_to_vowels(phonemes))

# =========================================================
# 音素相似度與比對
# =========================================================

PHONEME_SIMILARITY = {
    # 清音 / 濁音
    ("k", "g"): 0.8, ("g", "k"): 0.8,
    ("s", "z"): 0.8, ("z", "s"): 0.8,
    ("sh", "j"): 0.8, ("j", "sh"): 0.8,
    ("t", "d"): 0.8, ("d", "t"): 0.8,
    ("ch", "j"): 0.8, ("j", "ch"): 0.8,
    ("h", "b"): 0.7, ("b", "h"): 0.7,
    ("h", "p"): 0.7, ("p", "h"): 0.7,
    ("b", "p"): 0.8, ("p", "b"): 0.8,
    # s 系 / r / f / m / n
    ("s", "sh"): 0.7, ("sh", "s"): 0.7,
    ("ts", "s"): 0.7, ("s", "ts"): 0.7,
    ("r", "l"): 0.8, ("l", "r"): 0.8,
    ("f", "h"): 0.7, ("h", "f"): 0.7,
    ("m", "n"): 0.6, ("n", "m"): 0.6,
}

def phoneme_similarity(a: str, b: str) -> float:
    """回傳兩個音素的相似度 (1.0 完全相同, 0.8/0.7 相似, 0.0 不相似)"""
    if a == b:
        return 1.0
    return PHONEME_SIMILARITY.get((a, b), 0.0)

def compare_phonemes(expected, actual):
    """比較正確音素與實際音素"""
    max_len = max(len(expected), len(actual))
    results = []
    for i in range(max_len):
        expected_phoneme = expected[i] if i < len(expected) else None
        actual_phoneme = actual[i] if i < len(actual) else None

        if expected_phoneme is None:
            results.append({"index": i, "expected": None, "actual": actual_phoneme, "status": "extra", "similarity": 0.0})
            continue
        if actual_phoneme is None:
            results.append({"index": i, "expected": expected_phoneme, "actual": None, "status": "missing", "similarity": 0.0})
            continue

        similarity = phoneme_similarity(expected_phoneme, actual_phoneme)
        status = "correct" if similarity == 1.0 else ("similar" if similarity >= 0.7 else "wrong")

        results.append({
            "index": i,
            "expected": expected_phoneme,
            "actual": actual_phoneme,
            "status": status,
            "similarity": similarity,
        })
    return results

# =========================================================
# Sudachi Token 分析器
# =========================================================

def analyze_token_reading(text: str):
    results = []
    token_index = 0
    for m in tokenizer.tokenize(text, split_mode):
        pos_detail = m.part_of_speech()
        if pos_detail[0] in SKIP_POS:
            continue

        token_index += 1
        surface = m.surface()
        reading = m.reading_form() or surface
        hiragana = to_hiragana(reading)
        phonemes = hiragana_to_phonemes(hiragana)

        results.append({
            "index": token_index,
            "surface": surface,
            "reading": reading,
            "hira": hiragana,
            "sudachi_roma": to_romaji(reading),
            "direct_roma": to_romaji(surface),
            "phonemes": phonemes,
            "phoneme_string": phonemes_to_string(phonemes),
            "vowels": phonemes_to_vowels(phonemes),
            "vowel_string": phonemes_to_vowel_string(phonemes),
            "pos": " / ".join(pos_detail),
        })
    return results

def analyze_japanese_phonetics(text: str, mode: str = "tokens", show: bool = False, separator: str = " "):
    phonetic_results = []
    roma_list, vowel_list, kata_list, hira_list, phoneme_list = [], [], [], [], []
    token_index = 0

    if show:
        print(f"\n原始文字：{text}")
        print("=" * 150)

    for m in tokenizer.tokenize(text, split_mode):
        pos_detail = m.part_of_speech()
        if pos_detail[0] in SKIP_POS:
            continue

        token_index += 1
        surface, dict_form = m.surface(), m.dictionary_form()
        reading = m.reading_form() or surface

        katakana = reading
        hiragana = to_hiragana(reading)
        romaji = to_romaji(reading)

        phonemes = hiragana_to_phonemes(hiragana)
        phoneme_string = phonemes_to_string(phonemes)

        vowels = phonemes_to_vowels(phonemes)
        vowel_string = phonemes_to_vowel_string(phonemes)

        token_info = {
            "index": token_index,
            "surface": surface,
            "dict_form": dict_form,
            "reading": reading,
            "kata": katakana,
            "hira": hiragana,
            "romaji": romaji,
            "phonemes": phonemes,
            "phoneme_string": phoneme_string,
            "vowels": vowels,
            "vowel": vowel_string,
            "pos": " / ".join(pos_detail),
            "source_start": m.begin(),
            "source_end": m.end()
        }

        phonetic_results.append(token_info)
        kata_list.append(katakana)
        hira_list.append(hiragana)
        roma_list.append(romaji)
        vowel_list.append(vowel_string)
        phoneme_list.extend(phonemes)

        if show:
            print(
                f"[{token_index}] 表層: {surface:<8} | 辭書形: {dict_form:<8} | "
                f"片假名: {katakana:<12} | 平假名: {hiragana:<12} | 羅馬字: {romaji:<15} | "
                f"音素: {phoneme_string:<25} | 母音: {vowel_string:<10} | 詞性: {token_info['pos']}"
            )

    if show:
        print("-" * 150)

    mode_map = {
        "roma": separator.join(roma_list),
        "vowel": separator.join(vowel_list),
        "kata": separator.join(kata_list),
        "hira": separator.join(hira_list),
        "phoneme": separator.join(phoneme_list),
        "tokens": phonetic_results,
        "all": {
            "text": text,
            "roma": separator.join(roma_list),
            "vowel": separator.join(vowel_list),
            "kata": separator.join(kata_list),
            "hira": separator.join(hira_list),
            "phoneme": separator.join(phoneme_list),
            "tokens": phonetic_results,
        },
    }

    if mode in mode_map:
        return mode_map[mode]
    raise ValueError(f"未知 mode: {mode}，請使用 'roma', 'vowel', 'kata', 'hira', 'phoneme', 'tokens', 'all'")

if __name__ == "__main__":
    text = "母さんが言ってたんだ"
    result = analyze_japanese_phonetics(text, mode="all", show=True)

    print("\n========== 最終結果 ==========\n")
    print("羅馬字：\n", result["roma"])
    print("\n平假名：\n", result["hira"])
    print("\n音素：\n", result["phoneme"])
    print("\n母音：\n", result["vowel"])

    # 1. 基本音素測試
    print("========== 基本音素測試 ==========")
    test_words = [
        "こんにちは",
        "コーヒー",    # 長音
        "きって",      # 促音 Q
        "しんぶん",    # 撥音 N
        "まっちゃ",    # 促音 + 拗音
    ]

    for word in test_words:
        phonemes = hiragana_to_phonemes(word)
        print(f"{word} -> {phonemes}")

    # 2. 長音一致性
    print("\n========== 長音比較 ==========")
    for a, b in [("こー", "こう"), ("かー", "かあ")]:
        p1 = hiragana_to_phonemes(a)
        p2 = hiragana_to_phonemes(b)
        print(f"{a}: {p1}")
        print(f"{b}: {p2}")
        print(f"是否一致: {p1 == p2}\n")

    # 3. 詞邊界一致性
    print("========== 詞邊界比較 ==========")
    a = analyze_japanese_phonetics("さくらがさく", mode="phoneme")
    b = analyze_japanese_phonetics("さくら が さく", mode="phoneme")
    print("無空格:", a)
    print("有空格:", b)
    print("是否一致:", a.split() == b.split())

    # 4. 促音缺失比較
    print("\n========== 促音比較 ==========")
    p1 = hiragana_to_phonemes("きって")
    p2 = hiragana_to_phonemes("きて")
    print("Reference:", p1)
    print("Whisper  :", p2)
    for item in compare_phonemes(p1, p2):
        print(item)

    # 5. 一字多音候選測試
    print("\n========== 多音字候選測試 ==========")
    for kanji in ["行", "生", "角"]:
        candidates = get_all_readings_with_phonemes(kanji)
        print(f"\n漢字【{kanji}】的候選讀音：")
        for c in candidates:
            print(f"  讀音: {c['reading']:<6} | 羅馬字: {c['romaji']:<8} | 音素: {c['phoneme_str']}")

# python -m sandbox.new_test_dp.file_process.jp_tool