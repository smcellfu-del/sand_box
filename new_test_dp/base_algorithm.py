#--------------------------------------------------------------
#基礎 DP 區
#--------------------------------------------------------------

def levenshtein_distance(s1, s2):
  
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    
    # 初始化邊界條件
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
        
    # 動態規劃填表
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                cost = 0
            else:
                cost = 1
                
            dp[i][j] = min(
                dp[i - 1][j] + 1,      # 刪除
                dp[i][j - 1] + 1,      # 插入
                dp[i - 1][j - 1] + cost # 替換
            )
            
    return dp[m][n]

def edit_distance_similarity(s1, s2):
    """計算 0 到 1 之間的相似度"""
    max_len = max(len(s1), len(s2))
    
    # 避免除以零的情況（如果兩個字串都是空的）
    if max_len == 0:
        return 1.0
        
    distance = levenshtein_distance(s1, s2)
    
    # 相似度公式：1 - (編輯距離 / 兩者最大長度)
    similarity = 1.0 - (distance / max_len)
    return similarity

def needleman_wunsch(seq1: str, seq2: str, match: int = 1, mismatch: int = -1, gap: int = -1) -> tuple[str, str, int]:
    """Return the best global alignment and its score."""
    rows = len(seq1) + 1
    cols = len(seq2) + 1
    scores = [[0] * cols for _ in range(rows)]

    for i in range(1, rows):
        scores[i][0] = scores[i - 1][0] + gap
    for j in range(1, cols):
        scores[0][j] = scores[0][j - 1] + gap

    for i in range(1, rows):
        for j in range(1, cols):
            diagonal = scores[i - 1][j - 1] + (
                match if seq1[i - 1] == seq2[j - 1] else mismatch
            )
            up = scores[i - 1][j] + gap
            left = scores[i][j - 1] + gap
            scores[i][j] = max(diagonal, up, left)

    aligned1 = []
    aligned2 = []
    i, j = len(seq1), len(seq2)

    while i > 0 or j > 0:
        if i > 0 and j > 0:
            pair_score = match if seq1[i - 1] == seq2[j - 1] else mismatch
            if scores[i][j] == scores[i - 1][j - 1] + pair_score:
                aligned1.append(seq1[i - 1])
                aligned2.append(seq2[j - 1])
                i -= 1
                j -= 1
                continue

        if i > 0 and scores[i][j] == scores[i - 1][j] + gap:
            aligned1.append(seq1[i - 1])
            aligned2.append("-")
            i -= 1
        else:
            aligned1.append("-")
            aligned2.append(seq2[j - 1])
            j -= 1

    aligned1.reverse()
    aligned2.reverse()

    # 字串輸入：維持原本的輸出方式
    if isinstance(seq1, str) and isinstance(seq2, str):
        return "".join(aligned1), "".join(aligned2), scores[-1][-1]

    # Token List 輸入：保留每個 Token
    return aligned1, aligned2, scores[-1][-1]





def semi_global_align_segment(
    lyrics,
    whisper_segment,
    match=1,
    mismatch=-1,
    gap=-2,
    *,
    return_details=False,
):
    """Align ALL of whisper_segment to any substring of lyrics.

    Returns (aligned_lyrics, aligned_whisper, score).
    With return_details=True, returns a fourth value with coordinates,
    operation counts, and an aligned operation trace.

    DP uses O(len(lyrics) * len(whisper_segment)) trace bytes, and only
    O(len(lyrics)) score memory (not a full Python-int DP matrix).
    """
    if isinstance(lyrics, str) != isinstance(whisper_segment, str):
        raise TypeError("lyrics and whisper_segment must both be strings or both be token sequences")
    if not lyrics or not whisper_segment:
        raise ValueError("lyrics and whisper_segment cannot be empty")
    if gap > 0:
        raise ValueError("gap must be <= 0")

    n = len(lyrics)
    m = len(whisper_segment)

    # Direction codes: 1 diagonal, 2 consume Whisper (Lyrics gap),
    # 3 consume Lyrics (Whisper gap).
    trace = [bytearray(n + 1) for _ in range(m + 1)]

    # D(0, j) = 0: free Lyrics prefix.
    previous = [0] * (n + 1)

    for i in range(1, m + 1):
        current = [0] * (n + 1)
        current[0] = i * gap            # Whisper prefix is NOT free.
        trace[i][0] = 2
        w = whisper_segment[i - 1]

        for j in range(1, n + 1):
            diagonal = previous[j - 1] + (match if w == lyrics[j - 1] else mismatch)
            up = previous[j] + gap
            left = current[j - 1] + gap

            # Deterministic tie break: diagonal > up > left.
            if diagonal >= up and diagonal >= left:
                current[j] = diagonal
                trace[i][j] = 1
            elif up >= left:
                current[j] = up
                trace[i][j] = 2
            else:
                current[j] = left
                trace[i][j] = 3

        previous = current

    # D(m, j): Whisper fully consumed; Lyrics suffix is free.
    # In ties, max() selects the leftmost ending coordinate.
    lyrics_end = max(range(n + 1), key=previous.__getitem__)
    score = previous[lyrics_end]
    i, j = m, lyrics_end

    l_aligned = []
    w_aligned = []
    operations = []

    # Stop as soon as every Whisper token is consumed.
    # Any Lyrics prefix before this point is ignored for free.
    while i > 0:
        direction = trace[i][j]
        if direction == 1:
            l = lyrics[j - 1]
            w = whisper_segment[i - 1]
            l_aligned.append(l)
            w_aligned.append(w)
            operations.append("MATCH" if l == w else "SUB")
            i -= 1
            j -= 1
        elif direction == 2:
            l_aligned.append("-")
            w_aligned.append(whisper_segment[i - 1])
            operations.append("INSERT")  # extra Whisper token
            i -= 1
        elif direction == 3:
            l_aligned.append(lyrics[j - 1])
            w_aligned.append("-")
            operations.append("DELETE")  # Lyrics token not found in Whisper
            j -= 1
        else:
            raise RuntimeError(f"unexpected traceback direction {direction} at {(i, j)}")

    lyrics_start = j
    l_aligned.reverse()
    w_aligned.reverse()
    operations.reverse()

    counts = {op: operations.count(op) for op in ("MATCH", "SUB", "INSERT", "DELETE")}

    if isinstance(lyrics, str):
        output_lyrics = "".join(l_aligned)
        output_whisper = "".join(w_aligned)
    else:
        output_lyrics = l_aligned
        output_whisper = w_aligned

    if not return_details:
        return output_lyrics, output_whisper, score

    details = {
        "lyrics_start": lyrics_start,
        "lyrics_end": lyrics_end,
        "whisper_length": m,
        "normalized_score": score / (m * match) if match > 0 else None,
        "counts": counts,
        "operations": operations,
    }
    return output_lyrics, output_whisper, score, details\


