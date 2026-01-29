#!/usr/bin/env python3
"""
YouTube Live HLS URL Extractor - Standalone GitHub Version
Extracts m3u8 URLs from YouTube live streams using yt-dlp
Runs on GitHub Actions (uses GitHub's non-blocked IPs)
Outputs raw m3u8 URLs that can be played directly
"""

import subprocess
import json
import os
import sys
from datetime import datetime, timezone

CHANNELS_FILE = "channels.json"
OUTPUT_FILE = "streams.json"
M3U_FILE = "youtube.m3u"
COOKIES_FILE = "cookies.txt"


def get_cookies_args():
    """Return cookies arguments if cookies.txt exists"""
    if os.path.exists(COOKIES_FILE):
        return ["--cookies", COOKIES_FILE]
    return []


def extract_stream_url(youtube_url):
    """Extract HLS stream URL using yt-dlp"""
    try:
        # Handle channel URLs - append /live
        if "/channel/" in youtube_url or "/c/" in youtube_url or "/@" in youtube_url:
            if not youtube_url.endswith("/live"):
                youtube_url = youtube_url.rstrip("/") + "/live"

        cookies_args = get_cookies_args()

        # Use yt-dlp to extract the HLS manifest URL
        cmd = [
            "yt-dlp",
            "--no-download",
            "--print",
            "%(manifest_url)s",
            "--force-ipv4",
            *cookies_args,
            youtube_url,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0 and result.stdout.strip():
            manifest_url = result.stdout.strip()
            if manifest_url and manifest_url != "NA" and "manifest" in manifest_url:
                return {
                    "success": True,
                    "url": manifest_url,
                    "extracted_at": datetime.now(timezone.utc).isoformat(),
                }

        # Try alternative: get direct URL for format 95 (1080p) or best available
        cmd_alt = [
            "yt-dlp",
            "-f",
            "95/94/93/92/91/best",
            "--no-download",
            "--print",
            "%(url)s",
            "--force-ipv4",
            *cookies_args,
            youtube_url,
        ]

        result_alt = subprocess.run(cmd_alt, capture_output=True, text=True, timeout=60)

        if result_alt.returncode == 0 and result_alt.stdout.strip():
            url = result_alt.stdout.strip()
            if url and url.startswith("http"):
                return {
                    "success": True,
                    "url": url,
                    "extracted_at": datetime.now(timezone.utc).isoformat(),
                }

        # Check stderr for error info
        error_msg = result.stderr or result_alt.stderr or "Unknown error"
        if "is not a valid URL" in error_msg or "Unsupported URL" in error_msg:
            error_msg = "Invalid or unsupported YouTube URL"
        elif "Private video" in error_msg:
            error_msg = "Private video"
        elif "Video unavailable" in error_msg:
            error_msg = "Video unavailable"
        elif (
            "not a live stream" in error_msg.lower()
            or "is not live" in error_msg.lower()
        ):
            error_msg = "Not a live stream"
        elif "Sign in" in error_msg:
            error_msg = "Age-restricted or sign-in required"
        else:
            error_msg = f"yt-dlp error: {error_msg[:200]}"

        return {
            "success": False,
            "error": error_msg,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Extraction timed out",
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
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
            "logo": "",
            "group": "Music",
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

    # Check yt-dlp version
    try:
        result = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
        print(f"yt-dlp version: {result.stdout.strip()}")
    except:
        print("WARNING: yt-dlp not found!")

    # Check cookies
    if os.path.exists(COOKIES_FILE):
        print(f"Using cookies from {COOKIES_FILE}")
    else:
        print("No cookies.txt found (some streams may require login)")

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
            print(f"    SUCCESS - Found HLS stream")
            print(f"    m3u8: {stream_info['url'][:80]}...")
        else:
            print(f"    FAILED - {stream_info.get('error', 'Unknown error')}")

        results.append({**channel, "stream": stream_info})

    # Save results
    print("\n" + "-" * 60)
    save_streams(results)
    print(f"Saved streams to {OUTPUT_FILE}")

    # Generate M3U
    generate_m3u(results)
    print(f"Generated M3U playlist: {M3U_FILE}")

    # Summary
    print("\n" + "=" * 60)
    print(f"SUMMARY: {success_count}/{len(results)} streams extracted successfully")
    print("=" * 60)

    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
