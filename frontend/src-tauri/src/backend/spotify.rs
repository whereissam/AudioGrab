//! Spotify podcast episode support.
//!
//! Spotify's own streams are DRM-protected, so yt-dlp cannot (and should
//! not) touch them. Podcast episodes, however — unlike music — are almost
//! always syndicated on the show's public RSS feed. This module resolves
//! the same episode there using only public metadata endpoints:
//!
//!   Spotify oEmbed (episode title)
//!     → iTunes Search API (entity=podcastEpisode)
//!       → RSS enclosure MP3 (direct download)

use std::path::Path;

use serde::Deserialize;
use tokio::io::AsyncWriteExt;

use super::types::{ContentInfo, DownloadResult, Platform};

#[derive(Deserialize)]
struct OEmbed {
    title: String,
}

#[derive(Deserialize)]
struct ItunesSearch {
    results: Vec<ItunesEpisode>,
}

#[derive(Deserialize)]
struct ItunesEpisode {
    #[serde(rename = "trackName")]
    track_name: Option<String>,
    #[serde(rename = "collectionName")]
    collection_name: Option<String>,
    #[serde(rename = "episodeUrl")]
    episode_url: Option<String>,
    #[serde(rename = "trackTimeMillis")]
    track_time_millis: Option<u64>,
}

/// A Spotify episode located on its public RSS feed.
pub struct ResolvedEpisode {
    pub title: String,
    pub show: Option<String>,
    pub mp3_url: String,
    pub duration_seconds: Option<f64>,
}

pub fn is_episode_url(url: &str) -> bool {
    url.contains("open.spotify.com/episode/")
}

fn episode_id(url: &str) -> String {
    url.split("/episode/")
        .nth(1)
        .unwrap_or("")
        .split(['?', '/'])
        .next()
        .unwrap_or("")
        .to_string()
}

fn sanitize_filename(name: &str) -> String {
    name.chars()
        .map(|c| match c {
            '/' | '\\' | ':' | '*' | '?' | '"' | '<' | '>' | '|' => '_',
            _ => c,
        })
        .take(150)
        .collect::<String>()
        .trim()
        .to_string()
}

/// Locate a Spotify episode on its public RSS feed. Fails with a clear
/// message when the episode is Spotify-exclusive (no public syndication).
pub async fn resolve_episode(url: &str) -> Result<ResolvedEpisode, String> {
    let client = reqwest::Client::builder()
        .user_agent("sift-desktop/0.2")
        .build()
        .map_err(|e| format!("HTTP client error: {e}"))?;

    let oembed: OEmbed = client
        .get("https://open.spotify.com/oembed")
        .query(&[("url", url)])
        .send()
        .await
        .map_err(|e| format!("Spotify oEmbed request failed: {e}"))?
        .error_for_status()
        .map_err(|_| "Spotify did not recognize this episode URL".to_string())?
        .json()
        .await
        .map_err(|e| format!("Unexpected Spotify oEmbed response: {e}"))?;
    let title = oembed.title;

    let search: ItunesSearch = client
        .get("https://itunes.apple.com/search")
        .query(&[
            ("term", title.as_str()),
            ("media", "podcast"),
            ("entity", "podcastEpisode"),
            ("limit", "10"),
        ])
        .send()
        .await
        .map_err(|e| format!("iTunes episode search failed: {e}"))?
        .error_for_status()
        .map_err(|e| format!("iTunes episode search rejected: {e}"))?
        .json()
        .await
        .map_err(|e| format!("Unexpected iTunes search response: {e}"))?;

    // Prefer an exact/prefix title match; fall back to the first result
    // with an enclosure URL (the search is already title-scoped).
    let with_url = |e: &&ItunesEpisode| e.episode_url.is_some();
    let picked = search
        .results
        .iter()
        .filter(with_url)
        .find(|e| {
            e.track_name
                .as_deref()
                .map(|t| t == title || t.starts_with(&title) || title.starts_with(t))
                .unwrap_or(false)
        })
        .or_else(|| search.results.iter().find(with_url))
        .ok_or_else(|| {
            format!(
                "'{title}' was not found on any public podcast feed — it may be \
                 Spotify-exclusive, which cannot be downloaded"
            )
        })?;

    Ok(ResolvedEpisode {
        title,
        show: picked.collection_name.clone(),
        mp3_url: picked.episode_url.clone().expect("filtered on episode_url"),
        duration_seconds: picked.track_time_millis.map(|ms| ms as f64 / 1000.0),
    })
}

