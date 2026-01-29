#!/usr/bin/env python3
"""
YouTube Live HLS Segment Downloader
Downloads HLS segments from YouTube and stores them in GitHub repo
Creates a local m3u8 playlist pointing to GitHub raw URLs
"""

import subprocess
import json
import os
import sys
import re
import requests
import shutil
from datetime import datetime, timezone
from pathlib import Path

CHANNELS_FILE = "channels.json"
COOKIES_FILE = "cookies.txt"
SEGMENTS_DIR = "segments"
GITHUB_REPO = "invisiblecoder99/youtube-restream"
GITHUB_BRANCH = "main"
MAX_SEGMENTS = 10  # Keep only last N segments to save space


def get_cookies_args():
    """Return cookies arguments if cookies.txt exists"""
    if os.path.exists(COOKIES_FILE):
        return ["--cookies", COOKIES_FILE]
    return []


def get_manifest_url(youtube_url):
    """Extract HLS manifest URL using yt-dlp"""
    try:
        if "/channel/" in youtube_url or "/c/" in youtube_url or "/@" in youtube_url:
            if not youtube_url.endswith("/live"):
                youtube_url = youtube_url.rstrip("/") + "/live"

        cookies_args = get_cookies_args()

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
                return manifest_url

        return None
    except Exception as e:
        print(f"Error extracting manifest: {e}")
        return None


def download_manifest(manifest_url):
    """Download and parse master manifest"""
    try:
        resp = requests.get(manifest_url, timeout=30)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"Error downloading manifest: {e}")
        return None


def get_best_quality_playlist(master_manifest, manifest_url):
    """Parse master manifest and get best quality playlist URL"""
    lines = master_manifest.strip().split("\n")
    playlists = []

    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF"):
            # Extract bandwidth
            bw_match = re.search(r"BANDWIDTH=(\d+)", line)
            bandwidth = int(bw_match.group(1)) if bw_match else 0

            # Next line should be the playlist URL
            if i + 1 < len(lines):
                playlist_url = lines[i + 1].strip()
                if not playlist_url.startswith("http"):
                    # Relative URL - make absolute
                    base_url = manifest_url.rsplit("/", 1)[0]
                    playlist_url = f"{base_url}/{playlist_url}"
                playlists.append((bandwidth, playlist_url))

    if playlists:
        # Sort by bandwidth and return highest
        playlists.sort(key=lambda x: x[0], reverse=True)
        return playlists[0][1]

    return None


def download_segments(playlist_url, channel_id):
    """Download HLS segments from playlist"""
    try:
        resp = requests.get(playlist_url, timeout=30)
        resp.raise_for_status()
        playlist_content = resp.text
    except Exception as e:
        print(f"Error downloading playlist: {e}")
        return None, []

    # Create segments directory for this channel
    channel_dir = Path(SEGMENTS_DIR) / channel_id
    channel_dir.mkdir(parents=True, exist_ok=True)

    lines = playlist_content.strip().split("\n")
    segments = []
    segment_info = {}

    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF"):
            # Extract duration
            match = re.search(r"#EXTINF:([\d.]+)", line)
            if match:
                segment_info["duration"] = float(match.group(1))
        elif line.startswith("#") or not line:
            continue
        else:
            # This is a segment URL
            segment_url = line
            if not segment_url.startswith("http"):
                base_url = playlist_url.rsplit("/", 1)[0]
                segment_url = f"{base_url}/{segment_url}"

            # Generate segment filename
            segment_name = f"seg_{len(segments):04d}.ts"
            segment_path = channel_dir / segment_name

            # Download segment
            try:
                print(f"    Downloading segment {len(segments) + 1}...")
                seg_resp = requests.get(segment_url, timeout=30)
                seg_resp.raise_for_status()

                with open(segment_path, "wb") as f:
                    f.write(seg_resp.content)

                segments.append(
                    {
                        "filename": segment_name,
                        "duration": segment_info.get("duration", 2.0),
                        "path": str(segment_path),
                    }
                )
                segment_info = {}

                # Limit segments
                if len(segments) >= MAX_SEGMENTS:
                    break

            except Exception as e:
                print(f"    Error downloading segment: {e}")
                continue

    return channel_dir, segments


def generate_local_m3u8(channel_id, segments):
    """Generate m3u8 playlist pointing to GitHub raw URLs"""
    if not segments:
        return None

    github_base = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{SEGMENTS_DIR}/{channel_id}"

    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        "#EXT-X-TARGETDURATION:10",
        f"#EXT-X-MEDIA-SEQUENCE:0",
        "",
    ]

    for seg in segments:
        lines.append(f"#EXTINF:{seg['duration']:.3f},")
        lines.append(f"{github_base}/{seg['filename']}")

    # Don't add ENDLIST for live streams - allows continuous playback
    # lines.append("#EXT-X-ENDLIST")

    m3u8_path = Path(SEGMENTS_DIR) / channel_id / "playlist.m3u8"
    with open(m3u8_path, "w") as f:
        f.write("\n".join(lines))

    return str(m3u8_path)


