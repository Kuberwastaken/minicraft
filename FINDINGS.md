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

The bundle also appears to carry unused Node crypto polyfills (elliptic / bn.js /
pbkdf2 / secp256k1) — stripping that dead weight is a promising, orthogonal lever.

## Current thread
`build_thread.py` emits `TWEETS/`:
- `tweet-001` hook: visible text + a compose link with the explanation.
- `tweet-002` decoder: a compose link carrying `data:text/html;base64,<decoder>`.
- `tweet-003…` the game as base64url(deflate-raw) parts.

Reader flow: open tweet 2's `data:` URL (the decoder), paste tweets 3+ into it, hit
Play — the decoder base64url-decodes, inflates via `DecompressionStream('deflate-raw')`,
and `document.write`s the game. Verified: byte-exact round-trip, and every link returns
HTTP 200 under a realistic logged-in header set.

## Tooling (`scripts/`)
- `compose_link.py` — any text/file → one compose link.
- `thread_pack.py` / `thread_unpack.py` — file ⇄ thread of compose links (verifier).
- `build_thread.py` — the full `TWEETS/` thread (hook + decoder + parts).
- `decoder.html` — the self-contained decoder page (paste parts, Play, confetti).
