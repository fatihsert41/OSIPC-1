#!/usr/bin/env python3
"""Generate synthetic text datasets D1..D5 (sizes from the assignment).

Words follow a Zipf-like distribution over a 60 000-word vocabulary (a few
hundred common English words + generated words), mixed with capital letters,
punctuation, digits and newlines, so the data looks like natural text.
If the official datasets from AYBUZEM are available, put them in the same
directory layout (data/D1 ... data/D5) and skip this script."""
import os, random, sys, zlib

MB = 1 << 20
DATASETS = {
    "D1": [("d1_small.txt", 1)],
    "D2": [("d2_large.txt", 100)],
    "D3": [(f"d3_part{i}.txt", 25) for i in range(1, 5)],
    "D4": [("d4_1mb.txt", 1), ("d4_5mb.txt", 5), ("d4_20mb.txt", 20), ("d4_100mb.txt", 100)],
    "D5": [("d5_1mb.txt", 1), ("d5_3mb.txt", 3), ("d5_8mb.txt", 8), ("d5_15mb.txt", 15),
           ("d5_30mb.txt", 30), ("d5_50mb.txt", 50), ("d5_75mb.txt", 75), ("d5_100mb.txt", 100)],
}
COMMON = ("the of and to a in is it you that he was for on are with as i his they be at one "
          "have this from or had by not word but what some we can out other were all there "
          "when up use your how said an each she which do their time if will way about many "
          "then them write would like so these her long make thing see him two has look more "
          "day could go come did number sound no most people my over know water than call "
          "first who may down side been now find any new work part take get place made live "
          "where after back little only round man year came show every good me give our under "
          "name very through just form sentence great think say help low line differ turn cause "
          "much mean before move right boy old too same tell does set three want air well also "
          "play small end put home read hand port large spell add even land here must big high "
          "such follow act why ask men change went light kind off need house picture try us "
          "again animal point mother world near build self earth father linux kernel process "
          "thread memory shared pipe system operating file data signal").split()

def build_vocab(rng, n=60000):
    letters = "abcdefghijklmnopqrstuvwxyz"
    vocab, seen = list(COMMON), set(COMMON)
    while len(vocab) < n:
        w = "".join(rng.choice(letters) for _ in range(rng.choice([2, 3, 4, 5, 5, 6, 6, 7, 7, 8, 9, 10, 12, 14])))
        if w not in seen:
            seen.add(w); vocab.append(w)
    weights = [1.0 / (r + 1) ** 1.05 for r in range(n)]
    cum, s = [], 0.0
    for w in weights:
        s += w; cum.append(s)
    return vocab, cum

def write_file(path, size, vocab, cum, rng):
    seps = [" "] * 40 + ["\n"] * 4 + [", ", ". ", "; ", "! ", "? ", " - ", " 2026 ", " (", ") "]
    with open(path, "wb") as f:
        written = 0
        while written < size:
            words = rng.choices(vocab, cum_weights=cum, k=200000)
            out = []
            for w in words:
                r = rng.random()
                if r < 0.03: w = w.capitalize()
                elif r < 0.035: w = w.upper()
                out.append(w); out.append(rng.choice(seps))
            b = "".join(out).encode()
            b = b[: size - written]
            f.write(b); written += len(b)

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "bench/data"
    rng = random.Random(2026)
    vocab, cum = build_vocab(rng)
    cache = {}
    for ds, files in DATASETS.items():
        d = os.path.join(root, ds); os.makedirs(d, exist_ok=True)
        for name, mb in files:
            p = os.path.join(d, name)
            if os.path.exists(p) and os.path.getsize(p) == mb * MB:
                continue
            print(f"generating {p} ({mb} MB)", flush=True)
            write_file(p, mb * MB, vocab, cum, random.Random(zlib.crc32(f"{ds}/{name}".encode())))

if __name__ == "__main__":
    main()
