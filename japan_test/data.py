import asyncio
from sudachipy import Dictionary, SplitMode
from core.manger import DatabaseManager

DB_PATH = r"config\jmdict.json"
db = DatabaseManager(DB_PATH)
tokenizer = Dictionary(dict="full").create()
split_mode = SplitMode.C

SUDACHI_JMDICT_POS_MAP = {
    "代名詞": ["pn"],
    "副詞": ["adv", "adv-to"],
    "助動詞": ["aux", "aux-v", "aux-adj", "cop"],
    "助詞": ["prt"],
    "動詞": ["v%"],
    "名詞": ["n", "n-adv", "n-t", "n-pr", "n-pref", "n-suf", "num"],
    "形容詞": ["adj-i", "adj-ix"],
    "形状詞": ["adj-na", "adj-no", "adj-f"],
    "感動詞": ["int"],
    "接尾辞": ["suf", "n-suf", "ctr"],
    "接続詞": ["conj"],
    "接頭辞": ["pref", "n-pref"],
    "連体詞": ["adj-pn"],
}

SKIP_POS = {"空白", "補助記号", "記号"}

def katakana_to_hiragana(text: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)

async def select_database(surface: str, dictionary_form: str, reading: str, sudachi_pos: str):
    pos_tags = SUDACHI_JMDICT_POS_MAP.get(sudachi_pos, [])
    if not pos_tags: return []
    return await db.create_sp("dbo.xsp_LookupJMdict", {
        "surface": surface, "dictionary_form": dictionary_form, "reading": reading, "pos_tags_json": pos_tags
    })

async def tokenize_japanese_text(text: str):
    print(f"\n原始文字：{text}\n" + "=" * 80)
    for i, m in enumerate(tokenizer.tokenize(text, split_mode), 1):
        pos_detail = m.part_of_speech()
        pos = pos_detail[0]
        if pos in SKIP_POS: continue
        
        surface, dict_form = m.surface(), m.dictionary_form()
        reading = katakana_to_hiragana(m.reading_form())
        
        print(f"[{i}] {surface} | 辭書形: {dict_form} | 讀音: {reading} | 詞性: {' / '.join(pos_detail)}")
        
        rows = await select_database(surface, dict_form, reading, pos)
        if not rows:
            print("    JMdict: 無結果\n" + "-" * 80)
            continue
            
        seen, results = set(), []
        for r in rows:
            key = (r.get("mwid"), r.get("mmid"), r.get("sense_no"), r.get("language_code"), r.get("meaning"))
            if key not in seen:
                seen.add(key)
                results.append(r)
                
        print(f"    JMdict 結果 ({len(results)} 筆):")
        for r in results:
            print(f"      - Sense {r.get('sense_no')}: {r.get('meaning')}")
        print("-" * 80)

async def main():
    try:
        await tokenize_japanese_text("死んだ眼で爆弾片手に口を開く")
    finally:
        await db.dispose()

if __name__ == "__main__":
    asyncio.run(main())