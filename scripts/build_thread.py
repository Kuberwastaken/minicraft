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
    "2) in the decoder, hit 'auto-fill from github' (it grabs every part for you), "
    "or paste tweets 3-on in yourself, then hit Play. Minecraft runs right in your "
    "browser, nothing leaves your machine.\n\n"
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
    ap.add_argument("--deflate", help="precompressed blob to ship as-is (e.g. zopfli deflate or LZMA); else zlib -9")
    ap.add_argument("--unlinked", default="unlinked-tweets",
                    help="also write the decoded text= of each tweet here (for local testing without X)")
    args = ap.parse_args()

    data = open(args.input, "rb").read()
    if args.deflate:
        comp = open(args.deflate, "rb").read(); how = "provided"
    else:
        co = zlib.compressobj(level=9, wbits=-15); comp = co.compress(data) + co.flush(); how = "zlib -9"

    # Game parts are posted as DIRECT tweet text (not compose links), so each can be up to
    # X's long-post limit (25,000 chars; base64url is ASCII, weight 1). That's ~2.4x more than
    # a compose link's ~10k URL cap -> far fewer tweets. (Posting these needs an X Premium acct.)
    DATA_CHUNK = 24000
    payload = b64url(comp)
    chunks = [payload[i:i + DATA_CHUNK] for i in range(0, len(payload), DATA_CHUNK)]

    decoder_html = open(args.decoder, "rb").read()
    decoder_b64 = base64.b64encode(decoder_html).decode()   # standard base64 -> data:text/html;base64,

    os.makedirs(args.outdir, exist_ok=True)
    os.makedirs(args.unlinked, exist_ok=True)
    files = []

    def write(name, link, unlinked):
        # link (compose URL / tweet text) -> TWEETS/ ; unlinked (decoded text=) -> unlinked-tweets/
        with open(os.path.join(args.outdir, name), "w", encoding="utf-8") as f:
            f.write(link)
        with open(os.path.join(args.unlinked, name), "w", encoding="utf-8") as f:
            f.write(unlinked)
        files.append((name, link))

    # intro text is editable in scripts/intro.txt (survives rebuilds); {n} = total tweets
    intro_path = os.path.join(os.path.dirname(__file__), "intro.txt")
    template = open(intro_path, encoding="utf-8").read().rstrip("\n") if os.path.exists(intro_path) else EXPLAIN
    explain = template.replace("{n}", str(len(chunks) + 2))
    decoder_data_url = "data:text/html;base64," + decoder_b64

    write("tweet-001.txt", HOOK + "\n\n" + link_for_text(explain), explain)
    write("tweet-002.txt",
          "tweet 2 is the decoder. open this link, copy the data: URL it shows, "
          "and paste it into your address bar:\n\n" + link_for_text(decoder_data_url),
          decoder_data_url)
    for i, c in enumerate(chunks):
        write(f"tweet-{i + 3:03d}.txt", c, c)   # raw base64url as direct tweet text (Premium long post)

    # manifest = number of game parts, so the decoder's "auto-fill from github" knows how many to fetch
    with open(os.path.join(args.outdir, "manifest.txt"), "w", encoding="utf-8") as f:
        f.write(str(len(chunks)))

    link_len = max(len(c.split("\n")[-1]) for n, c in files if n in ("tweet-001.txt", "tweet-002.txt"))
    data_len = max((len(c) for n, c in files if n not in ("tweet-001.txt", "tweet-002.txt")), default=0)
    print(f"input           : {len(data):>12,} bytes")
    print(f"raw DEFLATE     : {len(comp):>12,} bytes  ({how})")
    print(f"decoder.html    : {len(decoder_html):>12,} bytes  -> base64 {len(decoder_b64):,} chars (fits 1 tweet)")
    print(f"game chunks     : {len(chunks):>12} tweets  (direct text, up to 24,000 chars each)")
    print(f"TOTAL THREAD    : {len(files):>12} tweets  (1 hook + 1 decoder + {len(chunks)} data)")
    print(f"longest link    : {link_len:>12,} chars  (URL cap {URL_CEIL:,}) {'OK' if link_len <= URL_CEIL else 'OVER!'}")
    print(f"longest data tw : {data_len:>12,} chars  (X premium 25,000) {'OK' if data_len <= 25000 else 'OVER!'}")
    print(f"written to      : {args.outdir}/  and  {args.unlinked}/ (decoded, for local testing)")


if __name__ == "__main__":
    main()
