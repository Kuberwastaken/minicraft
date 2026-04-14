#!/usr/bin/env python3
"""
Compresses minified-index.html into a self-extracting HTML payload,
then hides it as Unicode variation selectors after visible tweet text.

Decoded output is a standalone .html file — open it in a browser to play Minecraft.
"""
import zlib, base64, sys, os

WRAPPER = (
    '<script type="module">'
    'document.open();'
    'document.write(await new Response('
    'new Response(Uint8Array.from(atob("{b64}"),c=>c.charCodeAt(0))).body'
    '.pipeThrough(new DecompressionStream("gzip"))'
    ').text());'
    'document.close();'
    '</script>'
)

VISIBLE_TEXT = "This tweet contains the entirity of minecraft"


def byte_to_vs(b):
    return chr(0xFE00 + b) if b < 16 else chr(0xE0100 + b - 16)


def encode(input_path, output_path):
    with open(input_path, "rb") as f:
        data = f.read()

    # gzip compress at max level
    compressor = zlib.compressobj(level=9, wbits=31)
    compressed = compressor.compress(data) + compressor.flush()

    # wrap in self-extracting HTML
    b64 = base64.b64encode(compressed).decode("ascii")
    html = WRAPPER.format(b64=b64)
    html_bytes = html.encode("utf-8")

    # encode every byte as a variation selector, appended after visible text
    result = VISIBLE_TEXT
    for byte in html_bytes:
        result += byte_to_vs(byte)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"Original:             {len(data):>12,} bytes")
    print(f"Gzip-9 compressed:    {len(compressed):>12,} bytes  ({len(compressed)/len(data)*100:.1f}%)")
    print(f"Self-extracting HTML: {len(html_bytes):>12,} bytes")
    print(f"Variation selectors:  {len(result):>12,} chars  (visible: {len(VISIBLE_TEXT)})")
    print(f"\nOutput: {output_path}")
    print("Decode with: python decode.py")


if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    inp = sys.argv[1] if len(sys.argv) > 1 else os.path.join(base, "minified-index.html")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(base, "tweet.txt")
    encode(inp, out)
