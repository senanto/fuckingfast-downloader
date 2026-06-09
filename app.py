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


def clean_filename(name: str) -> str:
    return name.split("?")[0].split("#")[0]


def extract_filename(response, fallback):
    cd = response.headers.get("Content-Disposition", "")

    match = re.search(
        r'filename\*=UTF-8\'\'([^;]+)|filename="?([^"]+)"?',
        cd,
        re.IGNORECASE
    )

    if match:
        return clean_filename(match.group(1) or match.group(2))

    return fallback


async def get_real_download_url(session, page_url):
    async with session.get(page_url) as response:
        if response.status != 200:
            return None

        html = await response.text()
        match = DOWNLOAD_URL_PATTERN.search(html)

        return match.group(1) if match else None


def get_local_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


async def smart_download(session, url, filepath, position):
    retry = 0

    while retry < 5:
        local_size = get_local_size(filepath)

        headers = {}
        if local_size > 0:
            headers["Range"] = f"bytes={local_size}-"

        try:
            async with session.get(url, headers=headers) as response:
                accept_range = response.status == 206

                if local_size > 0 and not accept_range:
                    filepath.unlink(missing_ok=True)
                    local_size = 0

                mode = "ab" if local_size > 0 and accept_range else "wb"

                total = response.headers.get("Content-Length")
                total = int(total) + local_size if total else None

                progress = tqdm(
                    total=total,
                    initial=local_size,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    position=position,
                    desc=filepath.name[:30],
                    leave=True
                )

                written = 0

                with open(filepath, mode) as f:
                    async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                        if not chunk:
                            continue

                        f.write(chunk)
                        written += len(chunk)
                        progress.update(len(chunk))

                progress.close()
                final_size = get_local_size(filepath)
                expected = total if total else final_size

                if expected and final_size > expected:
                    filepath.unlink(missing_ok=True)
                    raise Exception("SIZE_MISMATCH")

                print(f"[OK] {filepath.name}")
                return

        except Exception as e:
            retry += 1
            print(f"[RETRY {retry}] {filepath.name} -> {e}")
            await asyncio.sleep(2)

    print(f"[FAILED] {filepath.name}")


async def download_file(session, semaphore, page_url, position):
    async with semaphore:
        real_url = await get_real_download_url(session, page_url)
        if not real_url:
            return

        async with session.get(real_url) as r:
            filename = extract_filename(r, "unknown_file")

        filepath = DOWNLOAD_DIR / filename

        await smart_download(session, real_url, filepath, position)


async def main():
    with open("url.txt", "r", encoding="utf-8") as f:
        links = [x.strip() for x in f if x.strip()]

    semaphore = asyncio.Semaphore(CONCURRENT_DOWNLOADS)

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=None),
        connector=aiohttp.TCPConnector(limit=0),
        headers={"User-Agent": "Mozilla/5.0"}
    ) as session:

        tasks = [
            download_file(session, semaphore, url, i % CONCURRENT_DOWNLOADS)
            for i, url in enumerate(links)
        ]

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
