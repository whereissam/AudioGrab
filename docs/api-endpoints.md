# X/Twitter API Endpoints Reference

This document details the internal X/Twitter API endpoints used for downloading Spaces.

## Important Notice

> **Warning**: These are internal/undocumented APIs used by Twitter's web client.
> They may change without notice. As of July 2023, Twitter requires authenticated
> access (cookies) for these endpoints - guest tokens alone no longer work.

## Authentication Headers

All requests require these headers:

```
Authorization: Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCgYR9Wk5bLLMNhyFz4%3DsIHxcAabN8Z2cIUpYBUSsYGqNFtEGV1VTJFhD4ij8EV2YikPq3
Cookie: auth_token=<your_auth_token>; ct0=<your_ct0>
x-csrf-token: <your_ct0>
```

## 1. Guest Token Activation (Legacy - May Not Work)

**Endpoint**: `POST https://api.twitter.com/1.1/guest/activate.json`

```bash
curl -X POST 'https://api.twitter.com/1.1/guest/activate.json' \
  -H 'Authorization: Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCgYR9Wk5bLLMNhyFz4%3DsIHxcAabN8Z2cIUpYBUSsYGqNFtEGV1VTJFhD4ij8EV2YikPq3'
```

**Response**:
```json
{
  "guest_token": "1234567890123456789"
}
```

## 2. AudioSpaceById GraphQL Endpoint

**Endpoint**: `GET https://x.com/i/api/graphql/{query_id}/AudioSpaceById`

The `query_id` is a hash that changes when Twitter updates their API. Known values:
- `jyQ0_DEMZHeoluCgHJ-U5Q`
- `Uv5R_-Chxbn1FEkyUkSW2w`
- `s3V0Y5v6` (shortened form)

**Parameters** (URL encoded JSON):
```json
{
  "id": "1vOxwdyYrlqKB",
  "isMetatagsQuery": false,
  "withReplays": true,
  "withListeners": true
}
```

**Full URL Example**:
```
https://x.com/i/api/graphql/jyQ0_DEMZHeoluCgHJ-U5Q/AudioSpaceById?variables=%7B%22id%22%3A%221vOxwdyYrlqKB%22%2C%22isMetatagsQuery%22%3Afalse%2C%22withReplays%22%3Atrue%2C%22withListeners%22%3Atrue%7D
```

**Response Structure**:
```json
{
  "data": {
    "audioSpace": {
      "metadata": {
        "rest_id": "1vOxwdyYrlqKB",
        "state": "Ended",
        "title": "Space Title",
        "media_key": "28_2013482329990144000",
        "created_at": 1737549600000,
        "started_at": 1737549600000,
        "ended_at": 1737556800000,
        "is_space_available_for_replay": true,
        "total_replay_watched": 1234,
        "total_live_listeners": 5678,
        "creator_results": {
          "result": {
            "legacy": {
              "screen_name": "username",
              "name": "Display Name"
            }
          }
        }
      },
      "participants": {
        "total": 100,
        "admins": [...],
        "speakers": [...]
      }
    }
  }
}
```

**Key Fields**:
| Field | Description |
|-------|-------------|
| `media_key` | Required for stream URL lookup (format: `28_xxxx`) |
| `state` | `Running`, `Ended`, `Scheduled` |
| `is_space_available_for_replay` | Must be `true` for downloads |
| `rest_id` | Space ID from URL |

## 3. Live Video Stream Status

**Endpoint**: `GET https://x.com/i/api/1.1/live_video_stream/status/{media_key}`

```bash
curl 'https://x.com/i/api/1.1/live_video_stream/status/28_2013482329990144000' \
  -H 'Authorization: Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCgYR9Wk5bLLMNhyFz4%3DsIHxcAabN8Z2cIUpYBUSsYGqNFtEGV1VTJFhD4ij8EV2YikPq3' \
  -H 'Cookie: auth_token=xxx; ct0=xxx' \
  -H 'x-csrf-token: xxx'
```

**Response**:
```json
{
  "source": {
    "location": "https://prod-ec-us-east-1.video.pscp.tv/Transcoding/v1/hls/xxx/non_transcode/us-east-1/periscope-replay-direct-prod-us-east-1-public/audio-space/playlist_xxx.m3u8?type=replay",
    "noRedirectPlaybackUrl": "...",
    "status": "ENDED",
    "streamType": "HLS"
  },
  "sessionId": "...",
  "chatToken": "..."
}
```

**Key Fields**:
| Field | Description |
|-------|-------------|
| `source.location` | Master m3u8 playlist URL |
| `source.status` | `LIVE`, `ENDED` |
| `source.streamType` | Usually `HLS` |

## 4. M3U8 Playlist Structure

The master playlist contains multiple quality variants:

```m3u8
#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=64000,CODECS="mp4a.40.2"
chunk_playlist_64k.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=128000,CODECS="mp4a.40.2"
chunk_playlist_128k.m3u8
```

Each variant playlist contains audio segments:

```m3u8
#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:6
#EXT-X-MEDIA-SEQUENCE:0
#EXTINF:6.0,
chunk_00001.aac
#EXTINF:6.0,
chunk_00002.aac
...
#EXT-X-ENDLIST
```

## 5. Alternative: Broadcasts Show Endpoint

For some Spaces, an alternative endpoint exists:

**Endpoint**: `GET https://x.com/i/api/1.1/broadcasts/show.json`

**Parameters**:
- `ids`: Comma-separated broadcast IDs

## Rate Limiting

Twitter enforces rate limits on these endpoints:
- Guest tokens: ~100 requests per 15 minutes per IP
- Authenticated: ~900 requests per 15 minutes per user

## Error Responses

| Status | Meaning |
|--------|---------|
| 401 | Invalid/expired authentication |
| 403 | Space not available for replay or private |
| 404 | Space not found |
| 429 | Rate limited |

## Domains Used

The following domains are involved in Space downloads:
- `x.com` / `twitter.com` - Main API
- `video.twitter.com` - Video/audio CDN
- `pscp.tv` - Periscope streaming (legacy)
- `prod-ec-*.video.pscp.tv` - Stream CDN
