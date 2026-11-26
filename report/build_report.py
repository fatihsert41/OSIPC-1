#!/usr/bin/env python3
"""Build report/report.html (then report.pdf via html2pdf.js) from the
benchmark CSV files and figures. Usage: python3 report/build_report.py"""
import base64, csv, os, statistics
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(ROOT, "bench", "figures")


def img(name, width="100%"):
    with open(os.path.join(FIG, name), "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f'<img src="data:image/png;base64,{b64}" style="width:{width}">'


runs = defaultdict(list)
for r in csv.DictReader(open(os.path.join(ROOT, "bench", "results.csv"))):
    runs[(r["dataset"], r["impl"], int(r["workers"]))].append(float(r["ms"]))
med = {k: statistics.median(v) for k, v in runs.items()}
extra = list(csv.DictReader(open(os.path.join(ROOT, "bench", "extra.csv"))))
NS = [1, 2, 4, 8, 16]
IMPLS = [("shm", "Shared memory"), ("pipe", "Pipes"), ("thread", "Threads")]


def ex(exp, impl, param, n):
    for r in extra:
        if r["experiment"] == exp and r["impl"] == impl and r["param"] == param and int(r["workers"]) == n:
            return float(r["median_ms"])
    return float("nan")


def median_table():
    h = "<table><tr><th>Dataset</th><th>Implementation</th>" + "".join(f"<th>N={n}</th>" for n in NS) + "<th>Best speedup</th></tr>"
    for ds in ["D1", "D2", "D3", "D4", "D5"]:
        best = min(med[(ds, i, n)] for i, _ in IMPLS for n in NS)
        for j, (impl, label) in enumerate(IMPLS):
            cells = []
            for n in NS:
                v = med[(ds, impl, n)]
                cells.append(f'<td class="{"best" if v == best else ""}">{v:.1f}</td>')
            sp = max(med[(ds, impl, 1)] / med[(ds, impl, n)] for n in NS)
            first = f'<td rowspan="3"><b>{ds}</b></td>' if j == 0 else ""
            h += f"<tr>{first}<td>{label}</td>{''.join(cells)}<td>{sp:.2f}</td></tr>"
    return h + "</table>"


def extra_tables():
    ch = ["64K", "256K", "1M", "4M", "8M", "16M", "32M", "128M"]
    t1 = "<table><tr><th>Chunk threshold</th>" + "".join(f"<th>{c}</th>" for c in ch) + "</tr>"
    for impl, label in IMPLS:
        t1 += f"<tr><td>{label}</td>" + "".join(f"<td>{ex('chunk', impl, c, 4):.0f}</td>" for c in ch) + "</tr>"
    t1 += "</table>"
    t2 = "<table><tr><th>D1 split into 128 KiB chunks</th>" + "".join(f"<th>N={n}</th>" for n in NS) + "</tr>"
    for impl, label in IMPLS:
        t2 += f"<tr><td>{label}</td>" + "".join(f"<td>{ex('d1split', impl, '128K', n):.1f}</td>" for n in NS) + "</tr>"
    t2 += "</table>"
    t3 = "<table><tr><th>10 tiny files (fixed cost)</th><th>N=1</th><th>N=10</th></tr>"
    for impl, label in IMPLS:
        t3 += f"<tr><td>{label}</td><td>{ex('overhead', impl, '10tiny', 1):.2f}</td><td>{ex('overhead', impl, '10tiny', 10):.2f}</td></tr>"
    t3 += "</table>"
    return t1, t2, t3


nosplit = {}
p = os.path.join(ROOT, "bench", "d4_nosplit.txt")
if os.path.exists(p):
    for line in open(p):
        _, _, impl, n, v = line.split()
        nosplit[(impl, int(n[2:]))] = float(v)

t_chunk, t_d1, t_over = extra_tables()
m = lambda ds, i, n: f"{med[(ds, i, n)]:.0f}"
sp = lambda ds, i, n: f"{med[(ds, i, 1)] / med[(ds, i, n)]:.2f}"

html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Homework I Report</title>
<style>
body {{ font-family: 'DejaVu Serif', Georgia, serif; font-size: 9.8pt; line-height: 1.36; color: #111; background: #fff; }}
h1 {{ font-size: 17pt; margin: 0 0 2px; }} h2 {{ font-size: 12.5pt; margin: 16px 0 5px; border-bottom: 1px solid #ccc; }}
h3 {{ font-size: 10.8pt; margin: 10px 0 3px; }}
.sub {{ color: #444; margin-bottom: 8px; }}
table {{ border-collapse: collapse; margin: 6px 0 8px; font-size: 8.6pt; font-family: 'DejaVu Sans', Arial, sans-serif; }}
th, td {{ border: 1px solid #bbb; padding: 2px 6px; text-align: right; }} th {{ background: #f0f0f0; }}
td:first-child, th:first-child {{ text-align: left; }} td.best {{ font-weight: bold; background: #eef6ee; }}
code {{ font-size: 9pt; background: #f4f4f4; padding: 0 2px; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 4px 10px; }} .grid img {{ break-inside: avoid; }} .grid3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 2px 6px; }}
.cap {{ font-size: 8.8pt; color: #333; text-align: center; margin: 0 0 6px; }}
ul, ol {{ margin: 3px 0 6px; padding-left: 20px; }} p {{ margin: 4px 0 6px; text-align: justify; }}
.q {{ font-weight: bold; margin-top: 8px; }} .avoid {{ break-inside: avoid; }}
</style></head><body>
<h1>Multiprocess and Multithreaded MapReduce: Word Frequency Analysis</h1>
<div class="sub">Operating Systems 2026–2027 Fall, Homework I &nbsp;·&nbsp; Name Surname &nbsp;·&nbsp; Student ID</div>

<h2>1. Overview and test computer</h2>
<p>The same MapReduce-style application is implemented three times: with processes and POSIX shared memory
(<code>mapreduce_shm</code>), with processes and pipes (<code>mapreduce_pipe</code>), and with POSIX threads
(<code>mapreduce_thread</code>). All three programs share the same tokenizer, hash table, partitioning and output code, so
they differ only in how work is distributed and how partial results reach the master. They produce identical output.
<code>make test</code> runs 145 checks: the sample files, chunk sizes of 1–7 bytes that cut almost every word, random
files compared with an independent Python reference, and error cases. All 145 pass, and the programs are clean under
AddressSanitizer, UBSan and ThreadSanitizer.</p>
<table>
<tr><th>CPU</th><td style="text-align:left">Intel® Xeon® Processor @ 2.10 GHz (virtual machine), 4 cores, 1 thread per core</td></tr>
<tr><th>Logical processors</th><td style="text-align:left">4</td></tr>
<tr><th>RAM</th><td style="text-align:left">16 GB (15.7 GiB)</td></tr>
<tr><th>Operating system</th><td style="text-align:left">Ubuntu 24.04.5 LTS, Linux kernel 6.18 (x86-64)</td></tr>
<tr><th>Compiler</th><td style="text-align:left">gcc 13.3.0, <code>-O2 -std=gnu11</code></td></tr>
</table>

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
over the first table without copying.
One thread-specific problem appeared during measurement. glibc gives each thread its own malloc arena and grows it
in small <code>mprotect</code>/<code>mmap</code> steps, and each step takes the process-wide address-space lock in
write mode. This stalls the page faults of the other threads. The program therefore sets
<code>mallopt(M_TOP_PAD, 64 MiB)</code> (see §5).</p>

<h2>3. Experimental setup</h2>
<p>The official files from AYBÜZEM were not available, so datasets with the required sizes were generated by
<code>bench/gen_data.py</code>. The text is English-like: a Zipf-distributed vocabulary of 60,000 words with
capitals, punctuation and digits.</p>
<ul>
<li><b>D1:</b> 1 MB</li>
<li><b>D2:</b> 100 MB</li>
<li><b>D3:</b> 4 × 25 MB</li>
<li><b>D4:</b> 1, 5, 20 and 100 MB</li>
<li><b>D5:</b> 1, 3, 8, 15, 30, 50, 75 and 100 MB</li>
</ul>
<p>Each program measures itself with <code>clock_gettime(CLOCK_MONOTONIC)</code>. Timing starts just before
partitioning and parallel setup, and stops after the results have been printed and all workers and IPC objects have
been cleaned up. Output goes to <code>/dev/null</code>. Every configuration (3 implementations × 5 datasets ×
<i>N</i> ∈ {{1, 2, 4, 8, 16}}) was run 5 times, and the median is reported. Files were warm in the page cache, and
one warm-up run was done per dataset and implementation. The default chunk threshold was 8 MiB. The machine is a
shared cloud VM, so repeated runs of the same configuration varied by roughly 10–25%. Differences smaller than that
should not be over-interpreted.</p>

<div class="avoid"><h2>4. Results</h2>
<div class="grid3">
<div>{img("speedup_D1.png")}</div><div>{img("speedup_D2.png")}</div>
<div>{img("speedup_D3.png")}</div><div>{img("speedup_D4.png")}</div>
<div>{img("speedup_D5.png")}</div><div>{img("chunk_sweep.png")}</div>
</div>
<div class="cap">Figures 1–5: speedup T(1)/T(N) for D1–D5 (dotted line = linear speedup). Figure 6: execution time vs. chunk threshold (D2, N = 4).</div></div>
<div class="avoid">
<p><b>Table 1.</b> Median execution time in ms (5 runs). The fastest value for each dataset is shaded.</p>
{median_table()}
</div>

<h2>5. Additional experiments</h2>
<div class="avoid">
<p><b>Table 2.</b> Chunk threshold sweep, D2 (one 100 MB file), N = 4, median ms. With 128M the file is not split.</p>
{t_chunk}
</div>
<div class="grid avoid"><div>
<p><b>Table 3.</b> D1 split into 128 KiB chunks, median ms.</p>{t_d1}
<p><b>Table 4.</b> Fixed overhead: 10 tiny files (sample inputs), median of 21 runs, in ms.</p>{t_over}
<p><b>Table 5.</b> D4 without splitting (<code>-c 1G</code>), median ms. Shared memory: N=1 {nosplit.get(('shm',1),0):.0f}, N=4 {nosplit.get(('shm',4),0):.0f}.
Pipes: N=1 {nosplit.get(('pipe',1),0):.0f}, N=4 {nosplit.get(('pipe',4),0):.0f}. Threads: N=1 {nosplit.get(('thread',1),0):.0f}, N=4 {nosplit.get(('thread',4),0):.0f}.</p>
</div><div>{img("thread_malloc.png")}<div class="cap">Figure 7: multithreaded version on D2 with and without the malloc heap-growth setting.</div></div></div>

<h2>6. Discussion</h2>
<p class="q">Which implementation performs best for small input files? Why?</p>
<p><b>Multithreading.</b> On D1 it takes {m('D1','thread',1)} ms, compared with {m('D1','shm',1)} ms for shared
memory and {m('D1','pipe',1)} ms for pipes. Table 4 isolates the fixed cost. Processing 10 tiny files takes
{ex('overhead','thread','10tiny',1):.2f} ms with one thread, {ex('overhead','pipe','10tiny',1):.2f} ms with one pipe
worker, and {ex('overhead','shm','10tiny',1):.2f} ms with shared memory, which forks a process and creates, maps and
unlinks a segment for every task (about 0.3 ms per task when run serially). With little data, this setup cost is
most of the runtime. A thread shares the address space, so it needs no page-table copy, no serialization and no
system calls to exchange results. With the default 8 MiB threshold, D1 is a single task, so more workers cannot
help: all curves in Figure 1 stay near 1 and the differences are noise. If D1 is split into 128 KiB chunks
(Table 3), the process versions gain, for example shared memory falls from {ex('d1split','shm','128K',1):.1f} to
{ex('d1split','shm','128K',8):.1f} ms. However, they only reach about the time the threaded version already needs
with a single thread.</p>

<p class="q">Which implementation performs best for large input files? Why?</p>
<p>With 4 workers, the threaded version has the lowest or nearly the lowest time on every large dataset:
<ul>
<li>D2: {m('D2','thread',4)} ms (pipes {m('D2','pipe',4)}, shared memory {m('D2','shm',4)})</li>
<li>D3: {m('D3','thread',4)} ms (pipes {m('D3','pipe',4)}, shared memory {m('D3','shm',4)})</li>
<li>D4: {m('D4','thread',4)} ms (pipes {m('D4','pipe',4)}, shared memory {m('D4','shm',4)})</li>
<li>D5: {m('D5','thread',4)} ms (pipes {m('D5','pipe',4)}, shared memory {m('D5','shm',4)})</li>
</ul>
Its single-worker time is also 20–30% lower: {m('D2','thread',1)} ms on D2, compared with {m('D2','shm',1)} ms and
{m('D2','pipe',1)} ms. The process versions must serialize every partial table, copy it through the kernel (pipes)
or through tmpfs pages (shared memory), and parse and hash it again in the master. Threads hand over tables in
place, and the per-thread combining tables mean that only <i>T</i> tables per file are merged. Relative speedups
at N = 4 are similar for all three versions (about 2.7–4.1×). The process versions start from a larger T(1), and
their master's reduce work runs alongside the workers, which can push their speedup slightly above 4 on 4 cores.
Such values are within the run-to-run noise. The best absolute D2 time is the pipe version at N = 8
({m('D2','pipe',8)} ms), effectively tied with threads at N = 16 ({m('D2','thread',16)} ms). Pipes and shared memory are close. Pipes reuse
<i>N</i> long-lived workers, while the shared-memory version forks one process per task and creates one segment per
task, so it pays more per chunk (Table 2).</p>

<p class="q">How does increasing the number of workers affect execution time?</p>
<p>From 1 to 4 workers, the time falls almost linearly on all large datasets, because the work is CPU-bound
(tokenizing and hashing) and the files are in the page cache. For example, D5 with threads goes from
{m('D5','thread',1)} to {m('D5','thread',4)} ms, and with shared memory from {m('D5','shm',1)} to
{m('D5','shm',4)} ms. Beyond 4 workers (the number of logical CPUs), the time stops improving and often gets worse.
D5 with threads rises to {m('D5','thread',16)} ms at N = 16, and D4 with pipes rises from {m('D4','pipe',4)} to
{m('D4','pipe',16)} ms. The number of tasks also caps useful parallelism: D1 has 1 task, D2 has 13, D3 has 16,
D4 has 18 and D5 has 39.</p>

<p class="q">What are the overheads associated with process creation, thread creation, shared memory, and message passing?</p>
<ul>
<li><b>Process creation:</b> <code>fork()</code> copies page tables and file descriptors, and each later write
triggers a copy-on-write page fault. The cost grows with the parent's memory, and the master's merged tables keep
growing. <code>waitpid()</code> and process teardown add more. This is the main reason the shared-memory version
is slowest with tiny chunks: with 64 KiB chunks it forks about 1600 processes and needs {ex('chunk','shm','64K',4):.0f} ms.</li>
<li><b>Thread creation:</b> cheap, because only a stack and a kernel task are created and nothing is copied.
Creating 10 threads costs well under a millisecond (Table 4). The hidden cost of threads is <i>sharing</i>: all
threads use one address space, so <code>mmap</code>/<code>mprotect</code> and page faults contend on one lock.
Figure 7 shows that with default malloc on D2, 16 threads take {ex('malloc','thread','default',16):.0f} ms instead
of {ex('malloc','thread','tuned',16):.0f} ms, and system time was 0.45 s instead of 0.06 s.</li>
<li><b>Shared memory:</b> no data is copied through the kernel. However, every segment costs
<code>shm_open</code>, <code>ftruncate</code>, <code>mmap</code>, <code>munmap</code> and <code>shm_unlink</code>
system calls plus page faults on first touch, and the data must still be serialized into a flat layout, because
pointers are meaningless in another process.</li>
<li><b>Message passing:</b> every byte is copied twice (user to kernel to user) in pieces no larger than the 64 KiB
pipe buffer, which costs extra system calls and context switches. In return, pipes need no explicit
synchronization, and long-lived workers spread the fork cost over many tasks.</li>
</ul>

<p class="q">Does splitting a large file into smaller chunks always improve performance?</p>
<p><b>No.</b> Table 2 and Figure 6 show this. Without splitting (128M), the 100 MB file is one task, so only one
core works and every version takes about 550–610 ms. Splitting into 16–32 MiB chunks gives the best results for
the process versions (about 230–255 ms). Much smaller chunks hurt the process versions badly: at 64 KiB, pipes take
{ex('chunk','pipe','64K',4):.0f} ms and shared memory {ex('chunk','shm','64K',4):.0f} ms, because each chunk adds a
fork or a message, a fresh table that has to be serialized, and a merge. Threads stay at about 165–230 ms across the
whole range, since an extra chunk costs them only a mutex operation and they keep using one table per file. The
best chunk size is one that produces a few tasks per worker without the per-task overhead dominating.</p>

<p class="q">How does an uneven distribution of file sizes affect workload balancing?</p>
<p>When each file is one task, the largest file decides the total time. In D4, the 100 MB file is 79% of the data.
Without splitting (Table 5), 4 workers improve the time only from about {nosplit.get(('shm',1),0):.0f} to
{nosplit.get(('shm',4),0):.0f} ms (shared memory), a speedup of about 1.1–1.3, because three workers finish early
and sit idle. With 8 MiB chunks, D4 becomes 18 similar tasks served from a shared pool, and the speedup at N = 4
rises to {sp('D4','shm',4)} (shared memory), {sp('D4','thread',4)} (threads) and {sp('D4','pipe',4)} (pipes).
Dynamic scheduling, where the next free worker takes the next task, is what balances the load. Static assignment
of files to workers would not.</p>

<p class="q">Why might increasing the number of workers beyond the number of available CPU cores fail to improve performance?</p>
<p>The task is CPU-bound, and with 4 logical processors at most 4 mappers can run at the same time. Extra workers
only time-share the same cores and add costs: context switches, more process or thread creation, more partial
tables to merge, more cache and memory-bandwidth pressure, and for threads more contention on the address-space
lock. The master, which also needs CPU time to merge results, has to compete with them. This is why times at
N = 8 and 16 are equal to or worse than at N = 4 (Table 1).</p>

<p class="q">What are the advantages and disadvantages of processes compared with threads for this application?</p>
<p><b>Processes:</b>
<ul>
<li>Strong isolation: a crashing mapper cannot corrupt the master, and the failure is detected through its exit status.</li>
<li>No accidental sharing, so no data races.</li>
<li>No contention on one address space, so they scale smoothly to the core count.</li>
<li>Costs: expensive creation, explicit IPC with serialization and copying, and more resources to clean up (segments, descriptors, zombies).</li>
</ul>
<b>Threads:</b>
<ul>
<li>The cheapest creation and the fastest result exchange, because tables are merged in place.</li>
<li>Lower memory use, and the best absolute times in our measurements.</li>
<li>Costs: a bug in one thread can corrupt the whole program.</li>
<li>All shared state must be synchronized correctly. Here this is kept to one mutex-protected counter.</li>
<li>Hidden contention inside the shared address space (malloc arenas and page faults) can reduce scaling unless it is addressed.</li>
</ul>
For this read-mostly, CPU-bound workload, threads are the better engineering choice. The process-based designs pay
for safety with IPC overhead.</p>

<h2>7. Conclusion</h2>
<p>All three designs produce identical results and keep at most <i>N</i> mappers active. Threads had the best
absolute times on D1, D3, D4 and D5, and were effectively tied with pipes on D2. Message passing and shared memory scale well up to the number of cores, but
they spend extra time on process creation and on moving serialized tables, and the shared-memory version
additionally creates and destroys one segment per task. Chunking a file into a moderate number of word-safe chunks,
together with dynamic scheduling, is essential for large and unequal inputs. Using more workers than cores does not
help.</p>
</body></html>
"""
open(os.path.join(ROOT, "report", "report.html"), "w").write(html)
print("wrote report/report.html")
