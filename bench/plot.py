#!/usr/bin/env python3
"""Median execution times and speedup graphs from bench/results.csv."""
import csv, os, statistics, sys
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

src = sys.argv[1] if len(sys.argv) > 1 else "bench/results.csv"
out = sys.argv[2] if len(sys.argv) > 2 else "bench/figures"
os.makedirs(out, exist_ok=True)
runs = defaultdict(list)
with open(src) as f:
    for row in csv.DictReader(f):
        runs[(row["dataset"], row["impl"], int(row["workers"]))].append(float(row["ms"]))
med = {k: statistics.median(v) for k, v in runs.items()}
datasets = sorted({k[0] for k in med})
impls = [("shm", "Shared memory", "#2a6fdb", "o"), ("pipe", "Message passing (pipes)", "#e07b00", "s"),
         ("thread", "Multithreading (pthreads)", "#1a9e5a", "^")]
ns = sorted({k[2] for k in med})

with open(os.path.join(out, "medians.csv"), "w") as f:
    f.write("dataset,impl,workers,median_ms,speedup\n")
    for ds in datasets:
        for impl, *_ in impls:
            for n in ns:
                if (ds, impl, n) in med:
                    f.write(f"{ds},{impl},{n},{med[(ds, impl, n)]:.3f},{med[(ds, impl, 1)] / med[(ds, impl, n)]:.3f}\n")

for ds in datasets:
    fig, ax = plt.subplots(figsize=(5.2, 3.4), dpi=150)
    for impl, label, color, marker in impls:
        xs = [n for n in ns if (ds, impl, n) in med]
        ax.plot(xs, [med[(ds, impl, 1)] / med[(ds, impl, n)] for n in xs], marker=marker, color=color, label=label, lw=1.8)
    ax.plot(ns, ns, ls=":", color="#999", lw=1, label="Ideal (linear)")
    ax.set_xscale("log", base=2); ax.set_xticks(ns); ax.set_xticklabels([str(n) for n in ns])
    top = max(4.5, max(med[(ds, i, 1)] / med[(ds, i, n)] for i, *_ in impls for n in ns if (ds, i, n) in med) * 1.15)
    ax.set_ylim(0, top)
    ax.set_xlabel("Number of workers (N)"); ax.set_ylabel("Speedup  T(1) / T(N)")
    ax.set_title(f"{ds}: speedup vs. number of workers"); ax.grid(alpha=.3); ax.legend(fontsize=7, loc="upper left")
    fig.tight_layout(); fig.savefig(os.path.join(out, f"speedup_{ds}.png")); plt.close(fig)
print("wrote", out)
