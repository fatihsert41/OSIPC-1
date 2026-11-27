#!/usr/bin/env python3
"""Build report/report.html (then report.pdf via html2pdf.js) from the
benchmark CSV files and figures. Usage: python3 report/build_report.py

Edit the STUDENT and TEST COMPUTER values below before building."""
import base64, csv, os, statistics
from collections import defaultdict

# ---------------------------------------------------------------- edit me
STUDENT = "Name Surname"
STUDENT_ID = "Student ID"
ENV = [
    ("CPU", "Intel® Xeon® Processor @ 2.10 GHz (virtual machine), 4 cores, 1 thread per core"),
    ("Logical processors", "4"),
    ("RAM", "16 GB (15.7 GiB)"),
    ("Operating system", "Ubuntu 24.04.5 LTS, Linux kernel 6.18 (x86-64)"),
    ("Compiler", "gcc 13.3.0, <code>-O2 -std=gnu11</code>"),
]
NCPU = 4
# ------------------------------------------------------------------------

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, "bench")
NS = [1, 2, 4, 8, 16]
IMPLS = [("shm", "Shared memory"), ("pipe", "Pipes"), ("thread", "Threads")]
LABEL = dict(IMPLS)


def img(path, width="100%"):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f'<img src="data:image/png;base64,{b64}" style="width:{width}">'


def load_medians(path):
    runs = defaultdict(list)
    for r in csv.DictReader(open(path)):
        runs[(r["dataset"], r["impl"], int(r["workers"]))].append(float(r["ms"]))
    return {k: statistics.median(v) for k, v in runs.items()}


def load_extra(path):
    d = {}
    for r in csv.DictReader(open(path)):
        d[(r["experiment"], r["impl"], r["param"], int(r["workers"]))] = float(r["median_ms"])
    return d


def load_nosplit(path):
    d = {}
    if os.path.exists(path):
        for line in open(path):
            _, _, impl, n, v = line.split()
            d[(impl, int(n[2:]))] = float(v)
    return d


med = load_medians(os.path.join(B, "results.csv"))
ext = load_extra(os.path.join(B, "extra.csv"))
nos = load_nosplit(os.path.join(B, "d4_nosplit.txt"))
syn_dir = os.path.join(B, "synthetic")
syn = load_medians(os.path.join(syn_dir, "results.csv"))
syn_ext = load_extra(os.path.join(syn_dir, "extra.csv"))

m = lambda ds, i, n: f"{med[(ds, i, n)]:.1f}"
sp = lambda ds, i, n: med[(ds, i, 1)] / med[(ds, i, n)]
e = lambda exp, i, p, n: ext.get((exp, i, p, n), float("nan"))
ds_large = ["D2", "D3", "D4", "D5"]


def fastest(ds, n):
    return min(IMPLS, key=lambda x: med[(ds, x[0], n)])[0]



def median_table():
    h = "<table><tr><th>Dataset</th><th>Implementation</th>" + "".join(f"<th>N={n}</th>" for n in NS) + "<th>Max speedup</th></tr>"
    for ds in ["D1"] + ds_large:
        best = min(med[(ds, i, n)] for i, _ in IMPLS for n in NS)
        for j, (impl, label) in enumerate(IMPLS):
            cells = "".join(f'<td class="{"best" if med[(ds, impl, n)] == best else ""}">{med[(ds, impl, n)]:.1f}</td>' for n in NS)
            first = f'<td rowspan="3"><b>{ds}</b></td>' if j == 0 else ""
            h += f"<tr>{first}<td>{label}</td>{cells}<td>{max(sp(ds, impl, n) for n in NS):.2f}</td></tr>"
    return h + "</table>"



CH = ["64K", "256K", "1M", "4M", "8M", "16M", "32M", "128M"]
t_chunk = "<table><tr><th>Chunk threshold</th>" + "".join(f"<th>{c}</th>" for c in CH) + "</tr>" + "".join(
    f"<tr><td>{l}</td>" + "".join(f"<td>{e('chunk', i, c, 4):.0f}</td>" for c in CH) + "</tr>" for i, l in IMPLS) + "</table>"
t_d1 = "<table><tr><th>D1, 128 KiB chunks</th>" + "".join(f"<th>N={n}</th>" for n in NS) + "</tr>" + "".join(
    f"<tr><td>{l}</td>" + "".join(f"<td>{e('d1split', i, '128K', n):.2f}</td>" for n in NS) + "</tr>" for i, l in IMPLS) + "</table>"
