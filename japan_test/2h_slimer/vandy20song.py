import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Optional, Tuple

from sudachipy import Dictionary, SplitMode

import sandbox.japan_test.main as jp

# ============================================================
# CONFIG
# ============================================================
SONG_CSV = Path(r"C:\Users\kniou\Documents\project_in_1141\fianl\backend\web_crawler\lyrics_output.csv")
WHISPER_DIR = Path(r"G:\我的雲端硬碟\audio2\whisper_json")
SONG_MATCH_THRESHOLD = 0.72

MAX_READING_CANDIDATES = 10
READING_DP_BEAM = 120
READING_LENGTH_SLACK = 4
ALT_READING_PENALTY = 0.25

# ============================================================
# SUDACHI
# ============================================================
SUDACHI_DICT = Dictionary(dict="full")
SUDACHI = SUDACHI_DICT.create(mode=SplitMode.C)
SKIP_POS = {"空白", "補助記号", "記号"}

# ============================================================
# ROMAJI -> PHONEME
# ============================================================
VOWELS = set("aiueo")
MULTI_PHONEMES = [
    "tch", "sh", "ch", "ts", "ky", "gy", "ny", "hy", 
    "by", "py", "my", "ry", "dy", "ty", "jy"
]
CONSONANTS = set("bcdfghjklmnpqrstvwxyz")

def clean_romaji(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    replacements = {"ā": "aa", "ī": "ii", "ū": "uu", "ē": "ee", "ō": "ou"}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return "".join(c for c in text if c.isalpha())

def roma_to_phoneme_tokens(roma: str) -> List[str]:
    roma = clean_romaji(roma)
    tokens = []
    i = 0
    while i < len(roma):
        c = roma[i]
        if c in VOWELS:
            tokens.append(c)
            i += 1
            continue
        if c in CONSONANTS and c != "n" and i + 1 < len(roma) and roma[i + 1] == c:
            tokens.append("q")
            i += 1
            continue
        matched = False
        for phoneme in MULTI_PHONEMES:
            if roma.startswith(phoneme, i):
                tokens.append(phoneme)
                i += len(phoneme)
                matched = True
                break
        if matched:
            continue
        if c in CONSONANTS:
            tokens.append(c)
        i += 1
    return tokens

def reading_to_phonemes(reading: str) -> List[str]:
    return roma_to_phoneme_tokens(jp.to_romaji(reading))

# ============================================================
# CSV
# ============================================================
def open_csv_with_fallback(path: Path):
    for encoding in ("utf-8-sig", "utf-8", "cp932"):
        try:
            f = open(path, "r", encoding=encoding, newline="")
            f.read(4096)
            f.seek(0)
            return f
        except UnicodeDecodeError:
            try: f.close()
            except Exception: pass
    raise RuntimeError(f"Cannot decode CSV: {path}")

def load_song_csv(path: Path):
    songs = []
    with open_csv_with_fallback(path) as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return songs
        header = [x.strip().lstrip("\ufeff") for x in header]
        
        for row in reader:
            if not row:
                continue
            if len(header) == 5 and len(row) >= 6 and row[4].strip().lower().startswith(("http://", "https://")):
                song_name, lyrics = row[3].strip(), row[5].strip()
            else:
                mapping = {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}
                song_name = mapping.get("Song_Name", "").strip()
                lyrics = mapping.get("Lyrics", "").strip()
            if song_name and lyrics:
                songs.append({"song_name": song_name, "lyrics": lyrics})
    return songs

# ============================================================
# SONG NAME MATCH
# ============================================================
def normalize_song_name(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"(whisper|whisper_json|final|test|audio|vocal)", "", text, flags=re.IGNORECASE)
    return "".join(c for c in text if c.isalnum() or "\u3040" <= c <= "\u30ff" or "\u4e00" <= c <= "\u9fff")

def find_song_for_json(json_path: Path, songs) -> Tuple[Optional[dict], float]:
    stem = normalize_song_name(json_path.stem)
    for song in songs:
        if normalize_song_name(song["song_name"]) == stem:
            return song, 1.0

    best_song, best_score = None, 0.0
    for song in songs:
        song_norm = normalize_song_name(song["song_name"])
        if not song_norm:
            continue
        if song_norm in stem or stem in song_norm:
            score = min(len(song_norm), len(stem)) / max(len(song_norm), len(stem))
        else:
            score = SequenceMatcher(None, stem, song_norm).ratio()
        if score > best_score:
            best_score, best_song = score, song

    if best_score >= SONG_MATCH_THRESHOLD:
        return best_song, best_score
    return None, best_score

# ============================================================
# WHISPER JSON
# ============================================================
def load_whisper_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        segments = data["segments"] if isinstance(data.get("segments"), list) else [data]
    elif isinstance(data, list):
        segments = data
    else:
        raise ValueError(f"Unsupported JSON structure: {path}")

    lines = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        text = (seg.get("line") or seg.get("text") or "").strip()
        if text:
            lines.append(text)
    return "\n".join(lines)

# ============================================================
# PHONEME EDIT DISTANCE
# ============================================================
def phoneme_edit_distance(a: List[str], b: List[str]) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, token_a in enumerate(a, start=1):
        current = [i]
        for j, token_b in enumerate(b, start=1):
            sub_cost = 0 if token_a == token_b else 1
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + sub_cost))
        previous = current
    return previous[-1]

