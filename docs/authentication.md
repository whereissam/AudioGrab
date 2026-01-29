# Authentication Guide

## Overview

As of July 2023, Twitter/X disabled guest access to their internal APIs. You must now
provide authenticated cookies to download Spaces.

## Required Credentials

| Cookie/Token | Description | Where to Find |
|--------------|-------------|---------------|
| `auth_token` | Session authentication token | Browser cookies |
| `ct0` | CSRF token (also used as `x-csrf-token` header) | Browser cookies |
| Bearer Token | Public app identifier | Hardcoded (see below) |

## Public Bearer Token

This token is used by Twitter's web client and is publicly known:

```
AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCgYR9Wk5bLLMNhyFz4%3DsIHxcAabN8Z2cIUpYBUSsYGqNFtEGV1VTJFhD4ij8EV2YikPq3
```

## Obtaining Cookies

### Method 1: Browser DevTools (Manual)

1. Log into X/Twitter in your browser
2. Open DevTools (F12)
3. Go to Application → Cookies → twitter.com (or x.com)
4. Find and copy:
   - `auth_token`
   - `ct0`

### Method 2: Cookie Export Extension

Use a browser extension like "Get cookies.txt LOCALLY" or "EditThisCookie":

1. Install the extension
2. Navigate to x.com while logged in
3. Export cookies in Netscape format
4. Save as `cookies.txt`

### Method 3: Chrome Extension (Automated)

A Chrome extension can automatically capture cookies:

```javascript
// background.js
async function getTwitterCookies() {
    const cookies = await chrome.cookies.getAll({
        domain: '.twitter.com'
    });

    const authToken = cookies.find(c => c.name === 'auth_token')?.value;
    const ct0 = cookies.find(c => c.name === 'ct0')?.value;

    return {
        cookieString: cookies.map(cookie => `${cookie.name}=${cookie.value}`).join('; '),
        authToken,
        ct0
    };
}
```

### Method 4: Browser Cookie Extraction (yt-dlp style)

Use browser cookie databases directly:

```python
import browser_cookie3

# For Chrome
cookies = browser_cookie3.chrome(domain_name='.twitter.com')

# For Firefox
cookies = browser_cookie3.firefox(domain_name='.twitter.com')

# Extract specific cookies
auth_token = None
ct0 = None
for cookie in cookies:
    if cookie.name == 'auth_token':
        auth_token = cookie.value
    elif cookie.name == 'ct0':
        ct0 = cookie.value
```

## Cookie File Format (Netscape)

If using a cookies.txt file:

```
# Netscape HTTP Cookie File
.twitter.com	TRUE	/	TRUE	0	auth_token	YOUR_AUTH_TOKEN_HERE
.twitter.com	TRUE	/	TRUE	0	ct0	YOUR_CT0_HERE
```

## Environment Variables

Set these environment variables for the backend:

```bash
export TWITTER_AUTH_TOKEN="your_auth_token_value"
export TWITTER_CT0="your_ct0_value"

# Or use a cookie file
export TWITTER_COOKIE_FILE="/path/to/cookies.txt"
```

## Request Headers Construction

Python example for building authenticated headers:

```python
def get_auth_headers(auth_token: str, ct0: str) -> dict:
    return {
        "Authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCgYR9Wk5bLLMNhyFz4%3DsIHxcAabN8Z2cIUpYBUSsYGqNFtEGV1VTJFhD4ij8EV2YikPq3",
        "Cookie": f"auth_token={auth_token}; ct0={ct0}",
        "x-csrf-token": ct0,
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-client-language": "en",
        "x-twitter-active-user": "yes",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
```

## Token Expiration

- `auth_token`: Long-lived, lasts months unless invalidated
- `ct0`: Changes periodically, refresh if you get 403 errors

## Security Considerations

⚠️ **Warning**: Your `auth_token` provides full access to your Twitter account.

- Never commit credentials to version control
- Use environment variables or secure vaults
- Consider using a dedicated/throwaway account
- Rotate credentials if exposed

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| 401 Unauthorized | Invalid auth_token | Re-export cookies |
| 403 Forbidden | Invalid/expired ct0 | Refresh ct0 cookie |
| 429 Too Many Requests | Rate limited | Wait 15 minutes |
| CSRF token invalid | ct0 mismatch | Ensure ct0 cookie matches x-csrf-token header |

## Testing Authentication

Quick test script:

```python
import requests

auth_token = "YOUR_AUTH_TOKEN"
ct0 = "YOUR_CT0"

headers = {
    "Authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCgYR9Wk5bLLMNhyFz4%3DsIHxcAabN8Z2cIUpYBUSsYGqNFtEGV1VTJFhD4ij8EV2YikPq3",
    "Cookie": f"auth_token={auth_token}; ct0={ct0}",
    "x-csrf-token": ct0,
}

# Test with account verification endpoint
response = requests.get(
    "https://api.twitter.com/1.1/account/verify_credentials.json",
    headers=headers
)

if response.status_code == 200:
    print("Authentication successful!")
    print(f"Logged in as: @{response.json()['screen_name']}")
else:
    print(f"Authentication failed: {response.status_code}")
    print(response.text)
```
