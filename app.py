import asyncio
import aiohttp
import re
from pathlib import Path

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

CONCURRENT_DOWNLOADS = 10

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


async def download_file(session, semaphore, page_url):
    async with semaphore:
        try:
            real_url = await get_real_download_url(session, page_url)

            if not real_url:
                return

            async with session.get(real_url) as response:
                if response.status != 200:
                    print(f"[FAIL DOWNLOAD] {page_url}")
                    return

                filename = extract_filename(
                    response,
                    real_url.split("/")[-1]
                )

                filepath = DOWNLOAD_DIR / filename

                if filepath.exists():
                    print(f"[SKIP] {filename}")
                    return

                with open(filepath, "wb") as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        f.write(chunk)

                print(f"[OK] {filename}")

        except Exception as e:
            print(f"[ERROR] {page_url} -> {e}")


async def main():
    try:
        with open("url.txt", "r", encoding="utf-8") as f:
            links = [x.strip() for x in f if x.strip()]
    except FileNotFoundError:
        print("[ERROR] url.txt not found.")
        return

    semaphore = asyncio.Semaphore(CONCURRENT_DOWNLOADS)

    timeout = aiohttp.ClientTimeout(total=None)

    connector = aiohttp.TCPConnector(limit=0)

    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0 Safari/537.36"
            )
        }
    ) as session:

        tasks = [
            download_file(session, semaphore, url)
            for url in links
        ]

        await asyncio.gather(*tasks)

    print("[SUCCESS] Download completed.")


if __name__ == "__main__":
    asyncio.run(main())