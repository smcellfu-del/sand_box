"""Build reproducible Global/SM phoneme-evidence statistics from reviewed JSON logs.

This program does NOT run DP or change review labels. It also builds D1/D2/D3 trial substitution scores/costs from reviewed evidence.
It is a post-review statistics stage for the user's existing JSON layouts:

    ROOT/reviewed_need/*.json  # analysis report, similarity_groups -> segments
    ROOT/reviewed_sm/*.json    # semi-global report, segments

Outputs (under ROOT/statistics_output by default):
    need_matrix_statistics.json
    sm_matrix_statistics.json
    per_song_statistics.json
    reviewed_need_with_statistics/*.json  (copies, original files unchanged)
    reviewed_sm_with_statistics/*.json
    quality_experiments/{need,sm}_{d1,d2,d3}_matrix.json
    quality_experiments/{need,sm}_quality_evidence.json

Usage (after filling REVIEWED_DATASET_ROOT at top of file):
    python -m sandbox.new_test_dp.file_process.blud_dataset
    python -m sandbox.new_test_dp.file_process.blud_dataset --root another/reviewed_dataset

Important: source-side tokens and events below are *provisional romanized tokens*,
not validated Japanese phonemes; review tags are model-assisted text screening.
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

# Keep identical for Global and SM; changing tokenizer requires rebuilding BOTH.
MULTI = sorted(
    ("tch", "sh", "ch", "ts", "ky", "gy", "ny", "hy", "by", "py",
     "my", "ry", "dy", "ty", "jy"),
    key=len, reverse=True,
)
CONSONANTS = set("bcdfghjklmnpqrstvwxyz")
SCHEMA = "reviewed_matrix_evidence_v1"

# ============================================================
# 使用者設定區：只要貼上你的「已 Review 資料集」資料夾路徑
# 必須包含 reviewed_need/ 和 reviewed_sm/ 兩個子資料夾。
# Windows 範例：r"D:\\MyProject\\annotated_alignment_review"
# 切記：raw string 不要以單一反斜線結尾。
# ============================================================
REVIEWED_DATASET_ROOT = r"sandbox\new_test_dp\file_process\annotated_alignment_review"  # <-- 在這裡貼上資料夾路徑
OUTPUT_DIRECTORY = r"sandbox\new_test_dp\file_process\annotated_alignment_review\02"       # 留空：自動輸出在 ROOT/statistics_output

# ============================================================
# Quality Gate + 0~1 Substitution Matrix 實驗參數（可修改）
# D1: A only；D2: A+B；D3: A + (B * B_WEIGHT)
# 原版 Confidence 參數只用於 Score，不影響審核等級。
# ============================================================
B_WEIGHT = 0.5
KF = 3.0
KS = 2.0
B_MIN_LEFT_MATCHES = 1
B_MIN_RIGHT_MATCHES = 1
B_MIN_TOTAL_CONTEXT = 3
B_MIN_ALIGNMENT_CHARS = 12
B_MIN_MATCH_FRACTION = 0.78
B_MAX_GAP_FRACTION = 0.18
B_SM_MIN_NORMALIZED_SCORE = 0.55
EXPERIMENT_SCHEMA = "quality_gate_matrix_v1"



def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        result = json.load(f)
    if not isinstance(result, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return result


def save_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def tokenize_chunks(chunks: list[str]) -> list[dict]:
    """Provisional tokenization with 0-based start/end in concatenated Romaji.

    Tokenization resets at original line / segment boundaries, as in prior V2.
    Double consonant first char becomes Q; some multi-letter sequences are one
    token. This is NOT a full Japanese phonology parser (e.g. nasal 'n' needs
    future validation); no time in seconds can be inferred from char offsets.
    """
    result = []
    offset = 0
    for chunk in chunks:
        i = 0
        while i < len(chunk):
            if chunk.startswith("tch", i):
                tok, width = "Q", 1
            elif (i + 1 < len(chunk) and chunk[i] == chunk[i+1]
                  and chunk[i] in CONSONANTS and chunk[i] != "n"):
                tok, width = "Q", 1
            else:
                tok = next((s for s in MULTI if chunk.startswith(s, i)), chunk[i])
                width = len(tok)
            result.append({"text": tok, "start": offset+i, "end": offset+i+width})
            i += width
        offset += len(chunk)
    return result


def char_to_token(tokens: list[dict]) -> dict[int, int]:
    return {pos: idx for idx, tok in enumerate(tokens)
            for pos in range(tok["start"], tok["end"])}


def coordinate_columns(al: str, aw: str, lyrics_start: int, whisper_start: int):
    if len(al) != len(aw):
        raise ValueError("Aligned strings must be same length")
    lpos, wpos = lyrics_start, whisper_start
    columns = []
    for left, right in zip(al, aw):
        li = lpos if left != "-" else None
        wi = wpos if right != "-" else None
        if left == "-" and right == "-":
            raise ValueError("Both sides of an alignment column are gaps")
        columns.append((li, wi))
        if li is not None:
            lpos += 1
        if wi is not None:
            wpos += 1
    return columns, lpos, wpos


def need_rows(need: dict) -> list[dict]:
    rows = [r for g in need["similarity_groups"].values()
            for r in g["segments"]]
    rows.sort(key=lambda row: row["line_id"])
    if len({r["line_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate Need line_id")
    return rows


def eligible_unit(review: dict) -> bool:
    return review.get("status", "").upper() == "ACCEPTED" and review.get("use_for_matrix") is True


def units_for_song(need: dict, sm: dict):
    """Normalize two JSON layouts to identical alignment-column structures."""
    rows = need_rows(need)
    segments = sorted(sm["segments"], key=lambda r: r["segment_index"])
    lyrics_chunks = [r["lyrics_aligned"].replace("-", "") for r in rows]
    whisper_chunks = [r["whisper_romaji"] for r in segments]
    lyrics = "".join(lyrics_chunks)
    whisper = "".join(whisper_chunks)

    need_units = []
    lpos = wpos = 0
    for r in rows:
        al, aw = r["lyrics_aligned"], r["whisper_aligned"]
        columns, next_l, next_w = coordinate_columns(al, aw, lpos, wpos)
        if al.replace("-", "") != lyrics[lpos:next_l]:
            raise ValueError("Need Lyrics coordinate mismatch")
        review = r.get("review", {})
        need_units.append({
            "id": r["line_id"], "accepted": eligible_unit(review), "review": review,
            "columns": columns,
            "approved_pairs": {
                (p["lyrics_char_start"], p["whisper_char_start"])
                for p in review.get("matrix_phoneme_pairs", [])
            },
        })
        lpos, wpos = next_l, next_w
    if lpos != len(lyrics):
        raise ValueError("Need Lyrics lines do not cover the reference")
    need_whisper = "".join(r["whisper_aligned"].replace("-", "") for r in rows)
    # Earlier Need analysis reports omit last few Whisper segments in two songs.
    if not whisper.startswith(need_whisper):
        raise ValueError("Global Whisper prefix differs from SM raw Whisper sequence")

    sm_units = []
    for r in segments:
        cols, end_l, end_w = coordinate_columns(
            r["aligned_lyrics"], r["aligned_whisper"],
            r["lyrics_char_start"], r["whisper_char_start"]
        )
        if (end_l, end_w) != (r["lyrics_char_end"], r["whisper_char_end"]):
            raise ValueError(f"SM coordinate mismatch: segment {r['segment_index']}")
        if r["aligned_lyrics"].replace("-", "") != lyrics[r["lyrics_char_start"]:end_l]:
            raise ValueError(f"SM Lyrics mismatch: segment {r['segment_index']}")
        if r["aligned_whisper"].replace("-", "") != whisper[r["whisper_char_start"]:end_w]:
            raise ValueError(f"SM Whisper mismatch: segment {r['segment_index']}")
        review = r.get("review", {})
        sm_units.append({
            "id": r["segment_index"], "accepted": eligible_unit(review), "review": review,
            "columns": cols,
            "approved_pairs": {
                
                (p["lyrics_char_start"], p["whisper_char_start"])
                for p in review.get("matrix_phoneme_pairs", [])
            },
        })
    return lyrics_chunks, whisper_chunks, {
        "Need": (need_units, len(whisper)-len(need_whisper)),
        "SM": (sm_units, 0),
    }


def calculate_method_song(lyrics_tokens, whisper_tokens, units, song: str, method: str):
    """Classify each *complete* source token in each ACCEPTED unit.

    Strict 1-to-1 SUB event is counted in per-source sub_count; it is elevated
    to a verified substitution candidate ONLY if reviewed matrix_phoneme_pairs
    explicitly contains the exact source/observed token start coordinates.
    Overlapping SM units covering the same Lyrics token: drop all candidates
    for that source position rather than double count or arbitrarily choose.
    """
    lmap = char_to_token(lyrics_tokens)
    wmap = char_to_token(whisper_tokens)
    raw = Counter(t["text"] for t in lyrics_tokens)
    possibilities = defaultdict(list)
    accepted = 0
    observed_insert_tokens = set()

    for unit in units:
        if not unit["accepted"]:
            continue
        accepted += 1
        lcolumns = defaultdict(list)
        wcolumns = defaultdict(list)
        for ci, (lp, wp) in enumerate(unit["columns"]):
            if lp is not None:
                if lp not in lmap:
                    raise ValueError(f"Unknown Lyrics char index {lp} in {song}")
                lcolumns[lmap[lp]].append((ci, lp, wp))
            if wp is not None:
                if wp not in wmap:
                    raise ValueError(f"Unknown Whisper char index {wp} in {song}")
                wcolumns[wmap[wp]].append((ci, lp, wp))

        # Independent observed-side insertions, tracked separately.
        for wid, cols in wcolumns.items():
            t = whisper_tokens[wid]
            if (len(cols) == t["end"]-t["start"]
                and {c[2] for c in cols} == set(range(t["start"], t["end"]))
                and all(c[1] is None for c in cols)):
                observed_insert_tokens.add(wid)

        for lid, cols in lcolumns.items():
            source = lyrics_tokens[lid]
            if (len(cols) != source["end"]-source["start"]
                or {c[1] for c in cols} != set(range(source["start"], source["end"]))):
                continue  # token split by line/segment boundary

            paired = [c[2] for c in cols]
            state, observed, observed_start, approved = "COMPLEX", None, None, False
            if all(p is None for p in paired):
                state = "DELETE"
            elif all(p is not None for p in paired):
                wid_set = {wmap[p] for p in paired}
                if len(wid_set) == 1:
                    wid = next(iter(wid_set))
                    target = whisper_tokens[wid]
                    wcols = wcolumns[wid]
                    full_observed = (
                        len(wcols) == target["end"]-target["start"]
                        and {c[2] for c in wcols} == set(range(target["start"], target["end"]))
                    )
                    same_columns = len(cols) == len(wcols) and {c[0] for c in cols} == {c[0] for c in wcols}
                    if full_observed and same_columns:
                        observed, observed_start = target["text"], target["start"]
                        state = "MATCH" if source["text"] == observed else "SUB"
                        approved = state == "SUB" and (source["start"], observed_start) in unit["approved_pairs"]
            possibilities[lid].append({
                "state": state, "source": source["text"],
                "source_start": source["start"], "observed": observed,
                "observed_start": observed_start, "approved": approved,
                "unit_id": unit["id"],
            })

    symbol = defaultdict(Counter)
    clean_pairs = Counter()
    verified_pairs = Counter()
    event_refs = defaultdict(list)
    duplicates = 0
    for lid, options in possibilities.items():
        if len(options) != 1:
            duplicates += 1
            continue
        o = options[0]
        source = o["source"]
        stat = symbol[source]
        stat["reviewed_count"] += 1
        stat[f'{o["state"].lower()}_count'] += 1
        if o["state"] == "SUB":
            pair = (source, o["observed"])
            clean_pairs[pair] += 1
            if o["approved"]:
                verified_pairs[pair] += 1
                event_refs[pair].append({
                    "song": song, "method": method, "unit_id": o["unit_id"],
                    "lyrics_char_start": o["source_start"],
                    "whisper_char_start": o["observed_start"],
                })

    source_statistics = {}
    for source in sorted(raw):
        counts = symbol[source]
        all_count = raw[source]
        reviewed = counts["reviewed_count"]
        match, sub, delete, complex_ = (counts[k] for k in
                                         ("match_count", "sub_count", "delete_count", "complex_count"))
        if match + sub + delete + complex_ != reviewed:
            raise AssertionError(f"Partition violated: {song}, {method}, {source}")
        if reviewed > all_count:
            raise AssertionError(f"Reviewed > raw: {song}, {method}, {source}")
        source_statistics[source] = {
            "all_count": all_count,
            "reviewed_count": reviewed,
            "unreviewed_or_overlap_count": all_count-reviewed,
            "match_count": match,
            "sub_count": sub,
            "delete_count": delete,
            "complex_count": complex_,
            "verified_sub_count": sum(n for (s, _), n in verified_pairs.items() if s == source),
        }

    return {
        "song_id": song, "method": method,
        "all_source_token_count": len(lyrics_tokens),
        "accepted_unit_count": accepted,
        "total_unit_count": len(units),
        "overlapping_lyrics_positions_excluded": duplicates,
        "observed_insert_token_count_in_accepted_units": len(observed_insert_tokens),
        "source_statistics": source_statistics,
        "clean_pairs": clean_pairs,
        "verified_pairs": verified_pairs,
        "event_refs": event_refs,
    }


def rounded_ratio(num: int, den: int):
    return round(num / den, 8) if den else None


def build_method_statistics(songs: dict, method: str) -> dict:
    stats = defaultdict(Counter)
    appears_raw = defaultdict(set)
    appears_reviewed = defaultdict(set)
    clean_pairs = Counter()
    verified_pairs = Counter()
    song_verified = defaultdict(Counter)
    event_refs = defaultdict(list)
    n_accepted = 0
    n_units = 0
    n_duplicates = 0
    n_insert = 0

    for song, data in sorted(songs.items()):
        result = data[method]
        n_accepted += result["accepted_unit_count"]
        n_units += result["total_unit_count"]
        n_duplicates += result["overlapping_lyrics_positions_excluded"]
        n_insert += result["observed_insert_token_count_in_accepted_units"]
        for symbol, values in result["source_statistics"].items():
            stats[symbol].update({k:v for k,v in values.items() if k != "unreviewed_or_overlap_count"})
            if values["all_count"]:
                appears_raw[symbol].add(song)
            if values["reviewed_count"]:
                appears_reviewed[symbol].add(song)
        clean_pairs.update(result["clean_pairs"])
        verified_pairs.update(result["verified_pairs"])
        for pair, count in result["verified_pairs"].items():
            song_verified[pair][song] += count
        for pair, refs in result["event_refs"].items():
            event_refs[pair].extend(refs)

    # Recompute denominators from VERIFIABLE pair evidence only. No Kf/Ks score.
    src_errors, tgt_errors = Counter(), Counter()
    for (src, tgt), count in verified_pairs.items():
        src_errors[src] += count
        tgt_errors[tgt] += count
    total_verified = sum(verified_pairs.values())
    pair_entries = []
    for (src, tgt), count in sorted(verified_pairs.items(), key=lambda x: (-x[1], x[0])):
        conditional = rounded_ratio(count, src_errors[src])
        background = rounded_ratio(tgt_errors[tgt], total_verified)
        pair_entries.append({
            "target": src, "observed": tgt,
            "err_count": count,
            "err_song_count": len(song_verified[(src, tgt)]),
            "per_song_err_count": dict(sorted(song_verified[(src, tgt)].items())),
            "source_error_total_verified": src_errors[src],
            "observed_background_error_total_verified": tgt_errors[tgt],
            "total_verified_substitutions": total_verified,
            "conditional_probability": conditional,
            "background_probability": background,
            "lift": round((conditional / background), 8) if background else None,
            "evidence": event_refs[(src, tgt)],
        })

    # Helpful per-symbol breakdown, including candidates rejected at pair level.
    clean_by_source = defaultdict(Counter)
    verified_by_source = defaultdict(Counter)
    for (src, tgt), count in clean_pairs.items():
        clean_by_source[src][tgt] = count
    for (src, tgt), count in verified_pairs.items():
        verified_by_source[src][tgt] = count

    symbols = {}
    for src in sorted(stats):
        st = stats[src]
        all_count = st["all_count"]
        reviewed = st["reviewed_count"]
        symbols[src] = {
            "all_count": all_count,
            "all_song_count": len(appears_raw[src]),
            "reviewed_count": reviewed,
            "reviewed_song_count": len(appears_reviewed[src]),
            "unreviewed_or_overlap_count": all_count-reviewed,
            "match_count": st["match_count"],
            "sub_count": st["sub_count"],
            "delete_count": st["delete_count"],
            "complex_count": st["complex_count"],
            "verified_sub_count": st["verified_sub_count"],
            "match_fraction_in_reviewed": rounded_ratio(st["match_count"], reviewed),
            "sub_fraction_in_reviewed": rounded_ratio(st["sub_count"], reviewed),
            "clean_substitution_targets": dict(sorted(clean_by_source[src].items())),
            "verified_substitution_targets": dict(sorted(verified_by_source[src].items())),
        }
        if st["verified_sub_count"] != sum(verified_by_source[src].values()):
            raise AssertionError(f"Pair/source evidence mismatch for {method}: {src}")

    return {
        "schema_version": SCHEMA,
        "method": method,
        "unit": "provisional_romaji_tokens",
        "review_type": "model_assisted_text_screening_not_audio_ground_truth",
        "num_songs": len(songs),
        "summary": {
            "all_source_token_count": sum(x["all_count"] for x in symbols.values()),
            "reviewed_source_token_count": sum(x["reviewed_count"] for x in symbols.values()),
            "match_count": sum(x["match_count"] for x in symbols.values()),
            "sub_count": sum(x["sub_count"] for x in symbols.values()),
            "delete_count": sum(x["delete_count"] for x in symbols.values()),
            "complex_count": sum(x["complex_count"] for x in symbols.values()),
            "verified_substitution_count": total_verified,
            "accepted_units": n_accepted,
            "total_units": n_units,
            "overlapping_lyrics_positions_excluded": n_duplicates,
            "observed_insert_token_count_in_accepted_units": n_insert,
        },
        "symbols": symbols,
        "substitution_pairs": pair_entries,
        "warnings": [
            "Only units with review.status=ACCEPTED AND review.use_for_matrix=true are counted as reviewed.",
            "sub_count includes clean 1-to-1 substitutions in reviewed units; err_count only counts context-supported matrix_phoneme_pairs.",
            "No substitution score/cost is calculated; Kf/Ks are not used.",
            "Selected reviewed regions bias observed error rates; fractions are not unbiased ASR error probabilities.",
            "Character offsets cannot be converted to audio seconds without timestamp mapping.",
            "Provisional Romaji grouping requires future validation for Q/N/sh/ch/ts etc.",
        ],
    }


def serialize_per_song(record: dict) -> dict:
    return {
        k: (dict(sorted((f"{x[0]}->{x[1]}", n) for x,n in v.items())) if isinstance(v, Counter)
            else {f"{x[0]}->{x[1]}": refs for x,refs in v.items()} if k == "event_refs"
            else v)
        for k,v in record.items()
    }



def _pair_location(pair: dict) -> tuple[int, int]:
    return (int(pair["lyrics_char_start"]), int(pair["whisper_char_start"]))


def _b_gate(review: dict, method: str, candidate: dict, unit_chars: int) -> tuple[bool, str]:
    """Conservative, reproducible candidate-level B gate; NOT verified truth."""
    if review.get("status", "").upper() not in {"ACCEPTED", "UNCERTAIN"}:
        return False, "unit_not_accepted_or_uncertain"
    if not candidate.get("context_supported", False):
        return False, "context_unsupported"
    left = int(candidate.get("left_match_context") or 0)
    right = int(candidate.get("right_match_context") or 0)
    if (left < B_MIN_LEFT_MATCHES or right < B_MIN_RIGHT_MATCHES
            or left + right < B_MIN_TOTAL_CONTEXT):
        return False, "insufficient_two_sided_match_context"
    f = review.get("features", {})
    if (unit_chars < B_MIN_ALIGNMENT_CHARS or
            float(f.get("match_fraction") or 0) < B_MIN_MATCH_FRACTION):
        return False, "short_or_low_match_fraction"
    gap_count = int(f.get("gap_count") or 0)
    if gap_count > max(3, unit_chars * B_MAX_GAP_FRACTION):
        return False, "too_many_gaps"
    if method == "SM":
        if f.get("order_conflict") is True:
            return False, "order_conflict"
        occurrences = f.get("exact_full_occurrences")
        if occurrences is not None and int(occurrences) > 1:
            return False, "repeated_full_lyrics_ambiguous"
        score = f.get("normalized_score")
        if score is None or float(score) < B_SM_MIN_NORMALIZED_SCORE:
            return False, "low_semi_global_score"
    return True, "context_and_alignment_thresholds_passed"


def _same_one_to_one_alignment(columns, ltok, wtok) -> bool:
    """Require two COMPLETE tokens to face one another with no gaps/extra chars.

    Supports compound tokens like sh/ch of equal aligned lengths. This does NOT
    infer a phoneme pair from a partial mismatch of multi-letter Romaji symbols.
    """
    lp_to_wp = {}
    wp_to_lp = {}
    for lp, wp in columns:
        if lp is not None:
            lp_to_wp[lp] = wp
        if wp is not None:
            wp_to_lp[wp] = lp
    source_range = range(ltok["start"], ltok["end"])
    observed_range = range(wtok["start"], wtok["end"])
    if len(source_range) != len(observed_range):
        return False
    return (all(lp_to_wp.get(i) == j for i, j in zip(source_range, observed_range))
            and all(wp_to_lp.get(j) == i for i, j in zip(source_range, observed_range)))


def collect_quality_events(
    lyrics_tokens: list[dict], whisper_tokens: list[dict],
    units: list[dict], song: str, method: str,
) -> tuple[list[dict], dict]:
    """One A/B label per validated SUB token pair; never auto-accept REJECTED.

    A: previous ACCEPTED unit's explicitly approved matrix_phoneme_pairs.
    B: a context-supported candidate in ACCEPTED/UNCERTAIN unit passing gate.
    Candidate positions are VERIFIED against actual DP traceback and tokenization.
    Any overlapping source/observed coordinates are conservatively excluded.
    """
    lt_by_start = {t["start"]: t for t in lyrics_tokens}
    wt_by_start = {t["start"]: t for t in whisper_tokens}
    draft = []
    reasons = Counter()
    status_counts = Counter()
    # One accepted SM segment may overlap another on the *same Lyrics token*.
    # Count every accepted unit's complete source tokens, including MATCH columns.
    # Otherwise an A substitution can sneak in even though another accepted
    # segment also claims that position as MATCH.
    lmap = char_to_token(lyrics_tokens)
    accepted_coverage = Counter()
    for accepted_unit in units:
        if not accepted_unit["accepted"]:
            continue
        visited = set()
        for lp, wp in accepted_unit["columns"]:
            if lp is not None and lp in lmap:
                visited.add(lmap[lp])
        for lid in visited:
            tok = lyrics_tokens[lid]
            covered = {lp for lp, wp in accepted_unit["columns"] if lp is not None
                       and tok["start"] <= lp < tok["end"]}
            if covered == set(range(tok["start"], tok["end"])):
                accepted_coverage[tok["start"]] += 1
    for unit in units:
        rev = unit.get("review", {})
        status = str(rev.get("status", "")).upper()
        status_counts[status] += 1
        if status == "REJECTED":
            continue
        approved = {_pair_location(x): x for x in rev.get("matrix_phoneme_pairs", [])}
        candidate = {_pair_location(x): x for x in rev.get("phoneme_candidates", [])}
        # Always include approved pairs (even if not duplicated in candidates).
        for coords, row in {**candidate, **approved}.items():
            if coords in approved and eligible_unit(rev):
                level, why = "A", "previous_review_approved"
            else:
                ncols = len(unit["columns"])
                passes, why = _b_gate(rev, method, row, ncols)
                if not passes:
                    reasons[why] += 1
                    continue
                level = "B"
            lp, wp = coords
            ltok, wtok = lt_by_start.get(lp), wt_by_start.get(wp)
            if ltok is None or wtok is None:
                reasons["not_a_complete_token_start"] += 1
                continue
            if ltok["text"] != row.get("target") or wtok["text"] != row.get("observed"):
                reasons["phoneme_name_or_tokenization_mismatch"] += 1
                continue
            if ltok["text"] == wtok["text"]:
                reasons["not_substitution"] += 1
                continue
            if not _same_one_to_one_alignment(unit["columns"], ltok, wtok):
                reasons["not_complete_one_to_one_traceback"] += 1
                continue
            if accepted_coverage[ltok["start"]] > 1:
                reasons["overlap_with_other_accepted_unit"] += 1
                continue
            if (not unit["accepted"] and accepted_coverage[ltok["start"]] > 0):
                reasons["uncertain_candidate_overlaps_accepted_alignment"] += 1
                continue
            draft.append({
                "song": song,
                "method": method,
                "unit_id": unit["id"],
                "source": ltok["text"],
                "observed": wtok["text"],
                "lyrics_char_start": lp,
                "whisper_char_start": wp,
                "level": level,
                "review_status": status,
                "review_confidence": rev.get("confidence"),
                "left_match_context": row.get("left_match_context"),
                "right_match_context": row.get("right_match_context"),
                "reason": why,
            })
    # If a Lyrics position or Whisper position is claimed by multiple units,
    # cannot pick a correct source/observed mapping from this evidence alone.
    l_counts = Counter((x["song"], x["lyrics_char_start"]) for x in draft)
    w_counts = Counter((x["song"], x["whisper_char_start"]) for x in draft)
    events = []
    for x in draft:
        if (l_counts[(song, x["lyrics_char_start"])] > 1
                or w_counts[(song, x["whisper_char_start"])] > 1):
            reasons["overlapping_substitution_coordinate"] += 1
        else:
            events.append(x)
    events.sort(key=lambda x: (x["lyrics_char_start"], x["whisper_char_start"]))
    return events, {
        "unit_status_counts": dict(status_counts),
        "candidate_rejections": dict(reasons),
        "kept_A": sum(x["level"] == "A" for x in events),
        "kept_B": sum(x["level"] == "B" for x in events),
    }


def build_variant_matrix(method: str, variant: str, events: list[dict],
                         base_stats: dict, num_songs: int) -> dict:
    """Previous Lift × Confidence, clipped to a nonnegative 0..1 similarity.

    D1: A (1.0)
    D2: A (1.0) + B (1.0)
    D3: A (1.0) + B (B_WEIGHT)
    """
    assert variant in {"D1", "D2", "D3"}
    filtered = [e for e in events if variant != "D1" or e["level"] == "A"]
    pair_weighted = defaultdict(float)
    pair_raw = Counter()
    pair_a = Counter()
    pair_b = Counter()
    pair_songs = defaultdict(lambda: defaultdict(lambda: {"raw_count": 0, "weighted_count": 0.0}))
    for e in filtered:
        pair = (e["source"], e["observed"])
        weight = 1.0 if e["level"] == "A" or variant != "D3" else B_WEIGHT
        pair_weighted[pair] += weight
        pair_raw[pair] += 1
        if e["level"] == "A": pair_a[pair] += 1
        else: pair_b[pair] += 1
        sd = pair_songs[pair][e["song"]]
        sd["raw_count"] += 1
        sd["weighted_count"] += weight

    source_weighted = defaultdict(float)
    background_weighted = defaultdict(float)
    total_weighted = sum(pair_weighted.values())
    for (source, target), count in pair_weighted.items():
        source_weighted[source] += count
        background_weighted[target] += count

    pairs = []
    for (source, observed), weighted in sorted(pair_weighted.items(), key=lambda x: (-x[1], x[0])):
        probability = weighted / source_weighted[source]
        background = background_weighted[observed] / total_weighted
        lift = probability / background
        frequency_confidence = weighted / (weighted + KF) if KF >= 0 else 0
        song_count = len(pair_songs[(source, observed)])
        song_confidence = song_count / (song_count + KS) if KS >= 0 else 0
        confidence = frequency_confidence * song_confidence
        association = max(0.0, (lift - 1.0) / (lift + 1.0))
        score = min(1.0, max(0.0, confidence * association))
        per_song = {
            name: {"raw_count": int(v["raw_count"]), "weighted_count": round(v["weighted_count"], 8)}
            for name, v in sorted(pair_songs[(source, observed)].items())
        }
        pairs.append({
            "target": source, "observed": observed,
            "err_count": pair_raw[(source, observed)],
            "a_count": pair_a[(source, observed)],
            "b_count": pair_b[(source, observed)],
            "weighted_err_count": round(weighted, 8),
            "err_song_count": song_count,
            "per_song_err_count": per_song,
            "source_error_total_weighted": round(source_weighted[source], 8),
            "observed_background_total_weighted": round(background_weighted[observed], 8),
            "conditional_probability": round(probability, 8),
            "background_probability": round(background, 8),
            "lift": round(lift, 8),
            "frequency_confidence": round(frequency_confidence, 8),
            "song_confidence": round(song_confidence, 8),
            "confidence": round(confidence, 8),
            "association": round(association, 8),
            "score": round(score, 8),
            "substitution_similarity": round(score, 8),
            "edit_cost": round(1.0 - score, 8),
            # Only valid for a MAX-score NW with MATCH=+1, MISMATCH=-1.
            "nw_reward_match1_mismatch_minus1": round(-1.0 + 2.0 * score, 8),
        })

    return {
        "schema_version": EXPERIMENT_SCHEMA,
        "method": method,
        "variant": variant,
        "variant_definition": {
            "D1": "A only",
            "D2": "A + B (both full weight)",
            "D3": "A full weight + B discounted weight",
        }[variant],
        "unit": "provisional_romaji_tokens",
        "training_song_count": num_songs,
        "config": {
            "Kf": KF, "Ks": KS, "B_weight_D3": B_WEIGHT,
            "B_context_left_min": B_MIN_LEFT_MATCHES,
            "B_context_right_min": B_MIN_RIGHT_MATCHES,
            "B_context_sum_min": B_MIN_TOTAL_CONTEXT,
            "B_match_fraction_min": B_MIN_MATCH_FRACTION,
            "B_gap_fraction_max": B_MAX_GAP_FRACTION,
            "B_min_alignment_chars": B_MIN_ALIGNMENT_CHARS,
            "B_SM_min_normalized_score": B_SM_MIN_NORMALIZED_SCORE,
        },
        "score_definition": {
            "probability": "weighted_pair / sum(weighted_pairs_with_same_source)",
            "background": "weighted_pairs_with_same_observed / all_weighted_pairs",
            "lift": "probability / background",
            "frequency_confidence": "weighted_pair / (weighted_pair + Kf)",
            "song_confidence": "number_of_distinct_songs_with_pair / (number_of_distinct_songs_with_pair + Ks)",
            "score": "confidence * max(0, (lift-1)/(lift+1)) ; clipped to [0,1]",
            "edit_cost": "1 - score",
        },
        "summary": {
            "pair_types": len(pairs),
            "raw_event_count": sum(pair_raw.values()),
            "A_events": sum(pair_a.values()),
            "B_events": sum(pair_b.values()),
            "weighted_event_count": round(total_weighted, 8),
            "positive_score_pair_types": sum(x["score"] > 0 for x in pairs),
        },
        # Original symbol denominators based on ACCEPTED units only. They are
        # NOT used for variant conditional/background probabilities.
        "symbols_baseline_accepted_only": base_stats["symbols"],
        "substitution_pairs": pairs,
        "warnings": [
            "Model-assisted text/coordinate review; not audio-verified labels.",
            "Level B are candidates screened by heuristic thresholds, not manually approved.",
            "B gate uses no other method's aligned coordinates as a truth source.",
            "Score 0..1 is a similarity, not a calibrated probability of a true substitution.",
            "Kf/Ks remain tunable heuristic confidence constants, not validated parameters.",
            "Lift<=1 -> score=0 (negative association is not rewarded).",
            "Provisional Romaji tokenizer needs phonological checking before final phoneme evaluation.",
            "The baseline symbols denominators apply to ACCEPTED units only and must not be read as variant D2/D3 exposure counts.",
            "To insert this 0..1 score into max-score NW with match=1 mismatch=-1, use reward=-1+2*score, NOT raw score.",
        ],
    }


def build_quality_matrix_experiments(needs, sms, source_results,
                                     need_base, sm_base, output: Path,
                                     include_copy: bool = False) -> dict:
    """Emit six reproducible matrices and event-level audit, no source mutations."""
    all_events = {"Need": [], "SM": []}
    audit = {"Need": {}, "SM": {}}
    for song in sorted(needs):
        if not include_copy and " copy" in song.lower():
            continue
        lchunks, wchunks, methods = units_for_song(needs[song], sms[song])
        ltoks, wtoks = tokenize_chunks(lchunks), tokenize_chunks(wchunks)
        for method in ("Need", "SM"):
            units, _ = methods[method]
            events, diagnostics = collect_quality_events(ltoks, wtoks, units, song, method)
            all_events[method].extend(events)
            audit[method][song] = diagnostics
    root = output / "quality_experiments"
    results = {}
    for method, base in (("Need", need_base), ("SM", sm_base)):
        save_json(root / f"{method.lower()}_quality_evidence.json", {
            "schema_version": EXPERIMENT_SCHEMA,
            "method": method,
            "events": all_events[method],
            "per_song_diagnostics": audit[method],
            "notice": "B is heuristic screening, not ground truth. Lyrics coordinate units are Romaji characters.",
        })
        results[method] = {}
        for variant in ("D1", "D2", "D3"):
            matrix = build_variant_matrix(method, variant, all_events[method], base, len(source_results))
            save_json(root / f"{method.lower()}_{variant.lower()}_matrix.json", matrix)
            results[method][variant] = matrix["summary"]
    return results


def run(root: Path, output: Path, include_copy: bool = False,
        embed_reviewed_copies: bool = True) -> dict:
    need_dir = root / "reviewed_need"
    sm_dir = root / "reviewed_sm"
    if not need_dir.is_dir() or not sm_dir.is_dir():
        raise FileNotFoundError(f"Expected reviewed_need/ and reviewed_sm/ inside {root}")

    needs = {}
    need_files = {}
    for path in sorted(need_dir.glob("*.json")):
        obj = load_json(path)
        song = obj["song_name"]
        if song in needs:
            raise ValueError(f"Duplicate Need song: {song}")
        needs[song], need_files[song] = obj, path
    sms = {}
    sm_files = {}
    for path in sorted(sm_dir.glob("*.json")):
        obj = load_json(path)
        song = obj["song_id"]
        if song in sms:
            raise ValueError(f"Duplicate SM song: {song}")
        sms[song], sm_files[song] = obj, path
    if set(needs) != set(sms):
        raise ValueError(f"Need/SM song mismatch: {sorted(set(needs) ^ set(sms))}")

    results = {}
    incomplete_need = {}
    for song in sorted(needs):
        if not include_copy and " copy" in song.lower():
            continue
        lchunks, wchunks, methods = units_for_song(needs[song], sms[song])
        ltoks = tokenize_chunks(lchunks)
        wtoks = tokenize_chunks(wchunks)
        results[song] = {}
        for method in ("Need", "SM"):
            units, missing_suffix_chars = methods[method]
            stats = calculate_method_song(ltoks, wtoks, units, song, method)
            stats["need_whisper_missing_suffix_chars"] = missing_suffix_chars
            results[song][method] = stats
            if method == "Need" and missing_suffix_chars:
                incomplete_need[song] = missing_suffix_chars

    # Process once; output is deterministic and original input files are untouched.
    need_output = build_method_statistics(results, "Need")
    sm_output = build_method_statistics(results, "SM")
    need_output["need_whisper_missing_suffix_by_song"] = incomplete_need
    for method, result in (("Need", need_output), ("SM", sm_output)):
        save_json(output / f"{method.lower()}_matrix_statistics.json", result)

    quality_summary = build_quality_matrix_experiments(
        needs, sms, results, need_output, sm_output, output,
        include_copy=include_copy,
    )

    per_song_output = {
        song: {method: serialize_per_song(stats) for method, stats in per_method.items()}
        for song, per_method in results.items()
    }
    save_json(output / "per_song_statistics.json", per_song_output)

    if embed_reviewed_copies:
        for song in results:
            for method, objs, paths, folder in (
                ("Need", needs, need_files, "reviewed_need_with_statistics"),
                ("SM", sms, sm_files, "reviewed_sm_with_statistics"),
            ):
                original = objs[song]
                # Do not overwrite original phoneme_statistics, review tags, DP scores.
                copy_obj = dict(original)
                copy_obj["matrix_statistics"] = {
                    "schema_version": SCHEMA,
                    "unit": "provisional_romaji_tokens",
                    "method": method,
                    "source_statistics": results[song][method]["source_statistics"],
                    "clean_pair_counts": serialize_per_song(results[song][method])["clean_pairs"],
                    "verified_pair_counts": serialize_per_song(results[song][method])["verified_pairs"],
                    "accepted_units": results[song][method]["accepted_unit_count"],
                    "overlapping_positions_excluded": results[song][method]["overlapping_lyrics_positions_excluded"],
                }
                save_json(output / folder / paths[song].name, copy_obj)

    return {
        "songs": len(results),
        "Need": need_output["summary"],
        "SM": sm_output["summary"],
        "out_dir": str(output),
        "need_report_truncated_whisper_songs": incomplete_need,
        "quality_experiments": quality_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    # --root 不再是必填；優先使用命令列參數，否則使用上面的設定路徑。
    parser.add_argument("--root", type=Path,
                        help="Override REVIEWED_DATASET_ROOT")
    parser.add_argument("--output", type=Path,
                        help="Override OUTPUT_DIRECTORY; default: ROOT/statistics_output")
    parser.add_argument("--include-copy", action="store_true",
                        help="Include the redundant ' copy' test song in training statistics")
    parser.add_argument("--no-embed", action="store_true",
                        help="Don't create per-song reviewed JSON copies with matrix_statistics")
    args = parser.parse_args()

    if args.root is not None:
        root = args.root.expanduser()
    elif REVIEWED_DATASET_ROOT.strip():
        root = Path(REVIEWED_DATASET_ROOT.strip()).expanduser()
    else:
        parser.error(
            "請在檔案上方 REVIEWED_DATASET_ROOT 貼入已審核資料集路徑，"
            "或使用 --root 路徑。資料夾內必須有 reviewed_need 和 reviewed_sm。"
        )

    if args.output is not None:
        output = args.output.expanduser()
    elif OUTPUT_DIRECTORY.strip():
        output = Path(OUTPUT_DIRECTORY.strip()).expanduser()
    else:
        output = root / "statistics_output"

    print(f"[輸入] {root.resolve()}")
    print(f"[輸出] {output.resolve()}")
    report = run(root, output, include_copy=args.include_copy,
                 embed_reviewed_copies=not args.no_embed)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

#python -m sandbox.new_test_dp.file_process.blud_dataset