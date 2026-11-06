from collections import defaultdict, Counter
from difflib import SequenceMatcher


# ============================================================
# BASIC SCORE
# 功能：
# 1. 計算兩個 Sequence 的相似度
# 2. Representation Test / Loop Recovery 共用
# ============================================================

def sequence_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


# ============================================================
# GLOBAL DP — NEEDLEMAN-WUNSCH
# 功能：
# 1. 整首 Lyric 全域對齊s ↔ ASR
# 2. 不使用 L / W Segment Boundary
# 3. 回傳 Lyrics → ASR 與 ASR → Lyrics 雙向 Mapping
# 4. ASR 對到 Gap 時保留 target_to_ref[target] = None
# ============================================================

def global_align(reference, target, match_score=2, mismatch_score=-1, gap_score=-2):
    n, m = len(reference), len(target)
    dp = [[0] * (m + 1) for _ in range(n + 1)] #建立dp 矩陣
    trace = [[None] * (m + 1) for _ in range(n + 1)] #這個就不懂在幹嘛了
    for i in range(1, n + 1):

        dp[i][0] = i * gap_score #全部歸0
        trace[i][0] = "U"

    for j in range(1, m + 1):
        dp[0][j] = j * gap_score #全部歸0
        trace[0][j] = "L"

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            # kaworu(ref) V.S gaworu(tar) 
            char_score = match_score if reference[i - 1] == target[j - 1] else mismatch_score 
            diagonal = dp[i - 1][j - 1] + char_score # 跑斜邊
            up = dp[i - 1][j] + gap_score 
            left = dp[i][j - 1] + gap_score

            best = max(diagonal, up, left) # 找最佳解

            dp[i][j] = best
            trace[i][j] = "D" if best == diagonal else ("U" if best == up else "L")
    #下面是負責吧路徑往回走嗎 下面我還須要想一下
    i, j = n, m 
    aligned_reference = []
    aligned_target = []
    mapping_pairs = []

    while i > 0 or j > 0:
        direction = trace[i][j]

        if i > 0 and j > 0 and direction == "D":
            aligned_reference.append(reference[i - 1])
            aligned_target.append(target[j - 1])
            mapping_pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1

        elif i > 0 and direction == "U":
            aligned_reference.append(reference[i - 1])
            aligned_target.append("-")
            mapping_pairs.append((i - 1, None))
            i -= 1

        else:
            aligned_reference.append("-")
            aligned_target.append(target[j - 1])
            mapping_pairs.append((None, j - 1))
            j -= 1

    aligned_reference.reverse()
    aligned_target.reverse()
    mapping_pairs.reverse()

    ref_to_target = {}
    target_to_ref = {}

    for ref_idx, target_idx in mapping_pairs:
        if ref_idx is not None:
            ref_to_target[ref_idx] = target_idx
        if target_idx is not None:
            target_to_ref[target_idx] = ref_idx

    return {
        "score": dp[n][m],
        "aligned_reference": "".join(aligned_reference),
        "aligned_target": "".join(aligned_target),
        "ref_to_target": ref_to_target,
        "target_to_ref": target_to_ref,
        "mapping_pairs": mapping_pairs
    }


# ============================================================
# GLOBAL ALIGNMENT STATISTICS
# 功能：
# 1. Lyrics / ASR Mapping 覆蓋率
# 2. Character Exact Match Rate
# 3. 僅描述對齊狀況，不等同 Ground Truth Accuracy
# ============================================================

def evaluate_real_alignment(reference, target, mapping):
    mapped_pairs = [
        (ref_idx, target_idx)
        for ref_idx, target_idx in mapping.items()
        if target_idx is not None
    ]

    exact_matches = sum(
        1 for ref_idx, target_idx in mapped_pairs
        if reference[ref_idx] == target[target_idx]
    )

    mapped_target_positions = {target_idx for _, target_idx in mapped_pairs}

    return {
        "lyrics_coverage": len(mapped_pairs) / len(reference) if reference else 0.0,
        "ars_coverage": len(mapped_target_positions) / len(target) if target else 0.0,
        "exact_matches": exact_matches,
        "mapped_pairs": len(mapped_pairs),
        "exact_rate": exact_matches / len(mapped_pairs) if mapped_pairs else 0.0
    }


