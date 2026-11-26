#!/usr/bin/env python3
"""Independent reference implementation (test oracle only).
Prints the expected output for the given files in the same format."""
import os, re, sys
from collections import Counter

for path in sys.argv[1:]:
    with open(path, 'rb') as f:
        words = re.findall(rb'[A-Za-z]+', f.read())
    c = Counter(w.lower() for w in words)
    top = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    print(f"File: {os.path.basename(path)}")
    if not top:
        print("No words found.")
    for w, n in top:
        print(f"{w.decode():<14} {n}")
