import csv
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from config.app_config import YoutubeConfig
from services.ThirdParty.API.YoutubeAPI import YoutubeService
YOUTUBE_API_KEY = "AIzaSyADt5EkYwlX3Bz_ptEY5CvGXvesbgb2yIQ"


# ============================================================
# CONFIG
# ============================================================

OUTPUT_DIR = Path(
    r"C:\Users\kniou\Documents\project_in_1141\fianl\backend\web_crawler"
)

JSON_OUTPUT = OUTPUT_DIR / "youtube_videos.json"
CSV_OUTPUT = OUTPUT_DIR / "youtube_videos.csv"


# ============================================================
# YOUTUBE URLS
# ============================================================

YOUTUBE_URLS = [
    "https://youtu.be/i68HdrqOPcE?si=j7D3B49pkANE-GV8",
    "https://youtu.be/H_2jH6XVYU0?si=OFkdmDInuT5KDCVO",
    "https://youtu.be/cMLTX2FClxw?si=5QKB8o8MMxNd0OAy",
    "https://youtu.be/sem3UU-EQJs?si=OfBvhF3t66ulEyBX",
    "https://youtu.be/bPCqpUiUzsI?si=4sHwjxcF5FOsWISB",
    "https://youtu.be/qg80CGlJTWA?si=Ipn0Y-dA2s59jKIR",
    "https://youtu.be/22mOCjkwQjM?si=JrWbsupr3aOrKCLz",
    "https://youtu.be/mtmy_qW01Bo?si=f3c_k1_ISSdQVWxj",
    "https://youtu.be/PZX2npwj6jY?si=a8I51PJNpwcl74KE",

    "https://youtu.be/6h6AQbdTkaE?si=hgZ82fGOR3txVyGt",
    "https://youtu.be/5pbExTvSU0E?si=KPdVqQzPpMgK78Z_",
    "https://youtu.be/pOII6UpF-uQ?si=XmFVhBNoB81zDCtk",

    "https://youtu.be/Gbz2C2gQREI?si=SyIHQOEGxa6v2dqN",
    "https://youtu.be/mufCugmbCpo?si=fsSfUxSCLtVH3hLO",
    "https://youtu.be/DS8IKAtVUOQ?si=06X0sHn247mMNeLd",

    "https://youtu.be/v8UKU1blzQ4?si=Ap7ccxAX44Bt2nHj",
    "https://youtu.be/TGjsIZToTeI?si=aSr06QJbma50_haA",

    "https://youtu.be/b3H5RvRHiYs?si=l1tz0wSpoXupV5Ei",

    "https://youtu.be/S90X8XK0Cs8?si=OkgMVmhN99Md8q8j",
    "https://youtu.be/PDSkFeMVNFs?si=2i1POgPXXfsh7YRv",

    "https://youtu.be/UM9XNpgrqVk?si=Yz-wJ6wL4mMYiBfc",

    "https://youtu.be/7HgJIAUtICU?si=LJhOKwBWd6VQkb0c",
    "https://youtu.be/CKDRnaObMRs?si=9BYxC6hoaEVLQOdV",
]


# ============================================================
# EXTRACT VIDEO ID
# ============================================================

def extract_video_id(url: str) -> str | None:
    """
    支援：

    https://youtu.be/VIDEO_ID
    https://www.youtube.com/watch?v=VIDEO_ID
    https://youtube.com/shorts/VIDEO_ID
    """

    parsed = urlparse(url)

    # --------------------------------------------------------
    # youtu.be/VIDEO_ID
    # --------------------------------------------------------

    if parsed.hostname in ("youtu.be", "www.youtu.be"):

        video_id = parsed.path.lstrip("/")

        return video_id or None

    # --------------------------------------------------------
    # youtube.com
    # --------------------------------------------------------

    if parsed.hostname in (
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
    ):

        # youtube.com/watch?v=...
        if parsed.path == "/watch":

            query = parse_qs(parsed.query)

            return query.get("v", [None])[0]

        # youtube.com/shorts/...
        if parsed.path.startswith("/shorts/"):

            parts = parsed.path.split("/")

            if len(parts) >= 3:
                return parts[2]

        # youtube.com/embed/...
        if parsed.path.startswith("/embed/"):

            parts = parsed.path.split("/")

            if len(parts) >= 3:
                return parts[2]

    return None


# ============================================================
# EXPORT JSON
# ============================================================

def save_json(videos: list[dict]):

    with JSON_OUTPUT.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            videos,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print(f"[JSON] Saved -> {JSON_OUTPUT}")


# ============================================================
# EXPORT CSV
# ============================================================

def save_csv(videos: list[dict]):

    if not videos:
        return

    columns = [
        "ytid",
        "url",
        "oname",
        "odes",
        "channel_id",
        "channel_title",
        "duration_ms",
        "view_count",
        "img_path",
        "published_at",
    ]

    with CSV_OUTPUT.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=columns,
            extrasaction="ignore",
        )

        writer.writeheader()

        for video in videos:
            writer.writerow(video)

    print(f"[CSV ] Saved -> {CSV_OUTPUT}")


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("YOUTUBE VIDEO EXPORT")
    print("=" * 80)

    # --------------------------------------------------------
    # 建立 YoutubeService
    # --------------------------------------------------------

    config = YoutubeConfig(YOUTUBE_API_KEY)

    youtube = YoutubeService(config)

    # --------------------------------------------------------
    # URL -> Video ID
    # --------------------------------------------------------

    video_ids = []
    url_map = {}

    for url in YOUTUBE_URLS:

        video_id = extract_video_id(url)

        if not video_id:

            print(f"[INVALID URL] {url}")
            continue

        print(
            f"[URL] {video_id} "
            f"<- {url}"
        )

        video_ids.append(video_id)

        # 保留原始 URL
        url_map[video_id] = url

    # 去除重複 ID，同時保留原順序
    video_ids = list(dict.fromkeys(video_ids))

    print()
    print(f"Valid video IDs : {len(video_ids)}")

    # --------------------------------------------------------
    # YouTube API
    #
    # YoutubeService 本身會：
    # - 每 50 個 ID 一批
    # - 呼叫 videos.list
    # - normalize
    # --------------------------------------------------------

    video_map = youtube.get_videos_by_ids(video_ids)

    # --------------------------------------------------------
    # 按照輸入 URL 的順序整理
    # --------------------------------------------------------

    videos = []

    for video_id in video_ids:

        video = video_map.get(video_id)

        if video is None:

            print(
                f"[NOT FOUND] "
                f"{video_id}"
            )

            continue

        # copy 避免直接修改 YoutubeService 回傳物件
        video = dict(video)

        # 把原始 URL 也存起來
        video["url"] = url_map.get(video_id)

        videos.append(video)

        print(
            f"[OK] "
            f"{video_id:<12} "
            f"{video.get('oname')}"
        )

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_json(videos)
    save_csv(videos)

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("FINISHED")
    print("=" * 80)

    print(f"Input URLs : {len(YOUTUBE_URLS)}")
    print(f"Valid IDs  : {len(video_ids)}")
    print(f"API Videos : {len(video_map)}")
    print(f"Exported   : {len(videos)}")

    print("=" * 80)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main() 