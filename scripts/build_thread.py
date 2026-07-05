#!/usr/bin/env python3
"""
Build the full TWEETS/ thread for "Minecraft in a Twitter post":

  tweet-001  hook  : visible text  + a compose link carrying the explanation
  tweet-002  decoder: a compose link carrying base64(decoder.html)
  tweet-003..N      : the game, as base64url(raw-DEFLATE) split across compose links

Every link is packed to x.com's measured URL ceiling (14,280 chars). base64url
carries the game (no %-expansion); the hook text and decoder are standard-base64/
plain because they're tiny. Nothing contains a literal '<script>' in the URL, so
x.com's WAF passes all of it.

Usage:
    python build_thread.py minified-index.html --deflate game.deflate -o TWEETS
"""
import os, zlib, base64, urllib.parse, argparse

PREFIX = "https://x.com/compose/post?text="
# x.com 431s when the TOTAL request (URL + cookies + headers) is too big. A
# logged-in browser sends ~2-4 KB of cookies/headers, so the safe URL length is
# far below the ~14,300 no-cookie ceiling. 10,000 leaves ~4.4 KB of headroom.
URL_CEIL = 10000
MAXCHUNK = URL_CEIL - len(PREFIX)

HOOK = "I made minecraft fit in a twitter post"

EXPLAIN = (
    "yes, it literally is. the whole game is in this thread.\n\n"
    "it works by abusing X's compose-link trick: every link counts as just 23 "
    "characters no matter how long the URL really is, so each link below smuggles "
    "a chunk of data past the character limit. this is probably the most "
    "compressed copy of Minecraft Classic but... even so, it takes {n} of them to "
    "hold the whole game.\n\n"
    "how the thread is laid out:\n"
    "tweet 2 is the decoder, a tiny self-contained page.\n"
    "tweets 3 and onward are the game itself, split into parts.\n\n"
    "to play:\n"
    "1) open tweet 2's link, copy the whole  data:text/html;base64,...  line it "
    "shows, and paste it into your browser's address bar. that opens the decoder "
    "(or save that line as decoder.html and open it).\n"
    "2) copy every part after it (tweets 3 and on), paste them all into the decoder, "
    "and hit Play. Minecraft runs right in your browser, nothing leaves your machine.\n\n"
    "not the copyright holder. Minecraft is (c) Mojang / Microsoft. this is a "
    "technical art demo, unaffiliated and not endorsed.\n\n"
    "made with funmaxxing by Kuber Mehta (kuber.studio)"
)


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def link_for_text(text: str) -> str:
    """compose link for arbitrary text/base64 (percent-encode everything)."""
    return PREFIX + urllib.parse.quote(text, safe="")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--outdir", default="TWEETS")
    ap.add_argument("--decoder", default=os.path.join(os.path.dirname(__file__), "decoder.html"))
    ap.add_argument("--deflate", help="precompressed raw-DEFLATE blob (e.g. zopfli); else zlib -9")
    args = ap.parse_args()

    data = open(args.input, "rb").read()
    if args.deflate:
        comp = open(args.deflate, "rb").read(); how = "provided"
    else:
        co = zlib.compressobj(level=9, wbits=-15); comp = co.compress(data) + co.flush(); how = "zlib -9"

    payload = b64url(comp)
    chunks = [payload[i:i + MAXCHUNK] for i in range(0, len(payload), MAXCHUNK)]

    decoder_html = open(args.decoder, "rb").read()
    decoder_b64 = base64.b64encode(decoder_html).decode()   # standard base64 -> data:text/html;base64,

    os.makedirs(args.outdir, exist_ok=True)
    files = []

    def write(name, content):
        with open(os.path.join(args.outdir, name), "w", encoding="utf-8") as f:
            f.write(content)
        files.append((name, content))

    decoder_data_url = "data:text/html;base64," + decoder_b64

    write("tweet-001.txt", HOOK + "\n\n" + link_for_text(EXPLAIN.format(n=len(chunks))))
    write("tweet-002.txt",
          "tweet 2 is the decoder. open this link, copy the data: URL it shows, "
          "and paste it into your address bar:\n\n"
          + link_for_text(decoder_data_url))
    for i, c in enumerate(chunks):
        write(f"tweet-{i + 3:03d}.txt", PREFIX + c)   # base64url is already URL-safe

    longest = max(len(c.split("\n")[-1]) for _, c in files)
    print(f"input           : {len(data):>12,} bytes")
    print(f"raw DEFLATE     : {len(comp):>12,} bytes  ({how})")
    print(f"decoder.html    : {len(decoder_html):>12,} bytes  -> base64 {len(decoder_b64):,} chars (fits 1 tweet)")
    print(f"game chunks     : {len(chunks):>12} tweets")
    print(f"TOTAL THREAD    : {len(files):>12} tweets  (1 hook + 1 decoder + {len(chunks)} data)")
    print(f"longest link    : {longest:>12,} chars  (ceiling {URL_CEIL:,}) {'OK' if longest <= URL_CEIL else 'OVER!'}")
    print(f"written to      : {args.outdir}/")


if __name__ == "__main__":
    main()
