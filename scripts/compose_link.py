#!/usr/bin/env python3
"""
Turns any text/file into an X (Twitter) "compose link":

    https://x.com/compose/post?text=<url-encoded payload>

Trick (via rebane2001): every link on X is counted as 23 chars (t.co),
regardless of the real URL length. So a link whose ?text= param carries a
huge payload still only costs 23 chars in the tweet you post it in.
Clicking it opens the in-app composer pre-filled with the decoded text.

Two real limits to keep in mind:
  1. The link's actual URL length must survive t.co / X's backend (unknown
     hard cap, empirically low-KB range) -> this is what limits payload size.
  2. text= lands in the composer as PLAIN TEXT (a <script> there is inert);
     it does not execute. Good for delivering prose/source, not for running code.

Usage:
    python compose_link.py                 # reads stdin
    python compose_link.py file.html       # reads a file
    python compose_link.py file.html out.txt
"""
import sys, os, urllib.parse

PREFIX = "https://x.com/compose/post?text="


def make_link(text: str) -> str:
    # safe='' -> encode EVERYTHING that isn't unreserved, so no payload byte
    # can break the URL structure (newlines -> %0A, & -> %26, etc.)
    return PREFIX + urllib.parse.quote(text, safe="")


def main():
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            text = f.read()
        src = sys.argv[1]
    else:
        text = sys.stdin.read()
        src = "<stdin>"

    link = make_link(text)

    out = sys.argv[2] if len(sys.argv) > 2 else None
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(link)

    # report to stderr so stdout stays pipe-clean (the link itself)
    twttr_display = 23  # t.co fixed weight
    print(f"source                : {src}", file=sys.stderr)
    print(f"payload text          : {len(text):>12,} chars", file=sys.stderr)
    print(f"compose link (URL)    : {len(link):>12,} chars", file=sys.stderr)
    print(f"cost inside a tweet   : {twttr_display:>12,} chars  (t.co fixed weight)", file=sys.stderr)
    if out:
        print(f"written to            : {out}", file=sys.stderr)
    else:
        print(link)


if __name__ == "__main__":
    main()
