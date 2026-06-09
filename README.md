# Fuckingfast.co Downloader

A high-performance async file downloader with resume support, range handling, and multi-download concurrency.

---

## Features

- Async downloading with `aiohttp`
- Multi-threaded style concurrency (async workers)
- Resume support using HTTP Range headers
- Automatic partial file recovery
- Crash-safe `.part` handling via disk-based progress tracking
- Smart retry system (up to 5 attempts per file)
- Progress bars for each active download
- Extracts real filenames from server headers

---

## How It Works

1. Fetches real download links from provided page URLs
2. Extracts filename from `Content-Disposition` header
3. Downloads files using streaming chunks
4. Saves progress directly to disk
5. If interrupted, continues from last byte using HTTP Range
6. Validates download integrity during transfer

---

## Requirements

```bash
pip install aiohttp tqdm
