# YouTube Live Stream Extractor

Automatically extracts HLS (m3u8) URLs from YouTube live streams using GitHub Actions.

## Why?

YouTube blocks datacenter IPs from accessing live stream URLs. This repo runs on GitHub Actions (which uses clean IPs) to extract working HLS URLs every 2 hours.

## Usage

### Get the M3U Playlist

After the workflow runs, use the raw GitHub URL:

```
https://raw.githubusercontent.com/YOUR_USERNAME/youtube-restream/main/youtube.m3u
```

### Add to IPTV Players

- **VLC**: Media > Open Network Stream > paste URL
- **Kodi**: Add as M3U playlist source
- **NoxStream**: Add as external playlist URL

## Adding Channels

Edit `channels.json`:

```json
[
  {
    "id": "unique_id",
    "name": "Channel Name",
    "url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "logo": "https://example.com/logo.png",
    "group": "Category"
  }
]
```

Or trigger the workflow manually with a YouTube URL.

## How It Works

1. GitHub Actions runs `extractor.py` every 2 hours
2. Script fetches YouTube pages and extracts `hlsManifestUrl` from HTML
3. Generates `youtube.m3u` playlist and `streams.json`
4. Commits updated files back to repo

## Limitations

- **Only works for LIVE streams** (not VOD)
- **URLs expire** in ~6-12 hours (hence 2-hour refresh)
- **Geo-restricted streams** may not work

## Default Channels

- Lofi Girl (Music)
- DW News, France 24, Al Jazeera, Sky News, ABC Australia (News)
- NASA Live (Science)
- Bloomberg Global (Business)

## Manual Trigger

Go to Actions > YouTube Stream Extractor > Run workflow

## License

MIT