t_over = "<table><tr><th>10 tiny files</th><th>N=1</th><th>N=10</th></tr>" + "".join(
    f"<tr><td>{l}</td><td>{e('overhead', i, '10tiny', 1):.2f}</td><td>{e('overhead', i, '10tiny', 10):.2f}</td></tr>" for i, l in IMPLS) + "</table>"
t_nos = "<table><tr><th>D4</th><th>no split N=1</th><th>no split N=4</th><th>speedup</th><th>8 MiB chunks, speedup N=4</th></tr>" + "".join(
    f"<tr><td>{l}</td><td>{nos.get((i, 1), 0):.0f}</td><td>{nos.get((i, 4), 0):.0f}</td><td>{nos.get((i, 1), 0) / max(nos.get((i, 4), 1), 1e-9):.2f}</td><td>{sp('D4', i, 4):.2f}</td></tr>" for i, l in IMPLS) + "</table>"
t_syn = "<table><tr><th>Synthetic D2 (60 000-word vocabulary)</th><th>N=1</th><th>N=4</th><th>N=16</th></tr>" + "".join(
    f"<tr><td>{l}</td><td>{syn[('D2', i, 1)]:.0f}</td><td>{syn[('D2', i, 4)]:.0f}</td><td>{syn[('D2', i, 16)]:.0f}</td></tr>" for i, l in IMPLS) + "</table>"
sm = lambda mode, n: syn_ext.get(("malloc", "thread", mode, n), float("nan"))

# numbers used in the text
avg_sp4 = {i: statistics.mean(sp(ds, i, 4) for ds in ds_large) for i, _ in IMPLS}
fast4 = {ds: fastest(ds, 4) for ds in ds_large}
thr_1 = 100.0 / (med[("D2", "thread", 1)] / 1e3)  # MB/s, one core
d2_1 = {i: med[("D2", i, 1)] for i, _ in IMPLS}

