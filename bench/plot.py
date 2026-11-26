#!/usr/bin/env python3
"""Median execution times and speedup graphs from bench/results.csv."""
import csv, os, statistics, sys
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"axes.edgecolor": "#bbbbbb", "axes.labelcolor": "#333333", "xtick.color": "#555555",
                     "ytick.color": "#555555", "axes.spines.top": False, "axes.spines.right": False,
                     "font.size": 9, "legend.frameon": False})

src = sys.argv[1] if len(sys.argv) > 1 else "bench/results.csv"
out = sys.argv[2] if len(sys.argv) > 2 else "bench/figures"
os.makedirs(out, exist_ok=True)
runs = defaultdict(list)
with open(src) as f:
    for row in csv.DictReader(f):
        runs[(row["dataset"], row["impl"], int(row["workers"]))].append(float(row["ms"]))
med = {k: statistics.median(v) for k, v in runs.items()}
datasets = sorted({k[0] for k in med})
impls = [("shm", "Shared memory", "#257de0", "o"), ("pipe", "Message passing (pipes)", "#f47230", "s"),
         ("thread", "Multithreading (pthreads)", "#00b894", "^")]
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
        ax.plot(xs, [med[(ds, impl, 1)] / med[(ds, impl, n)] for n in xs], marker=marker, ms=6, color=color, label=label, lw=2, mec="white", mew=1)
    ax.plot(ns, ns, ls=":", color="#999", lw=1, label="Ideal (linear)")
    ax.set_xscale("log", base=2); ax.set_xticks(ns); ax.set_xticklabels([str(n) for n in ns])
    top = max(4.5, max(med[(ds, i, 1)] / med[(ds, i, n)] for i, *_ in impls for n in ns if (ds, i, n) in med) * 1.15)
    ax.set_ylim(0, top)
    ax.set_xlabel("Number of workers (N)"); ax.set_ylabel("Speedup  T(1) / T(N)")
    ax.set_title(f"{ds}: speedup vs. number of workers"); ax.grid(alpha=.25, lw=.6); ax.legend(fontsize=7, loc="upper left")
    fig.tight_layout(); fig.savefig(os.path.join(out, f"speedup_{ds}.png")); plt.close(fig)

# extra experiments (bench/extra.csv), if present
extra = os.path.join(os.path.dirname(src), "extra.csv")
if os.path.exists(extra):
    rows = list(csv.DictReader(open(extra)))
    order = ["64K", "256K", "1M", "4M", "8M", "16M", "32M", "128M"]
    fig, ax = plt.subplots(figsize=(5.2, 3.2), dpi=150)
    for impl, label, color, marker in impls:
        pts = {r["param"]: float(r["median_ms"]) for r in rows if r["experiment"] == "chunk" and r["impl"] == impl}
        xs = [c for c in order if c in pts]
        ax.plot(range(len(xs)), [pts[c] for c in xs], marker=marker, ms=6, color=color, label=label, lw=2, mec="white", mew=1)
    ax.set_xticks(range(len(order))); ax.set_xticklabels(order)
    ax.set_xlabel("Chunk threshold (D2 = one 100 MB file)"); ax.set_ylabel("Median time (ms), N = 4")
    ax.set_title("Chunk size vs. execution time"); ax.set_ylim(0); ax.grid(alpha=.25, lw=.6); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(os.path.join(out, "chunk_sweep.png")); plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.2, 3.2), dpi=150)
    for mode, label, color, marker in [("tuned", "Heap grows in 64 MiB steps (M_TOP_PAD)", "#00b894", "^"),
                                       ("default", "Default glibc malloc", "#7f7f7f", "D")]:
        pts = {int(r["workers"]): float(r["median_ms"]) for r in rows if r["experiment"] == "malloc" and r["param"] == mode}
        xs = sorted(pts)
        ax.plot(xs, [pts[n] for n in xs], marker=marker, ms=6, color=color, label=label, lw=2, mec="white", mew=1)
    ax.set_xscale("log", base=2); ax.set_xticks(ns); ax.set_xticklabels([str(n) for n in ns])
    ax.set_xlabel("Number of threads (N)"); ax.set_ylabel("Median time (ms), D2")
    ax.set_title("Multithreaded version: effect of malloc heap growth"); ax.set_ylim(0); ax.grid(alpha=.25, lw=.6); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(os.path.join(out, "thread_malloc.png")); plt.close(fig)
print("wrote", out)
