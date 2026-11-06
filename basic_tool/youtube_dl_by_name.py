import asyncio
import csv
from pathlib import Path
from services.ThirdParty.worker.YtDlpWorker import YtDlpWorker
# 
name_raw_data = r"C:\Users\kniou\Documents\project_in_1141\fianl\backend\web_crawler\songs_output1.csv"
custom_save_path = Path(r"G:\我的雲端硬碟\a4")

# 初始化 worker
worker = YtDlpWorker(base_dir=custom_save_path)


async def process_song(
    worker: YtDlpWorker,
    artist: str,
    song: str,
    semaphore: asyncio.Semaphore,
):
    """Processes a single song with a concurrency limit."""
    async with semaphore:
        keyword = f"{artist} {song}"

        try:
            print(f"[-] Starting: {keyword}")

            await worker.run(
                keyword=keyword,
                song_name=song,
                output_dir=custom_save_path,
            )
            await asyncio.sleep(5)
        except Exception as e:
            print(f"[❌] Error processing '{keyword}': {e}")


async def main():
    print("正在讀取 CSV 與初始化任務...")
    semaphore = asyncio.Semaphore(1)  # 限制同時執行的任務數量
    tasks = []

    # 使用 utf-8-sig 來避開 Windows CSV 的 BOM 隱形字元
    with open(name_raw_data, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            artist = row.get("Artist_Name", "").strip()
            song = row.get("Song_Name", "").strip()

            # 此處範例為過濾 Vaundy 的歌曲；若要下載所有歌手，可把條件改為 `if artist and song:`
            if artist == "YOASOBI" and song:
                tasks.append(
                    process_song(
                        worker,
                        artist,
                        song,
                        semaphore,
                    )
                )

    print(f"總共載入了 {len(tasks)} 個下載任務，開始執行！")

    if len(tasks) == 0:
        print(
            "[!] 警告：沒有讀取到任何歌曲，請檢查 CSV 欄位名稱是否正確（需包含 Artist_Name 與 Song_Name）。"
        )
        return

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main()) #