# Minecraft-in-a-thread — findings

Notes from packing a playable Minecraft Classic build into a thread of X (Twitter)
posts using the "compose-link" trick. All numbers here were measured against x.com
directly, not assumed.

## The trick
Every link on X counts as 23 characters (t.co), no matter how long the URL is. So a
link to `https://x.com/compose/post?text=<PAYLOAD>` costs 23 chars in a tweet but can
carry a large `text=` payload. Clicking it opens the composer pre-filled with the
decoded text. We use that to smuggle the game across many tweets.

## Two hard walls
1. **WAF (content).** x.com URL-decodes the request and returns **403** on XSS
   signatures: `<script` (any spacing/case), `onerror=`, etc. Benign tags (`<div>`,
   `<b>`), the word "script", bare `< >`, and our decoder machinery (`atob`,
   `DecompressionStream`) all pass. So the payload must contain **no literal
   `<script`** — we encode the game as base64url, and deliver the decoder as base64.
2. **URL length (transport).** x.com returns **431 "Request Header Fields Too Large"**
   when the *total* request (request-line URL + cookies + headers) is too big.
   - No cookies (curl): ceiling ~**14,300** chars of URL.
   - Logged-in browser: cookies + headers eat ~2.5–4 KB, so the safe URL is ~**10,000–11,000**.
   We cap the URL at **10,000** so links survive a real logged-in click.

## Encoding
- **base64url** (`A-Za-z0-9_-`, no `=` padding): URL-safe with zero %-expansion, 6 bits
  per URL char. This is effectively the density ceiling — only ~64–66 single-byte chars
  survive the URL + WAF unencoded. Standard base64 wastes ~7% percent-encoding `+ / =`.

## Per-tweet capacity
- URL cap 10,000 − prefix 32 = **9,968 payload chars/tweet** = 7,476 bytes of raw payload.

## Compression (input: 4,466,890-byte terser-minified game)
Browsers only decompress gzip/deflate natively, but we ship our own decoder, so a
stronger codec is possible (weigh the decoder's own size).

| codec | size | data tweets | vs deflate |
|---|---:|---:|---:|
| deflate / zopfli (native, current) | 880,075 | 118 | — |
| zstd −22 | 697,085 | 94 | −21% |
| LZMA −9e | 657,445 | 88 | −25% |
| brotli −11 | 654,521 | 88 | −26% |

## Optimization: 120 → 44 tweets
The game (`minified-index.html`, 4.47 MB) is mostly one library.

1. **Strip the engine down.** Module 470 of the webpack bundle is Babylon.js 4.0.3
   (2.37 MB, ~69% of the bundle) but the game references only **26 `BABYLON.*`
   names**. Tree-shaking `@babylonjs/core@4.0.3` to that surface = **806 KB**. Plus
   the reachable crypto tree (elliptic / bn.js ×7 / ciphers / pbkdf2, dragged in by a
   single `randomBytes` call) is stubbed out (~543 KB). Result: `game-shaken.html`,
   **2.32 MB**. Verified in headless Chrome: world renders, menus / place / break /
   movement work, 0 fatal errors.
2. **Better codec.** LZMA1 (`lzma` npm, mode 9) → **310,866 B → 42 base64url parts**
   (deflate would be ~74). Decoded in-browser by an embedded LZMA-JS engine, so we're
   not limited to native `DecompressionStream`.

## Current thread — 44 tweets
`build_thread.py` emits `TWEETS/` (compose links) and `unlinked-tweets/` (the decoded
`text=` of each, for local testing):
- `tweet-001` hook: visible text + a compose link with the explanation.
- `tweet-002` decoder: `data:text/html;base64,<bootstrap>`. The bootstrap is a tiny
  page that inflates (native `deflate-raw`) the real decoder — which embeds the LZMA
  engine, so **decode works fully offline**. `TWEETS/manifest.txt` = the part count.
- `tweet-003…` the game as base64url(LZMA) parts.

Decoder (`scripts/decoder_page.html` → deflated into `decoder_bootstrap.html`): paste
the parts (or **auto-fill from GitHub**) → Play → LZMA-decodes → `document.write`s the
game. A **play-directly** link points at kuber.studio/minicraft. Font (Press Start 2P)
and wallpaper are progressive — CSS falls back if offline. Verified: byte-exact
reconstruction, boots in-browser online **and** offline, all links HTTP 200 logged-in.

## Tooling (`scripts/`)
- `compose_link.py` — any text/file → one compose link.
- `thread_pack.py` / `thread_unpack.py` — file ⇄ deflate thread (generic verifier).
- `build_decoder.mjs` — inline LZMA engine + UI → deflate → self-extracting bootstrap.
- `build_thread.py` — the full `TWEETS/` + `unlinked-tweets/` thread.
- `decoder_page.html`, `lzma-d-min.js` — decoder source + embedded LZMA engine.