import json
#--------------------------------------------------------------
#工具區
#--------------------------------------------------------------


def map_boundaries_to_aligned(aligned_seq, boundaries):
    """
    將原始累積字元邊界 (boundaries) 映射到帶有 Gap (-) 的對齊字串索引位置
    回傳每個區塊的 (start_idx, end_idx) 列表
    """
    aligned_ranges = []
    orig_count = 0
    align_idx = 0
    prev_idx = 0
    b_idx = 0
    
    while align_idx < len(aligned_seq) and b_idx < len(boundaries):
        if aligned_seq[align_idx] != "-":
            orig_count += 1
        align_idx += 1
        
        if orig_count == boundaries[b_idx]:
            aligned_ranges.append((prev_idx, align_idx))
            prev_idx = align_idx
            b_idx += 1
            
    while len(aligned_ranges) < len(boundaries):
        aligned_ranges.append((prev_idx, len(aligned_seq)))
        prev_idx = len(aligned_seq)
        
    return aligned_ranges


def print_lyrics_driven_alignment_with_whisper_mapping(
    aligned_lyrics, 
    lyrics_boundaries, 
    aligned_whisper, 
    whisper_boundaries, 
    width=50
):
    """
    以 Lyrics 座標為主的印出函式，並在標題顯示對應的 Whisper 區塊編號
    """
    # 1. 取得各自在對齊字串中的 (start, end) 範圍
    lyrics_ranges = map_boundaries_to_aligned(aligned_lyrics, lyrics_boundaries)
    whisper_ranges = map_boundaries_to_aligned(aligned_whisper, whisper_boundaries)
    
    print("=" * 70)
    print(" 歌詞與辨識結果對齊檢視（顯示對應 Whisper 區塊編號） ")
    print("=" * 70)
    
    name1, name2 = "lyrics", "whisper"
    max_name_len = max(len(name1), len(name2))
    
    for l_idx, (l_start, l_end) in enumerate(lyrics_ranges):
        # 尋找與當前歌詞區間 (l_start, l_end) 有重疊的 Whisper 區塊
        matched_whisper_blocks = []
        for w_idx, (w_start, w_end) in enumerate(whisper_ranges):
            # 判斷區間重疊條件：l_start < w_end 且 l_end > w_start
            if l_start < w_end and l_end > w_start:
                matched_whisper_blocks.append(w_idx + 1) # 1-based index
                
        # 格式化 Whisper 區塊顯示文字
        if not matched_whisper_blocks:
            w_info = "無對應區塊"
        elif len(matched_whisper_blocks) == 1:
            w_info = f"whisper {matched_whisper_blocks[0]} 區塊"
        else:
            w_info = f"whisper {matched_whisper_blocks[0]}~{matched_whisper_blocks[-1]} 區塊"
            
        # 切出對齊的子字串
        chunk_l = aligned_lyrics[l_start:l_end]
        chunk_w = aligned_whisper[l_start:l_end]
        
        print(f"\n--- 第 {l_idx + 1} 句歌詞區塊 (對應 {w_info}) ---")
        
        # 處理超過寬度時自動換行
        max_len = len(chunk_l)
        for sub_i in range(0, max_len, width):
            sub_l = chunk_l[sub_i : sub_i + width]
            sub_w = chunk_w[sub_i : sub_i + width]
            
            match_line = "".join("|" if c1 == c2 and c1 != "-" else " " for c1, c2 in zip(sub_l, sub_w))
            
            s1_str = " ".join(sub_l)
            s2_str = " ".join(sub_w)
            m_str = " ".join(match_line)
            
            print(f"{name1:<{max_name_len}} : {s1_str}")
            print(f"{'':<{max_name_len}}   {m_str}")
            print(f"{name2:<{max_name_len}} : {s2_str}")



# python -m sandbox.new_test_dp.base_algorithm