/// Download a Spotify episode via its public RSS enclosure.
pub async fn download_episode(url: &str, output_dir: &Path) -> DownloadResult {
    match try_download_episode(url, output_dir).await {
        Ok(result) => result,
        Err(error) => DownloadResult {
            success: false,
            file_path: None,
            metadata: None,
            error: Some(error),
            file_size_bytes: None,
        },
    }
}

async fn try_download_episode(url: &str, output_dir: &Path) -> Result<DownloadResult, String> {
    let episode = resolve_episode(url).await?;

    let base = match &episode.show {
        Some(show) => format!("{show} - {}", episode.title),
        None => episode.title.clone(),
    };
    let file_path = output_dir.join(format!("{}.mp3", sanitize_filename(&base)));

    let client = reqwest::Client::builder()
        .user_agent("sift-desktop/0.2")
        .build()
        .map_err(|e| format!("HTTP client error: {e}"))?;
    let mut response = client
        .get(&episode.mp3_url)
        .send()
        .await
        .map_err(|e| format!("Episode download failed to start: {e}"))?
        .error_for_status()
        .map_err(|e| format!("Episode host rejected the download: {e}"))?;

    let mut file = tokio::fs::File::create(&file_path)
        .await
        .map_err(|e| format!("Cannot create output file: {e}"))?;
    let mut size: u64 = 0;
    while let Some(chunk) = response
        .chunk()
        .await
        .map_err(|e| format!("Episode download interrupted: {e}"))?
    {
        size += chunk.len() as u64;
        file.write_all(&chunk)
            .await
            .map_err(|e| format!("Write failed: {e}"))?;
    }
    file.flush().await.ok();

    Ok(DownloadResult {
        success: true,
        file_path: Some(file_path.to_string_lossy().to_string()),
        metadata: Some(ContentInfo {
            platform: Platform::Spotify,
            content_id: episode_id(url),
            title: episode.title,
            creator_name: episode.show,
            creator_username: None,
            duration_seconds: episode.duration_seconds,
        }),
        error: None,
        file_size_bytes: Some(size),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detects_episode_urls() {
        assert!(is_episode_url(
            "https://open.spotify.com/episode/3FErc0AYpIO97DdOmMlCjw"
        ));
        assert!(!is_episode_url(
            "https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC"
        ));
    }

    #[test]
    fn extracts_episode_id() {
        assert_eq!(
            episode_id("https://open.spotify.com/episode/3FErc0AYpIO97DdOmMlCjw?si=xyz"),
            "3FErc0AYpIO97DdOmMlCjw"
        );
    }

    #[test]
    fn sanitizes_filenames() {
        assert_eq!(sanitize_filename("a/b:c?d"), "a_b_c_d");
        assert!(sanitize_filename(&"x".repeat(300)).len() <= 150);
    }

    /// Live resolution against Spotify + iTunes; run explicitly with:
    /// cargo test -- --ignored resolve
    #[tokio::test]
    #[ignore]
    async fn resolves_real_episode_to_rss_enclosure() {
        let ep = resolve_episode("https://open.spotify.com/episode/3FErc0AYpIO97DdOmMlCjw")
            .await
            .expect("episode should resolve");
        assert!(ep.mp3_url.contains(".mp3"));
        assert!(ep.title.contains("OUSD"));
        assert_eq!(ep.show.as_deref(), Some("Web3 101"));
    }

    /// Full end-to-end download through the same entry point the HTTP
    /// route uses (execute_download → download_episode). Downloads a real
    /// ~97MB episode; run explicitly with: cargo test -- --ignored end_to_end
    #[tokio::test]
    #[ignore]
    async fn end_to_end_episode_download() {
        let dir = std::env::temp_dir().join(format!("sift-spotify-test-{}", std::process::id()));
        tokio::fs::create_dir_all(&dir).await.unwrap();

        let result = crate::backend::downloader::execute_download(
            "https://open.spotify.com/episode/3FErc0AYpIO97DdOmMlCjw",
            &dir,
            crate::backend::types::OutputFormat::M4a,
            crate::backend::types::QualityPreset::High,
            Platform::Spotify,
        )
        .await;

        assert!(result.success, "download failed: {:?}", result.error);
        let path = std::path::PathBuf::from(result.file_path.expect("file path set"));
        let size = std::fs::metadata(&path).expect("file exists").len();
        assert!(size > 10_000_000, "file suspiciously small: {size} bytes");
        let meta = result.metadata.expect("metadata set");
        assert_eq!(meta.creator_name.as_deref(), Some("Web3 101"));

        tokio::fs::remove_dir_all(&dir).await.ok();
    }
}