# ============================================================
# 多讀音候選
# ============================================================
@dataclass
class ReadingCandidate:
    reading: str
    phonemes: List[str]
    is_default: bool

@dataclass
class ReadingUnit:
    surface: str
    candidates: List[ReadingCandidate]

def get_lookup_readings(surface: str) -> List[str]:
    result = []
    try:
        entries = SUDACHI_DICT.lookup(surface)
    except Exception:
        return result
    for entry in entries:
        reading = entry.reading_form()
        if reading and reading not in result:
            result.append(reading)
    return result

def build_reading_units(text: str) -> List[ReadingUnit]:
    units = []
    for morpheme in SUDACHI.tokenize(text):
        pos = morpheme.part_of_speech()
        if pos[0] in SKIP_POS:
            continue
        surface = morpheme.surface()
        default_reading = morpheme.reading_form() or surface
        readings = [default_reading]
        for reading in get_lookup_readings(surface):
            if reading not in readings:
                readings.append(reading)

        candidates, seen = [], set()
        for reading in readings:
            phonemes = reading_to_phonemes(reading)
            signature = tuple(phonemes)
            if signature in seen:
                continue
            seen.add(signature)
            candidates.append(ReadingCandidate(
                reading=reading, phonemes=phonemes, is_default=(reading == default_reading)
            ))
            if len(candidates) >= MAX_READING_CANDIDATES:
                break
        units.append(ReadingUnit(surface=surface, candidates=candidates))
    return units

def default_phonemes(text: str) -> List[str]:
    result = []
    for unit in build_reading_units(text):
        if unit.candidates:
            result.extend(unit.candidates[0].phonemes)
    return result

# ============================================================
# 一字多音 Reading DP
# ============================================================
def choose_whisper_reading_dp(whisper_text: str, reference_phonemes: List[str]) -> List[str]:
    units = build_reading_units(whisper_text)
    if not units:
        return []

    states = {0: (0.0, [])}
    ref_len = len(reference_phonemes)

    for unit in units:
        next_states = {}
        for ref_pos, (base_cost, built_phonemes) in states.items():
            for candidate in unit.candidates:
                p = candidate.phonemes
                p_len = len(p)
                min_len = max(0, p_len - READING_LENGTH_SLACK)
                max_len = min(ref_len - ref_pos, p_len + READING_LENGTH_SLACK)
                
                lengths = [0] if ref_pos >= ref_len else range(min_len, max_len + 1)

                for seg_len in lengths:
                    end = ref_pos + seg_len
                    ref_segment = reference_phonemes[ref_pos:end]
                    cost = phoneme_edit_distance(p, ref_segment)
                    if not candidate.is_default:
                        cost += ALT_READING_PENALTY
                    total = base_cost + cost
                    old = next_states.get(end)
                    if old is None or total < old[0]:
                        next_states[end] = (total, built_phonemes + p)

        states = dict(sorted(next_states.items(), key=lambda item: item[1][0])[:READING_DP_BEAM])

    best = None
    for ref_pos, (cost, phonemes) in states.items():
        total_cost = cost + (ref_len - ref_pos)
        if best is None or total_cost < best[0]:
            best = (total_cost, phonemes)
    return best[1]

# ============================================================
# SCORE
# ============================================================
def calculate_score(lyrics_text: str, whisper_text: str) -> float:
    lyrics_phonemes = default_phonemes(lyrics_text)
    whisper_phonemes = choose_whisper_reading_dp(whisper_text, lyrics_phonemes)
    distance = phoneme_edit_distance(lyrics_phonemes, whisper_phonemes)
    denominator = max(len(lyrics_phonemes), len(whisper_phonemes), 1)
    score = 1.0 - distance / denominator
    return max(0.0, min(1.0, score))

# ============================================================
# MAIN
# ============================================================
def main():
    songs = load_song_csv(SONG_CSV)
    whisper_files = sorted(WHISPER_DIR.glob("*.json"))

    print(f"Songs in CSV : {len(songs)}")
    print(f"Whisper JSON : {len(whisper_files)}")
    print("\n" + "=" * 70)

    total_score = 0.0
    processed = 0

    for whisper_path in whisper_files:
        song, match_score = find_song_for_json(whisper_path, songs)
        if song is None:
            print(f"[SKIP] {whisper_path.name}")
            continue

        try:
            whisper_text = load_whisper_text(whisper_path)
            score = calculate_score(song["lyrics"], whisper_text)
        except Exception as exc:
            print(f"[ERROR] {whisper_path.name}: {exc}")
            continue

        processed += 1
        total_score += score
        print(f"{song['song_name']:<30} {score:.6f}")

    print("=" * 70)
    if processed:
        average = total_score / processed
        print(f"Average score: {average:.6f}")
        print(f"Processed    : {processed}")

if __name__ == "__main__":
    main()