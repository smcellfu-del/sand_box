from services.ThirdParty.worker.Whisper_ars import Whisper_asr

import json
from pathlib import Path
import subprocess


def prepare_for_whisper(wav_path: Path) -> Path:
    """
    將原始 WAV 轉成 Whisper 適合的格式：
    16kHz / mono / PCM 16-bit
    """
    output_path = wav_path.with_name(
        f"{wav_path.stem}_whisper.wav"
    )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel", "error",
            "-i", str(wav_path),
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            str(output_path),
        ],
        check=True,
    )

    return output_path


# ============================================================
# Whisper 初始化
# ============================================================

print("[1] 開始初始化 Whisper")

whisper_worker = Whisper_asr(
    model_name="medium"
)

print("[2] Whisper 初始化完成")

# ============================================================
# 音訊根目錄
# ============================================================

audio_dir = Path(
    r"G:\我的雲端硬碟\100_song"
)

# ============================================================
# JSON 輸出資料夾
# ============================================================

json_dir = audio_dir / "whisper_json"
json_dir.mkdir(
    parents=True,
    exist_ok=True
)

# ============================================================
# 找 Final Vocal WAV
# ============================================================

wav_files = [
    wav_path
    for wav_path in audio_dir.rglob("*.wav")
    if "final" in wav_path.stem.lower()
    and not wav_path.stem.lower().endswith("_whisper")
]

print(f"總共找到 {len(wav_files)} 個 Final WAV 檔案：\n")

# ============================================================
# Whisper ASR
# ============================================================

for index, wav_path in enumerate(wav_files, start=1):

    song_name = wav_path.parent.name
    output_json = json_dir / f"{song_name}.json"

    # 檢查是否已存在輸出結果，若有則直接跳過
    if output_json.exists():
        print(f"[{index}/{len(wav_files)}] [跳過] {song_name} 已存在對應 JSON")
        continue

    print("\n" + "=" * 80)
    print(f"[{index}/{len(wav_files)}] 開始處理")
    print(f"WAV: {wav_path}")
    print(f"Song: {song_name}")

    print("[1/3] FFmpeg 轉換...")
    whisper_wav = prepare_for_whisper(wav_path)

    print("[2/3] Whisper ASR...")
    segments = whisper_worker.whisper_asr(
        str(whisper_wav)
    )

    print("[3/3] 寫入 JSON...")
    with open(
        output_json,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            segments,
            f,
            ensure_ascii=False,
            indent=4
        )

    print(f"[✔] 完成：{song_name}")

    # 刪掉 Whisper 臨時 WAV
    if whisper_wav.exists():
        whisper_wav.unlink()

    print(f"[→] 準備處理下一首")


print("\n全部 Final Vocal Whisper ASR 完成！")

# python -m sandbox.basic_tool.vocal