# ============================================================
# SEGMENT PROJECTION
# 功能：
# 1. Character Mapping → W ↔ L Segment
# 2. Segment Boundary 只在 DP 完成後使用
# 3. 支援 1↔1、1↔N、N↔1
# ============================================================

def build_position_lookup(segments, sequence_length):
    lookup = [None] * sequence_length 

    for segment_index, segment in enumerate(segments):
        for pos in range(segment["start"], segment["end"]):
            lookup[pos] = segment_index

    return lookup


def project_mapping_to_segments(mapping, lyrics_segments, ars_segments, lyrics_length, ars_length):
    l_lookup = build_position_lookup(lyrics_segments, lyrics_length)
    w_lookup = build_position_lookup(ars_segments, ars_length)

    w_to_l = defaultdict(Counter)
    l_to_w = defaultdict(Counter)

    for ref_idx, target_idx in mapping.items():
        if target_idx is None:
            continue
        if ref_idx >= lyrics_length or target_idx >= ars_length:
            continue

        l_index = l_lookup[ref_idx]
        w_index = w_lookup[target_idx]

        if l_index is None or w_index is None:
            continue

        w_to_l[w_index][l_index] += 1
        l_to_w[l_index][w_index] += 1

    return w_to_l, l_to_w


# ============================================================
# W SEGMENT COVERAGE
# 功能：
# 1. 計算每個 W 有多少字元被 Global DP 對到 Lyrics
# 2. Coverage 太低代表 Global DP 幾乎跳過該 W
# 3. 可作為 Loop Candidate
# ============================================================

def calculate_w_coverage(ars_segments, target_to_ref):
    results = []

    for w_index, segment in enumerate(ars_segments):
        total = segment["end"] - segment["start"]
        mapped = sum(
            1 for target_idx in range(segment["start"], segment["end"])
            if target_to_ref.get(target_idx) is not None
        )

        results.append({
            "w_index": w_index,
            "id": segment["id"],
            "mapped": mapped,
            "total": total,
            "coverage": mapped / total if total else 0.0
        })

    return results


def find_low_coverage_blocks(coverage_results, threshold=0.50):
    low_indices = [
        item["w_index"]
        for item in coverage_results
        if item["coverage"] < threshold
    ]

    if not low_indices:
        return []

    blocks = []
    start = low_indices[0]
    previous = low_indices[0]

    for index in low_indices[1:]:
        if index == previous + 1:
            previous = index
            continue

        blocks.append((start, previous))
        start = index
        previous = index

    blocks.append((start, previous))
    return blocks


# ============================================================
# LOOP CANDIDATE SEARCH
# 功能：
# 1. 將低 Coverage W Block 與整首 Lyrics 搜尋
# 2. Lyrics Candidate 允許連續多個 L
# 3. 同時計算 Roma + Roma Mom
# 4. 最後產生 Combined Score
# ============================================================

def concat_segment_field(segments, start, end, field):
    return "".join(segments[i][field] for i in range(start, end + 1))


def search_loop_lyrics(
    w_start,
    w_end,
    ars_segments,
    lyrics_segments,
    max_lyric_span=6,
    roma_weight=0.5,
    roma_mom_weight=0.5,
    min_length_ratio=0.50,
    max_length_ratio=1.50
):
    block_roma = concat_segment_field(
        ars_segments, w_start, w_end, "roma_sequence"
    )

    block_mom = concat_segment_field(
        ars_segments, w_start, w_end, "roma_mom_sequence"
    )

    candidates = []

    for l_start in range(len(lyrics_segments)):
        max_end = min(len(lyrics_segments), l_start + max_lyric_span)

        for l_end_exclusive in range(l_start + 1, max_end + 1):
            l_end = l_end_exclusive - 1

            lyrics_roma = concat_segment_field(
                lyrics_segments, l_start, l_end, "roma_sequence"
            )

            lyrics_mom = concat_segment_field(
                lyrics_segments, l_start, l_end, "roma_mom_sequence"
            )

            if not block_roma or not lyrics_roma:
                continue

            length_ratio = len(lyrics_roma) / len(block_roma)

            if length_ratio < min_length_ratio or length_ratio > max_length_ratio:
                continue

            roma_score = sequence_similarity(block_roma, lyrics_roma)
            roma_mom_score = sequence_similarity(block_mom, lyrics_mom)

            combined_score = (
                roma_weight * roma_score
                + roma_mom_weight * roma_mom_score
            )

            candidates.append({
                "l_start": l_start,
                "l_end": l_end,
                "length_ratio": length_ratio,
                "roma_score": roma_score,
                "roma_mom_score": roma_mom_score,
                "score": combined_score
            })

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates


# ============================================================
# LOOP DETAIL RECOVERY
# 功能：
# 1. 找到 W Block ↔ Lyrics Span 後
# 2. 再以 Roma 做一次局部 Global DP
# 3. 恢復 W5→L1、W6→L2 這種細部關係
# ============================================================

def localize_segments(segments, start, end, field):
    localized = []
    cursor = 0

    for i in range(start, end + 1):
        segment = dict(segments[i])
        sequence = segment[field]

        segment["start"] = cursor
        segment["end"] = cursor + len(sequence)
        segment["sequence"] = sequence

        localized.append(segment)
        cursor += len(sequence)

    return localized, cursor


def recover_loop_detail(candidate, w_start, w_end, ars_segments, lyrics_segments):
    l_start = candidate["l_start"]
    l_end = candidate["l_end"]

    local_l, l_length = localize_segments(
        lyrics_segments, l_start, l_end, "roma_sequence"
    )

    local_w, w_length = localize_segments(
        ars_segments, w_start, w_end, "roma_sequence"
    )

    lyrics_roma = "".join(item["sequence"] for item in local_l)
    asr_roma = "".join(item["sequence"] for item in local_w)

    result = global_align(lyrics_roma, asr_roma)

    w_to_l, l_to_w = project_mapping_to_segments(
        result["ref_to_target"],
        local_l,
        local_w,
        l_length,
        w_length
    )

    return {
        "result": result,
        "lyrics_segments": local_l,
        "ars_segments": local_w,
        "w_to_l": w_to_l,
        "l_to_w": l_to_w
    }


def calculate_w_alignment_quality(asr_segments, target_to_ref, lyrics_sequence, asr_sequence):
    results = []

    for w_index, segment in enumerate(asr_segments):
        start = segment["start"]
        end = segment["end"]
        total = end - start

        mapped = 0
        exact = 0

        for target_idx in range(start, end):
            ref_idx = target_to_ref.get(target_idx)

            # ASR character 對到 Gap
            if ref_idx is None:
                continue

            mapped += 1

            # 有對到 Lyrics，而且 character 真的相同
            if 0 <= ref_idx < len(lyrics_sequence) and asr_sequence[target_idx] == lyrics_sequence[ref_idx]:
                exact += 1

        coverage = mapped / total if total else 0.0
        exact_ratio = exact / total if total else 0.0
        exact_rate = exact / mapped if mapped else 0.0

        results.append({
            "w_index": w_index,
            "id": segment["id"],
            "total": total,
            "mapped": mapped,
            "exact": exact,
            "coverage": coverage,
            "exact_ratio": exact_ratio,  # Exact Match / 整個 W 長度
            "exact_rate": exact_rate,    # Exact Match / 已 Mapping 字元
        })

    return results


def filter_w_to_l(
    w_to_l,
    quality_results,
    min_coverage=0.50,
    min_exact_ratio=0.35,
    min_pair_share=0.15,
    min_pair_chars=3,
):
    quality_map = {item["w_index"]: item for item in quality_results}

    filtered = defaultdict(Counter)
    rejected = {}

    for w_index, links in w_to_l.items():
        quality = quality_map[w_index]

        # ------------------------------------------------
        # 第一層：判斷整個 Whisper Segment 是不是髒資料
        # ------------------------------------------------
        if quality["coverage"] < min_coverage or quality["exact_ratio"] < min_exact_ratio:
            rejected[w_index] = {
                "reason": "LOW_ALIGNMENT_QUALITY",
                **quality,
            }
            continue

        # ------------------------------------------------
        # 第二層：移除少量 accidental mapping
        # ------------------------------------------------
        total_mapped = sum(links.values())

        for l_index, count in links.items():
            pair_share = count / total_mapped if total_mapped else 0.0

            if count < min_pair_chars or pair_share < min_pair_share:
                continue

            filtered[w_index][l_index] = count

    return filtered, rejected