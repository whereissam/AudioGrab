# Downloading from Instagram — Setup Guide

Instagram blocks downloads unless you are **logged in**. To let the app
download Instagram reels and posts, you give it a copy of your Instagram
login (a "cookies" file). You only do this once.

> ⏱️ Takes about 3 minutes. No coding required.

---

## Step 1 — Install a cookies exporter

Add this free extension to your browser (Chrome, Brave, Edge, or Firefox):

- **"Get cookies.txt LOCALLY"**
  - Chrome / Brave / Edge: search the Chrome Web Store for
    *"Get cookies.txt LOCALLY"* and click **Add to browser**.
  - Firefox: search Firefox Add-ons for the same name.

> The word **LOCALLY** matters — it means the extension keeps your data on
> your computer and never uploads it. Use that exact one.

## Step 2 — Log in to Instagram

1. Open a new tab and go to **https://www.instagram.com**.
2. Make sure you are **logged in** (you can see your feed / profile).

## Step 3 — Export the cookies file

1. While the Instagram tab is open, click the **Get cookies.txt LOCALLY**
   icon in your browser toolbar (you may need to click the puzzle-piece
   "Extensions" icon to find it).
2. Click **Export** (or **Download**).
3. It saves a file named something like **`instagram.com_cookies.txt`** to
   your **Downloads** folder.

## Step 4 — Tell the app where the file is

1. Move the file somewhere permanent if you like (e.g. your home folder).
   Note its full path, for example:
   `/Users/yourname/Downloads/instagram.com_cookies.txt`
2. Open the app's **`.env`** file (in the project root) in any text editor.
3. Add this line (use your file's real path):

   ```
   INSTAGRAM_COOKIES_FILE=/Users/yourname/Downloads/instagram.com_cookies.txt
   ```

4. Save the file and **restart the app**.

## Step 5 — Try a download

Paste an Instagram reel or post URL into the app and download it. It should
now work.

---

## Notes & troubleshooting

- **Keep the file private.** It contains your Instagram login — anyone with
  it can access your account. Don't share it or commit it to git.
- **It expires.** Instagram sessions eventually log out (weeks to months).
  If downloads start failing again with a "requires login" message, just
  repeat Steps 3–4 to export a fresh file.
- **Private accounts:** you can only download content your logged-in account
  is allowed to see.
- **"Requires login" still showing?** Make sure you were logged in when you
  exported, and that the path in `.env` is exactly right (no typos, no extra
  quotes).

## Why not "read from my browser automatically"?

On macOS, browsers encrypt their cookies with a key locked in the system
Keychain. The app's downloader can't unlock that key, so automatic
browser-cookie reading fails with *"cannot decrypt cookies: no key found"*.
Exporting a `cookies.txt` file (above) is the reliable method.