html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Homework I Report</title>
<style>
body {{ font-family: 'DejaVu Serif', Georgia, serif; font-size: 9.8pt; line-height: 1.36; color: #111; background: #fff; }}
h1 {{ font-size: 17pt; margin: 0 0 2px; }} h2 {{ font-size: 12.5pt; margin: 14px 0 5px; border-bottom: 1px solid #ccc; }}
h3 {{ font-size: 10.6pt; margin: 9px 0 3px; }}
.sub {{ color: #444; margin-bottom: 8px; }}
table {{ border-collapse: collapse; margin: 5px 0 8px; font-size: 8.5pt; font-family: 'DejaVu Sans', Arial, sans-serif; }}
th, td {{ border: 1px solid #bbb; padding: 2px 6px; text-align: right; }} th {{ background: #f0f0f0; }}
td:first-child, th:first-child {{ text-align: left; }} td.best {{ font-weight: bold; background: #eef6ee; }}
code {{ font-size: 8.8pt; background: #f4f4f4; padding: 0 2px; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 4px 10px; }}
.grid3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 2px 6px; }}
.cap {{ font-size: 8.6pt; color: #333; text-align: center; margin: 0 0 6px; }}
ul, ol {{ margin: 3px 0 6px; padding-left: 20px; }} p {{ margin: 4px 0 6px; text-align: justify; }}
.q {{ font-weight: bold; margin-top: 8px; }} .avoid {{ break-inside: avoid; }}
</style></head><body>
<h1>Multiprocess and Multithreaded MapReduce: Word Frequency Analysis</h1>
<div class="sub">Operating Systems 2026–2027 Fall, Homework I &nbsp;·&nbsp; {STUDENT} &nbsp;·&nbsp; {STUDENT_ID}</div>

<h2>1. Overview and test computer</h2>
<p>The same MapReduce-style application is implemented three times: with processes and POSIX shared memory
(<code>mapreduce_shm</code>), with processes and pipes (<code>mapreduce_pipe</code>), and with POSIX threads
(<code>mapreduce_thread</code>). All three programs share the same tokenizer, hash table, partitioning and output code, so
they differ only in how work is distributed and how partial results reach the master. They produce identical output.
They match the provided expected results and, on all files of D1–D5, an independent Python reference.
<code>make test</code> runs 145 checks: the sample files, chunk sizes of 1–7 bytes that cut almost every word, random
files, and error cases. All 145 pass, and the programs are clean under AddressSanitizer, UBSan and ThreadSanitizer.</p>
<table>{"".join(f'<tr><th>{k}</th><td style="text-align:left">{v}</td></tr>' for k, v in ENV)}</table>

<h2>2. Program architecture</h2>
<h3>2.1 Common pipeline</h3>
<ol>
<li><b>Input and partitioning.</b> Each file is checked with <code>stat()</code>. A file larger than the chunk
threshold (<code>-c</code>, default 8 MiB) is split into <i>k</i> = ⌈size / threshold⌉ nearly equal byte ranges.
Every file, including an empty one, becomes at least one task (file index, start, end).</li>
<li><b>Map.</b> A mapper reads its range with <code>pread()</code> through a 64 KiB buffer. It converts ASCII letters to
lowercase and treats every other byte as a separator, so <code>world123test</code> gives <i>world</i> and <i>test</i>.
Words are counted in a local open-addressing hash table (FNV-1a hash, linear probing, words stored in an arena).
<b>Boundary rule:</b> a word belongs to the chunk that contains its first letter. If the byte before
<code>start</code> is a letter, the mapper skips the leading letters, because they belong to the previous chunk.
If a word is still open at <code>end</code>, the mapper reads past <code>end</code> until the word finishes.
This counts every word exactly once.</li>
<li><b>Reduce.</b> Partial tables of the same file are merged by adding the counts of equal words. Tables of
different files are never mixed.</li>
<li><b>Output.</b> For each file, in command-line order, a single pass with insertion keeps the top 5 words, sorted by
descending count with ties sorted alphabetically. If there are no words, the program prints <i>No words found.</i></li>
</ol>
<p>Each program limits the number of concurrently active mappers to <i>N</i>. Tasks beyond <i>N</i> are scheduled
over time through a worker pool.</p>

<h3>2.2 Implementation I: shared memory</h3>
<p>The master creates a <b>control region</b> with <code>shm_open</code>, <code>ftruncate</code> and
<code>mmap(MAP_SHARED)</code>. It holds one entry per task: file, byte range, status and result size. The master
<code>fork()</code>s one worker per task, keeping at most <i>N</i> alive at any time. A worker counts its range,
creates its own <b>result segment</b> (<code>/mr_res_&lt;pid&gt;_&lt;task&gt;</code>) sized exactly for its
serialized table, writes the table into it, records the size and <code>status = 1</code> in the control region,
and calls <code>_exit()</code>. <b>Synchronization:</b> the master reads an entry only after <code>waitpid()</code>
reports that worker's exit, so the write has happened before the read and no lock is needed. Each control entry
and each segment has exactly one writer. The master then opens and maps the segment, merges it, and releases it with
<code>munmap</code>, <code>close</code> and <code>shm_unlink</code>. Merging happens while the other workers are
still running. If an error occurs, the remaining workers are killed and reaped and every segment is unlinked.
The test suite checks that no <code>/dev/shm/mr_*</code> objects remain.</p>

<h3>2.3 Implementation II: message passing</h3>
<p>The master <code>fork()</code>s a pool of <i>W</i> = min(<i>N</i>, tasks) long-lived workers, each with two
pipes. The task pipe carries a fixed-size message (task id, file index, start, end, path length) followed by the
file path. The result pipe carries a header (task id, status, byte count) followed by the serialized table. Each
worker closes the ends it does not use, including the master-side ends of the pipes of previously created
workers, so EOF is delivered correctly. The master sends one task to each worker and then <code>poll()</code>s the
result pipes. When a result arrives, the master reads it completely, merges it, and sends that worker the next
task. When no tasks are left, the master closes the worker's task pipe, the worker sees EOF and exits, and the
master reaps it with <code>waitpid()</code>. <b>Synchronization</b> comes from the blocking pipe semantics alone.
<code>SIGPIPE</code> is ignored, so a dead worker shows up as an error instead of killing the master.</p>

<h3>2.4 Implementation III: POSIX threads</h3>
<p>The main thread creates <i>T</i> = min(<i>N</i>, tasks) threads with <code>pthread_create()</code>. The threads
take task indices from a shared counter that is protected by a <b>mutex</b>. This counter and an error flag are the
only shared mutable data. Each thread counts into its own private table per file, so chunks of the same file that
the same thread processes are combined locally and the hot path needs no lock. After <code>pthread_join()</code>
of all threads, the main thread alone performs the reduce step, merging at most <i>T</i> tables per file. It takes
over the first table without copying. The program also calls <code>mallopt(M_TOP_PAD, 64 MiB)</code>, so malloc
grows each thread's heap in large steps; §6 explains why.</p>

<h2>3. Experimental setup</h2>
<p>The official D1–D5 datasets from AYBÜZEM were used:</p>
<ul>
<li><b>D1:</b> 1 MB</li>
<li><b>D2:</b> 100 MB</li>
<li><b>D3:</b> 4 × 25 MB</li>
<li><b>D4:</b> 1, 5, 20 and 100 MB</li>
<li><b>D5:</b> 1, 5, 10, 25, 50, 75, 100 and 2 MB</li>
</ul>
<p>Here 1 MB = 10<sup>6</sup> bytes. The files repeat the same English paragraph, so each file has only 26 distinct
words. Each program measures itself with <code>clock_gettime(CLOCK_MONOTONIC)</code>. Timing starts just before
partitioning and parallel setup, and stops after the results have been printed and all workers and IPC objects have
been cleaned up. Output goes to <code>/dev/null</code>. Every configuration (3 implementations × 5 datasets ×
<i>N</i> ∈ {{1, 2, 4, 8, 16}}) was run 5 times, and the median is reported. Files were warm in the page cache, and
one warm-up run was done per dataset and implementation. The default chunk threshold was 8 MiB, which gives 1, 12,
12, 17 and 35 tasks for D1–D5. Repeated runs of the same configuration varied by roughly 5–20%, so smaller
differences should not be over-interpreted. All scripts are in <code>bench/</code> (<code>make bench</code>).</p>

<div class="avoid"><h2>4. Results</h2>
<div class="grid3">
<div>{img(os.path.join(B, "figures", "speedup_D1.png"))}</div><div>{img(os.path.join(B, "figures", "speedup_D2.png"))}</div>
<div>{img(os.path.join(B, "figures", "speedup_D3.png"))}</div><div>{img(os.path.join(B, "figures", "speedup_D4.png"))}</div>
<div>{img(os.path.join(B, "figures", "speedup_D5.png"))}</div><div>{img(os.path.join(B, "figures", "chunk_sweep.png"))}</div>
</div>
<div class="cap">Figures 1–5: speedup T(1)/T(N) for D1–D5 (dotted line = linear speedup). Figure 6: execution time vs. chunk threshold (D2, N = 4).</div></div>
<div class="avoid">
<p><b>Table 1.</b> Median execution time in ms (5 runs). The fastest value for each dataset is shaded.</p>
{median_table()}
</div>

<h2>5. Additional experiments (official data)</h2>
<div class="avoid"><p><b>Table 2.</b> Chunk threshold sweep, D2 (one 100 MB file), N = 4, median ms. With 128M the file is not split.</p>{t_chunk}</div>
<div class="grid avoid"><div>
<p><b>Table 3.</b> D1 split into 128 KiB chunks, median ms.</p>{t_d1}
</div><div>
<p><b>Table 4.</b> Fixed overhead: 10 tiny files (sample inputs), median of 21 runs, in ms.</p>{t_over}
</div></div>
<div class="avoid"><p><b>Table 5.</b> D4 with one task per file (<code>-c 1G</code>), median ms, compared with the
default 8 MiB chunks.</p>{t_nos}</div>

<h2>6. Supplementary experiment: a large vocabulary</h2>
<p>The official files have only 26 distinct words, so the frequency tables are tiny and almost no result data has to
be moved between workers. To see how the designs behave when the partial results are large, the same experiments
were also run on synthetic text with the same file sizes and a Zipf-distributed vocabulary of 60,000 words
(<code>bench/gen_data.py</code>; results in <code>bench/synthetic/</code>).</p>
<div class="grid avoid"><div>
<p><b>Table 6.</b> Synthetic D2, median ms.</p>{t_syn}
<p>With large tables, threads are clearly fastest with one worker, because the process versions must serialize
every partial table and parse and hash it again in the master. Without the <code>M_TOP_PAD</code> setting,
16 threads needed {sm('default', 16):.0f} ms instead of {sm('tuned', 16):.0f} ms, and the system time rose from
0.06 s to 0.45 s (Figure 7). glibc gives every thread its own malloc arena and grows it in small
<code>mprotect</code> steps, and each step takes the process-wide address-space lock in write mode. This stalls
the page faults of all other threads. Processes have separate address spaces and do not suffer from this.
With the official data the setting makes no difference
({e('malloc', 'thread', 'default', 16):.0f} vs. {e('malloc', 'thread', 'tuned', 16):.0f} ms at N = 16),
because the tables stay small.</p>
</div><div>{img(os.path.join(syn_dir, "figures", "thread_malloc.png"))}<div class="cap">Figure 7: synthetic D2, threads with and without the malloc heap-growth setting.</div></div></div>

<h2>7. Discussion</h2>
<p class="q">Which implementation performs best for small input files? Why?</p>
<p><b>Multithreading.</b> On D1 it takes {m('D1','thread',1)} ms, compared with {m('D1','shm',1)} ms for shared
memory and {m('D1','pipe',1)} ms for pipes. With so little data, setup cost is most of the runtime. Table 4
isolates that cost. Processing 10 tiny files takes {e('overhead','thread','10tiny',1):.2f} ms with one thread,
{e('overhead','pipe','10tiny',1):.2f} ms with one pipe worker, and {e('overhead','shm','10tiny',1):.2f} ms with shared
memory, which forks a process and creates, maps and unlinks a segment for every task (about 0.4 ms per task when
run serially). A thread needs no page-table copy, no serialization and no system calls to exchange results.
D1 is a single task at the default threshold, so more workers cannot help and all curves in Figure 1 stay near 1.
When D1 is split into 128 KiB chunks (Table 3), the best times fall to about 1.1–1.9 ms at N = 4, and the threaded
version is still fastest. Beyond that point, the extra workers cost more than the parallel work saves.</p>

<p class="q">Which implementation performs best for large input files? Why?</p>
<p>On the official data the three versions are close. At N = 4 the fastest version is:
<ul>
<li>D2: {LABEL[fast4['D2']].lower()} ({m('D2', fast4['D2'], 4)} ms)</li>
<li>D3: {LABEL[fast4['D3']].lower()} ({m('D3', fast4['D3'], 4)} ms)</li>
<li>D4: {LABEL[fast4['D4']].lower()} ({m('D4', fast4['D4'], 4)} ms)</li>
<li>D5: {LABEL[fast4['D5']].lower()} ({m('D5', fast4['D5'], 4)} ms)</li>
</ul>
Shared memory is usually last. Because each table holds only 26 words, the IPC payload is a few hundred bytes per
task. Almost all of the time goes to the identical scanning loop, which processes about {thr_1:.0f} MB/s per core.
The differences that remain come from per-task costs. Threads pay only a mutex operation per task. Pipes pay one
message round trip and reuse <i>N</i> workers. Shared memory pays a <code>fork()</code>, a new segment and a
<code>waitpid()</code> per task, which also makes its single-worker time the slowest
({d2_1['shm']:.0f} ms on D2, vs. {d2_1['pipe']:.0f} ms for pipes and {d2_1['thread']:.0f} ms for threads).
When the partial results are large (§6), threads win by a wider margin, because the process versions must
serialize, copy and re-hash every table.</p>

<p class="q">How does increasing the number of workers affect execution time?</p>
<p>From 1 to {NCPU} workers, the time falls almost linearly. The average speedup at N = 4 over D2–D5 is
{avg_sp4['shm']:.2f} for shared memory, {avg_sp4['pipe']:.2f} for pipes and {avg_sp4['thread']:.2f} for threads,
because the work is CPU-bound and the files are in the page cache. Beyond {NCPU} workers (the number of logical
CPUs), there is no consistent further gain. The best time at N = 8 or 16 is within about ±20% of the best at N = 4,
which is close to the measurement noise. The number of tasks also caps useful parallelism, since D1 has a single task.</p>

<p class="q">What are the overheads associated with process creation, thread creation, shared memory, and message passing?</p>
<ul>
<li><b>Process creation:</b> <code>fork()</code> copies page tables and descriptors, and each later write triggers a
copy-on-write page fault. <code>waitpid()</code> and process teardown add more. With 64 KiB chunks
(about 1,500 tasks), the fork-per-task shared-memory version needs {e('chunk','shm','64K',4):.0f} ms on D2, compared
with {e('chunk','shm','8M',4):.0f} ms at 8 MiB.</li>
<li><b>Thread creation:</b> cheap, because only a stack and a kernel task are created. Ten threads cost well under a
millisecond (Table 4). The hidden cost of threads is sharing one address space: malloc and page-fault contention
appear when the threads allocate a lot of memory (§6).</li>
<li><b>Shared memory:</b> no data passes through the kernel. However, each segment costs <code>shm_open</code>,
<code>ftruncate</code>, <code>mmap</code>, <code>munmap</code> and <code>shm_unlink</code> plus first-touch page
faults, and tables must be serialized because pointers are meaningless in another process.</li>
<li><b>Message passing:</b> every byte is copied twice (user to kernel to user) in pieces of at most 64 KiB, with
extra system calls and context switches. Pipes need no explicit synchronization, and long-lived workers spread the
fork cost over many tasks. With 64 KiB chunks, pipes need {e('chunk','pipe','64K',4):.0f} ms, compared with
{e('chunk','shm','64K',4):.0f} ms for shared memory.</li>
</ul>

<p class="q">Does splitting a large file into smaller chunks always improve performance?</p>
<p><b>No.</b> Table 2 and Figure 6 show this. Without splitting (128M), the 100 MB file is one task, so only one core
works and every version takes about {min(e('chunk',i,'128M',4) for i,_ in IMPLS):.0f}–{max(e('chunk',i,'128M',4) for i,_ in IMPLS):.0f} ms.
Moderate chunks of 256 KiB to 16 MiB are two to four times faster. Very small chunks hurt the process versions:
shared memory needs {e('chunk','shm','64K',4):.0f} ms at 64 KiB, because every chunk adds a fork or a message, a fresh
table and a merge. Threads stay at about {e('chunk','thread','64K',4):.0f}–{e('chunk','thread','16M',4):.0f} ms across that
range, since an extra chunk costs them only a mutex operation. Large chunks of 32 MiB leave only 3 tasks
for 4 workers. The best chunk size gives a few tasks per worker while the per-task overhead
stays small.</p>

<p class="q">How does an uneven distribution of file sizes affect workload balancing?</p>
<p>When each file is one task, the largest file decides the total time. In D4, the 100 MB file is 79% of the data.
With one task per file (Table 5), 4 workers give a speedup of only
{min(nos.get((i,1),0)/max(nos.get((i,4),1),1e-9) for i,_ in IMPLS):.2f}–{max(nos.get((i,1),0)/max(nos.get((i,4),1),1e-9) for i,_ in IMPLS):.2f},
because three workers finish early and sit idle. With 8 MiB chunks, D4 becomes 17 tasks of similar size served
from a shared pool, and the speedup at N = 4 rises to {min(sp('D4',i,4) for i,_ in IMPLS):.2f}–{max(sp('D4',i,4) for i,_ in IMPLS):.2f}.
Splitting large files and scheduling dynamically, where the next free worker takes the next task, is what
balances the load.</p>

<p class="q">Why might increasing the number of workers beyond the number of available CPU cores fail to improve performance?</p>
<p>The task is CPU-bound, and with {NCPU} logical processors at most {NCPU} mappers can run at the same time. Extra
workers only time-share the same cores and add costs: context switches, more process or thread creation, more
partial tables to merge, cache pressure, and for threads more contention on the shared address space. The master,
which needs CPU time to merge results, has to compete with them. Table 1 confirms this: times at N = 8 and 16 are
no better than at N = 4.</p>

<p class="q">What are the advantages and disadvantages of processes compared with threads for this application?</p>
<p><b>Processes:</b>
<ul>
<li>Strong isolation: a crashing mapper cannot corrupt the master, and the failure is detected through its exit status.</li>
<li>No accidental sharing, so no data races.</li>
<li>No contention inside one address space.</li>
<li>Costs: expensive creation, explicit IPC with serialization and copying, and more resources to clean up (segments, descriptors, zombie processes).</li>
</ul>
<b>Threads:</b>
<ul>
<li>The cheapest creation and the fastest result exchange, because tables are merged in place.</li>
<li>Lower memory use, and the best or near-best times in every experiment.</li>
<li>Costs: a bug in one thread can bring down the whole program.</li>
<li>All shared state must be synchronized correctly. Here this is kept to one mutex-protected counter.</li>
<li>Shared-address-space contention (malloc arenas, page faults) can limit scaling unless it is addressed.</li>
</ul>
For this CPU-bound, read-only workload, threads are the most efficient choice. The process designs trade some
speed for isolation.</p>

<h2>8. Conclusion</h2>
<p>All three designs produce identical, verified results and never run more than <i>N</i> mappers at a time. On the
official datasets they scale almost linearly up to the {NCPU} available cores and differ only slightly, because
the work is dominated by scanning text and the partial results are tiny. Shared memory with fork-per-task has the
highest per-task overhead, pipes are in between, and threads have the lowest. These differences grow with very
small chunks or large vocabularies. Splitting large files into moderate, word-safe chunks combined with dynamic
scheduling is essential for large and unequal inputs, and using more workers than cores does not help.</p>
</body></html>
"""
open(os.path.join(ROOT, "report", "report.html"), "w").write(html)
print("wrote report/report.html")
