#!/usr/bin/env python3
"""
YouTube Live HLS URL Extractor - Standalone GitHub Version
Extracts m3u8 URLs from YouTube live streams
Runs on GitHub Actions (uses GitHub's non-blocked IPs)
Outputs raw m3u8 URLs that can be played directly
"""

import requests
import json
import re
import os
import sys
from datetime import datetime, timezone

CHANNELS_FILE = "channels.json"
OUTPUT_FILE = "streams.json"
M3U_FILE = "youtube.m3u"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}


def extract_m3u8_from_html(html_content):
    """Extract m3u8 URL from YouTube page HTML"""

    # Method 1: Look for hlsManifestUrl in ytInitialPlayerResponse
    patterns = [
        r'"hlsManifestUrl"\s*:\s*"([^"]+)"',
        r'hlsManifestUrl["\s:]+([^"]+\.m3u8[^"]*)',
        r'(https://manifest\.googlevideo\.com/api/manifest/hls_variant[^"\\]+)',
        r'(https://manifest\.googlevideo\.com/api/manifest/hls_playlist[^"\\]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, html_content)
        if match:
            url = match.group(1)
            url = url.replace("\\u0026", "&").replace("\\/", "/").replace("%2C", ",")
            return url

    # Method 2: Brute search for m3u8
    if ".m3u8" in html_content:
        end = html_content.find(".m3u8") + 5
        tuner = 100
        while tuner < 600:
            chunk = html_content[end - tuner : end]
            if "https://" in chunk:
                start = chunk.find("https://")
                url = chunk[start:]
                url = (
                    url.replace("\\u0026", "&").replace("\\/", "/").replace("%2C", ",")
                )
                if "googlevideo.com" in url or "youtube.com" in url:
                    return url
            tuner += 20

    return None


def get_video_id(url):
    """Extract video ID from YouTube URL"""
    patterns = [
        r"(?:v=|/v/|youtu\.be/|/embed/)([a-zA-Z0-9_-]{11})",
        r"([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_stream_url(youtube_url):
    """Extract HLS stream URL from a YouTube video/channel URL"""
    try:
        # Handle channel URLs - append /live
        if "/channel/" in youtube_url or "/c/" in youtube_url or "/@" in youtube_url:
            if not youtube_url.endswith("/live"):
                youtube_url = youtube_url.rstrip("/") + "/live"

        response = requests.get(youtube_url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        m3u8_url = extract_m3u8_from_html(response.text)

        if m3u8_url:
            return {
                "success": True,
                "url": m3u8_url,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            # Check if stream is live
            if (
                '"isLive":true' in response.text
                or '"isLiveContent":true' in response.text
            ):
                return {
                    "success": False,
                    "error": "Stream is live but couldn't extract m3u8 URL",
                    "extracted_at": datetime.now(timezone.utc).isoformat(),
                }
            else:
                return {
                    "success": False,
                    "error": "Not a live stream or stream offline",
                    "extracted_at": datetime.now(timezone.utc).isoformat(),
                }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": str(e),
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }


def load_channels():
    """Load channel list from JSON file"""
    if os.path.exists(CHANNELS_FILE):
        with open(CHANNELS_FILE, "r") as f:
            return json.load(f)
    return []


def save_streams(streams):
    """Save extracted streams to JSON file"""
    output = {"updated_at": datetime.now(timezone.utc).isoformat(), "streams": streams}
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)


def generate_m3u(streams):
    """Generate M3U playlist file"""
    lines = ["#EXTM3U"]
    lines.append("")
    lines.append("# YouTube Live Streams - Auto-extracted by GitHub Actions")
    lines.append(f"# Last updated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("# URLs expire in ~6-12 hours, playlist auto-refreshes every 2 hours")
    lines.append("")

    for stream in streams:
        if stream.get("stream", {}).get("success"):
            group = stream.get("group", "YouTube")
            logo = stream.get("logo", "")
            tvg_id = stream.get("id", "")
            name = stream.get("name", "Unknown")
            url = stream["stream"]["url"]

            extinf = f'#EXTINF:-1 group-title="{group}" tvg-logo="{logo}" tvg-id="{tvg_id}", {name}'
            lines.append(extinf)
            lines.append(url)
            lines.append("")

    with open(M3U_FILE, "w") as f:
        f.write("\n".join(lines))


def create_default_channels():
    """Create default channels.json with popular live streams"""
    default_channels = [
        {
            "id": "lofi",
            "name": "Lofi Girl",
            "url": "https://www.youtube.com/watch?v=jfKfPfyJRdk",
            "logo": "https://yt3.googleusercontent.com/UgRgQc3RPWP-qJRKB5zuyG6T8VL3G1bEkjvIbQUyhTyfkQnw3aiX8f_0uvSCEbxWHxLJkzdqb4Y=s176-c-k-c0x00ffffff-no-rj",
            "group": "Music",
        },
        {
            "id": "dw_news",
            "name": "DW News",
            "url": "https://www.youtube.com/watch?v=GE_SfNVNyqk",
            "logo": "https://yt3.googleusercontent.com/ytc/AKedOLSGYwgujx1VgMYEpdurTfh8NRmOehOXf16DeMKoDfw=s176-c-k-c0x00ffffff-no-rj",
            "group": "News",
        },
        {
            "id": "france24_en",
            "name": "France 24 English",
            "url": "https://www.youtube.com/watch?v=h3MuIUNCCzI",
            "logo": "https://yt3.googleusercontent.com/ytc/AKedOLSc0mBH1gdDzNnWTdKdLdGbxyPiGN8_9Jv1C=s176-c-k-c0x00ffffff-no-rj",
            "group": "News",
        },
        {
            "id": "aljazeera",
            "name": "Al Jazeera English",
            "url": "https://www.youtube.com/watch?v=gCNeDWCI0vo",
            "logo": "https://yt3.googleusercontent.com/ytc/AKedOLQuzkdeUxIhS3KWZrYcDf4F8k2VC6SHZt2HlyzCM_c=s176-c-k-c0x00ffffff-no-rj",
            "group": "News",
        },
        {
            "id": "sky_news",
            "name": "Sky News",
            "url": "https://www.youtube.com/watch?v=9Auq9mYxFEE",
            "logo": "https://yt3.googleusercontent.com/E96qzkAoX81DQs7wqRHR4rNk1esa4quBPzda2QRzImlhoHOVgRdAN8o-S0Rb_hpygo_n4LdhwTE=s176-c-k-c0x00ffffff-no-rj",
            "group": "News",
        },
        {
            "id": "abc_au",
            "name": "ABC News Australia",
            "url": "https://www.youtube.com/watch?v=W1ilCy6XrmI",
            "logo": "https://yt3.googleusercontent.com/ytc/AKedOLQxmdPqHEhqCkYPjHTE0kxTnTbUfhTT9gFvMQN0=s176-c-k-c0x00ffffff-no-rj",
            "group": "News",
        },
        {
            "id": "nasa",
            "name": "NASA Live",
            "url": "https://www.youtube.com/watch?v=21X5lGlDOfg",
            "logo": "https://yt3.googleusercontent.com/ytc/AKedOLSzgVD89TWJFTxdXC8LZmh7xVu7BYI1D7-2jw=s176-c-k-c0x00ffffff-no-rj",
            "group": "Science",
        },
        {
            "id": "bloomberg",
            "name": "Bloomberg Global",
            "url": "https://www.youtube.com/watch?v=dp8PhLsUcFE",
            "logo": "https://yt3.googleusercontent.com/ytc/AKedOLRc5M7A22VxEBZj-9aF4H_WM58Zt_xhtmE1q=s176-c-k-c0x00ffffff-no-rj",
            "group": "Business",
        },
    ]

    with open(CHANNELS_FILE, "w") as f:
        json.dump(default_channels, f, indent=2)

    return default_channels


def main():
    print("=" * 60)
    print("YouTube Live HLS URL Extractor")
    print("Running on GitHub Actions - Using GitHub's IP")
    print("=" * 60)

    # Load or create channels
    channels = load_channels()

    if not channels:
        print("\nNo channels.json found. Creating default channels...")
        channels = create_default_channels()

    print(f"\nProcessing {len(channels)} channels...")
    print("-" * 60)

    results = []
    success_count = 0

    for i, channel in enumerate(channels, 1):
        print(f"\n[{i}/{len(channels)}] {channel['name']}")
        print(f"    URL: {channel['url']}")

        stream_info = extract_stream_url(channel["url"])

        if stream_info["success"]:
            success_count += 1
            print(f"    ✓ SUCCESS - Found HLS stream")
            print(f"    ✓ m3u8: {stream_info['url'][:70]}...")
        else:
            print(f"    ✗ FAILED - {stream_info.get('error', 'Unknown error')}")

        results.append({**channel, "stream": stream_info})

    # Save results
    print("\n" + "-" * 60)
    save_streams(results)
    print(f"✓ Saved streams to {OUTPUT_FILE}")

    # Generate M3U
    generate_m3u(results)
    print(f"✓ Generated M3U playlist: {M3U_FILE}")

    # Summary
    print("\n" + "=" * 60)
    print(f"SUMMARY: {success_count}/{len(results)} streams extracted successfully")
    print("=" * 60)

    if success_count > 0:
        print("\nTo use the playlist:")
        print(
            f"  Raw URL: https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/{M3U_FILE}"
        )
        print("\nThe playlist auto-updates every 2 hours via GitHub Actions")

    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
