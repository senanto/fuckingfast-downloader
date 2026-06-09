import asyncio
import aiohttp
import re
from pathlib import Path
from tqdm import tqdm

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

CONCURRENT_DOWNLOADS = 3
CHUNK_SIZE = 1024 * 1024

DOWNLOAD_URL_PATTERN = re.compile(
    r'window\.open\("([^"]*dl\.fuckingfast\.co/dl/[^"]+)"\)'
)


def extract_filename(response, fallback):
    cd = response.headers.get("Content-Disposition", "")

    match = re.search(
        r'filename\*=UTF-8\'\'([^;]+)|filename="?([^"]+)"?',
        cd,
        re.IGNORECASE
    )

    if match:
        return match.group(1) or match.group(2)

    return fallback


async def get_real_download_url(session, page_url):
    try:
        async with session.get(page_url) as response:
            if response.status != 200:
                print(f"[FAIL PAGE] {page_url}")
                return None

            html = await response.text()
            match = DOWNLOAD_URL_PATTERN.search(html)

            if not match:
                print(f"[NO DOWNLOAD URL] {page_url}")
                return None

            return match.group(1)

    except Exception as e:
        print(f"[ERROR PAGE] {page_url} -> {e}")
        return None


async def download_with_resume(session, url, filepath, position):
    downloaded = filepath.stat().st_size if filepath.exists() else 0

    headers = {}
    if downloaded > 0:
        headers["Range"] = f"bytes={downloaded}-"

    retry = 0

    while retry < 5:
        try:
            async with session.get(url, headers=headers) as response:

                if response.status not in (200, 206):
                    retry += 1
                    await asyncio.sleep(2)
                    continue

                total = response.headers.get("Content-Length")
                total = int(total) + downloaded if total else None

                progress = tqdm(
                    total=total,
                    initial=downloaded,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    position=position,
                    desc=filepath.name[:30],
                    leave=True
                )

                mode = "ab" if downloaded else "wb"

                with open(filepath, mode) as f:
                    async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        progress.update(len(chunk))

                progress.close()
                print(f"[OK] {filepath.name}")
                return

        except Exception as e:
            retry += 1
            print(f"[RETRY {retry}] {filepath.name} -> {e}")
            await asyncio.sleep(2)

    print(f"[FAILED] {filepath.name}")


async def download_file(session, semaphore, page_url, position):
    async with semaphore:
        try:
            real_url = await get_real_download_url(session, page_url)
            if not real_url:
                return

            filename = real_url.split("/")[-1].split("?")[0]
            filepath = DOWNLOAD_DIR / filename   # artık direkt .part1 vs neyse o

            await download_with_resume(session, real_url, filepath, position)

        except Exception as e:
            print(f"[ERROR] {page_url} -> {e}")


async def main():
    with open("url.txt", "r", encoding="utf-8") as f:
        links = [x.strip() for x in f if x.strip()]

    semaphore = asyncio.Semaphore(CONCURRENT_DOWNLOADS)

    timeout = aiohttp.ClientTimeout(total=None)
    connector = aiohttp.TCPConnector(limit=0)

    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    ) as session:

        tasks = [
            download_file(session, semaphore, url, i % CONCURRENT_DOWNLOADS)
            for i, url in enumerate(links)
        ]

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
