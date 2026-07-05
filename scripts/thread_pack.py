#!/usr/bin/env python3
"""
Pack a file into the smallest possible THREAD of X "compose links".

Each tweet carries one link:  https://x.com/compose/post?text=<chunk>
where <chunk> is a slice of  base64url( raw-DEFLATE(file) ).

Why this is the minimal encoding:
  - raw DEFLATE (wbits=-15) is the densest format browsers can inflate natively
    (DecompressionStream 'deflate-raw'); no zlib/gzip header wasted.
  - base64url ([A-Za-z0-9-_], no '=') is URL-safe with ZERO %-expansion, so the
    entire measured URL budget becomes payload. Standard base64 wastes ~7% on
    %-encoding +,/,= -> that alone is ~6 extra tweets for this game.
  - No literal '<script' anywhere, so x.com's WAF (which 403s XSS signatures)
    passes it.

Ceiling: x.com rejects URLs over ~14,300 chars (HTTP 431). Measured safe = 14,280.

Usage:
    python thread_pack.py minified-index.html
    python thread_pack.py minified-index.html --deflate game.deflate   # e.g. zopfli
    python thread_pack.py minified-index.html -o thread
"""
import os, zlib, base64, argparse

PREFIX = "https://x.com/compose/post?text="
URL_CEIL = 10000                       # safe under a logged-in browser (cookies+headers eat the ~14.3k total budget)
MAXCHUNK = URL_CEIL - len(PREFIX)      # base64url = no expansion, so chunk chars == url payload chars


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--outdir", default="thread")
    ap.add_argument("--deflate", help="use this precompressed raw-DEFLATE blob (e.g. zopfli) instead of zlib -9")
    args = ap.parse_args()

    data = open(args.input, "rb").read()
    if args.deflate:
        comp = open(args.deflate, "rb").read()
        how = f"provided ({os.path.basename(args.deflate)})"
    else:
        co = zlib.compressobj(level=9, wbits=-15)
        comp = co.compress(data) + co.flush()
        how = "zlib -9"

    payload = b64url(comp)
    chunks = [payload[i:i + MAXCHUNK] for i in range(0, len(payload), MAXCHUNK)]

    os.makedirs(args.outdir, exist_ok=True)
    links = []
    for i, c in enumerate(chunks, 1):
        link = PREFIX + c            # base64url is already URL-safe: no quoting
        links.append(link)
        with open(os.path.join(args.outdir, f"tweet-{i:03d}.txt"), "w") as f:
            f.write(link)
    with open(os.path.join(args.outdir, "thread.txt"), "w") as f:
        f.write("\n".join(links))

    longest = max(len(l) for l in links)
    print(f"input          : {len(data):>12,} bytes")
    print(f"raw DEFLATE    : {len(comp):>12,} bytes  ({how})")
    print(f"base64url      : {len(payload):>12,} chars")
    print(f"budget/tweet   : {MAXCHUNK:>12,} chars")
    print(f"THREAD         : {len(chunks):>12} tweets  -> {args.outdir}/tweet-001..{len(chunks):03d}.txt")
    print(f"longest link   : {longest:>12,} chars  (ceiling {URL_CEIL:,}) {'OK' if longest <= URL_CEIL else 'OVER!'}")


if __name__ == "__main__":
    main()
