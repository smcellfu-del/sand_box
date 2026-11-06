import json
import os
from datetime import datetime
from sandbox.new_test_dp.file_process import open_file as of
from sandbox.new_test_dp import base_algorithm as ba

def map_boundaries_to_aligned(aligned_seq, boundaries):
    """將原始累積字元邊界 (boundaries) 映射到帶有 Gap (-) 的對齊字串索引位置"""
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


def generate_alignment_json(folder_name, aligned_lyrics, lyrics_boundaries, aligned_whisper, whisper_boundaries, match=1, mismatch=-1, gap=-2):
    """
    將對齊結果轉換為指定的 JSON 結構
    """
    lyrics_ranges = map_boundaries_to_aligned(aligned_lyrics, lyrics_boundaries)
    whisper_ranges = map_boundaries_to_aligned(aligned_whisper, whisper_boundaries)
    
    segments = []
    
    for l_idx, (l_start, l_end) in enumerate(lyrics_ranges):
        # 尋找與當前歌詞區間有重疊的 Whisper 區塊
        matched_whisper_blocks = []
        for w_idx, (w_start, w_end) in enumerate(whisper_ranges):
            if l_start < w_end and l_end > w_start:
                matched_whisper_blocks.append(w_idx + 1) # 1-based index
                
        chunk_l = aligned_lyrics[l_start:l_end]
        chunk_w = aligned_whisper[l_start:l_end]
        
        segment_data = {
            "line_id": l_idx + 1,
            "lyrics_aligned": chunk_l,
            "whisper_aligned": chunk_w,
            "whisper_blocks": matched_whisper_blocks
        }
        segments.append(segment_data)
        
    result_json = {
        "song_name": folder_name,
        "alignment_params": {
            "match": match,
            "mismatch": mismatch,
            "gap": gap
        },
        "segments": segments
    }
    
    return result_json