def generate_master_m3u(channels_data):
    """Generate master M3U playlist with all channels"""
    lines = ["#EXTM3U", ""]
    lines.append(f"# YouTube Live Restream - Segments hosted on GitHub")
    lines.append(f"# Last updated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")

    github_base = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{SEGMENTS_DIR}"

    for channel in channels_data:
        if channel.get("success"):
            group = channel.get("group", "YouTube")
            logo = channel.get("logo", "")
            tvg_id = channel.get("id", "")
            name = channel.get("name", "Unknown")

            playlist_url = f"{github_base}/{tvg_id}/playlist.m3u8"

            extinf = f'#EXTINF:-1 group-title="{group}" tvg-logo="{logo}" tvg-id="{tvg_id}", {name}'
            lines.append(extinf)
            lines.append(playlist_url)
            lines.append("")

    with open("youtube.m3u", "w") as f:
        f.write("\n".join(lines))


def load_channels():
    """Load channel list from JSON file"""
    if os.path.exists(CHANNELS_FILE):
        with open(CHANNELS_FILE, "r") as f:
            return json.load(f)
    return []


def cleanup_old_segments(channel_dir, keep=MAX_SEGMENTS):
    """Remove old segments, keep only latest N"""
    if not channel_dir.exists():
        return

    segments = sorted(channel_dir.glob("seg_*.ts"))
    if len(segments) > keep:
        for seg in segments[:-keep]:
            seg.unlink()
            print(f"    Removed old segment: {seg.name}")


def main():
    print("=" * 60)
    print("YouTube Live HLS Segment Downloader")
    print("Downloads segments and hosts on GitHub")
    print("=" * 60)

    # Check yt-dlp
    try:
        result = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
        print(f"yt-dlp version: {result.stdout.strip()}")
    except:
        print("ERROR: yt-dlp not found!")
        return 1

    # Check cookies
    if os.path.exists(COOKIES_FILE):
        print(f"Using cookies from {COOKIES_FILE}")
    else:
        print("No cookies.txt found")

    # Load channels
    channels = load_channels()
    if not channels:
        print("No channels.json found!")
        return 1

    print(f"\nProcessing {len(channels)} channels...")
    print("-" * 60)

    # Create segments directory
    Path(SEGMENTS_DIR).mkdir(exist_ok=True)

    results = []

    for i, channel in enumerate(channels, 1):
        channel_id = channel.get("id", f"channel_{i}")
        print(f"\n[{i}/{len(channels)}] {channel['name']} (ID: {channel_id})")
        print(f"    URL: {channel['url']}")

        # Get manifest URL
        manifest_url = get_manifest_url(channel["url"])
        if not manifest_url:
            print("    FAILED - Could not extract manifest URL")
            results.append({**channel, "success": False})
            continue

        print(f"    Got manifest URL")

        # Download master manifest
        master_manifest = download_manifest(manifest_url)
        if not master_manifest:
            print("    FAILED - Could not download manifest")
            results.append({**channel, "success": False})
            continue

        # Get best quality playlist
        playlist_url = get_best_quality_playlist(master_manifest, manifest_url)
        if not playlist_url:
            # Maybe it's already a media playlist, not master
            playlist_url = manifest_url

        print(f"    Got playlist URL")

        # Download segments
        channel_dir, segments = download_segments(playlist_url, channel_id)
        if not segments:
            print("    FAILED - Could not download segments")
            results.append({**channel, "success": False})
            continue

        print(f"    Downloaded {len(segments)} segments")

        # Cleanup old segments
        cleanup_old_segments(channel_dir)

        # Generate local m3u8
        m3u8_path = generate_local_m3u8(channel_id, segments)
        print(f"    Generated playlist: {m3u8_path}")

        results.append({**channel, "success": True, "segments": len(segments)})

    # Generate master M3U
    generate_master_m3u(results)
    print(f"\nGenerated master playlist: youtube.m3u")

    # Summary
    success_count = sum(1 for r in results if r.get("success"))
    print("\n" + "=" * 60)
    print(f"SUMMARY: {success_count}/{len(results)} channels processed")
    print("=" * 60)

    github_url = (
        f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/youtube.m3u"
    )
    print(f"\nPlaylist URL: {github_url}")

    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
