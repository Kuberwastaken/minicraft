#!/usr/bin/env python3
"""
Extracts the hidden self-extracting HTML from a variation-selector-encoded text file.

Open the decoded .html output in any browser to play Minecraft — no server needed.
"""
import sys, os


def vs_to_byte(c):
    cp = ord(c)
    if 0xFE00 <= cp <= 0xFE0F:
        return cp - 0xFE00
    elif 0xE0100 <= cp <= 0xE01EF:
        return cp - 0xE0100 + 16
    return None


def decode(input_path, output_path):
    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()

    payload = bytearray()
    started = False
    for c in text:
        b = vs_to_byte(c)
        if b is not None:
            started = True
            payload.append(b)
        elif started:
            break

    with open(output_path, "wb") as f:
        f.write(payload)

    print(f"Extracted {len(payload):,} bytes → {output_path}")
    print("Open the .html file in a browser to play Minecraft!")


if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    inp = sys.argv[1] if len(sys.argv) > 1 else os.path.join(base, "tweet.txt")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(base, "decoded.html")
    decode(inp, out)
