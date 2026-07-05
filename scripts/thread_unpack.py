#!/usr/bin/env python3
"""
Reassemble a thread of X compose links back into the original file.

Reader flow: click each link in order, copy the text the composer is pre-filled
with (that's one chunk), paste them in order into one file, run this. Or just
point it at the thread/ directory / thread.txt produced by thread_pack.py.

Accepts full compose links OR bare base64url chunks, one per line / per file.

Usage:
    python thread_unpack.py thread/                 # a dir of tweet-*.txt
    python thread_unpack.py thread/thread.txt       # links, one per line
    python thread_unpack.py chunks.txt -o game.html
"""
import os, zlib, base64, glob, argparse
from urllib.parse import unquote

PREFIX_MARK = "text="


def unb64url(s: str) -> bytes:
    s += "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="thread dir, thread.txt, or a file of chunks/links")
    ap.add_argument("-o", "--output", default="reconstructed.html")
    args = ap.parse_args()

    if os.path.isdir(args.src):
        files = sorted(glob.glob(os.path.join(args.src, "tweet-*.txt")))
        links = [open(f).read().strip() for f in files]
    else:
        links = [ln.strip() for ln in open(args.src) if ln.strip()]

    # keep only real payload entries; if any look like compose links, use just
    # those (so a human-readable intro tweet mixed in gets skipped). Otherwise
    # treat every non-empty entry as a bare base64url chunk.
    linkish = [l for l in links if PREFIX_MARK in l]
    use = linkish if linkish else links
    payload = ""
    for ln in use:
        if PREFIX_MARK in ln:
            ln = ln.split(PREFIX_MARK, 1)[1]
        payload += unquote(ln)          # bare base64url passes through unchanged

    comp = unb64url(payload)
    data = zlib.decompress(comp, wbits=-15)
    with open(args.output, "wb") as f:
        f.write(data)

    print(f"tweets read : {len(links)}")
    print(f"base64url   : {len(payload):,} chars")
    print(f"raw DEFLATE : {len(comp):,} bytes")
    print(f"output      : {len(data):,} bytes -> {args.output}")


if __name__ == "__main__":
    main()
