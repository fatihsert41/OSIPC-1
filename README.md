# Multiprocess and Multithreaded MapReduce: Word Frequency Analysis

Operating Systems 2026-2027 Fall, Homework I.

These programs find the five most frequent words in each input file. There are three versions:

| Program            | Source                              | Parallelism / IPC                                             |
|--------------------|-------------------------------------|---------------------------------------------------------------|
| `mapreduce_shm`    | `shared_memory/mapreduce_shm.c`     | `fork()` processes, POSIX shared memory (`shm_open`/`mmap`)   |
| `mapreduce_pipe`   | `message_passing/mapreduce_pipe.c`  | `fork()` processes, pipes (no shared memory)                  |
| `mapreduce_thread` | `multithreading/mapreduce_thread.c` | POSIX threads in a single process                             |

Each source file stands alone. The word-processing code (tokenizer, hash table, chunking, output) is the same in all three, so the versions differ only in how work is distributed and how results are moved.

## Requirements

- Linux or another POSIX system (on Windows, use WSL)
- `gcc` and `make`
- Optional: `python3` for the tests and benchmarks, and `matplotlib` for the graphs

## Compile

```bash
make            # builds mapreduce_shm, mapreduce_pipe, mapreduce_thread
make clean      # removes the binaries
```

The default flags are `gcc -O2 -Wall -Wextra -std=gnu11`. `-lrt` is added for shared memory and `-pthread` for threads.

## Run

```
./mapreduce_shm    <max_workers> [options] file1 [file2 ... file10]
./mapreduce_pipe   <max_workers> [options] file1 [file2 ... file10]
./mapreduce_thread <max_workers> [options] file1 [file2 ... file10]
```

- `max_workers` sets the maximum number of mapper processes or threads that can run at the same time (1 to 1024).
- Up to 10 input files are accepted. Each file's results are printed in the same order as on the command line.
- Options can appear anywhere after `max_workers`:
  - `-c SIZE`: the chunk threshold. A file larger than `SIZE` bytes is split into `ceil(size/SIZE)` nearly equal chunks. The default is `8M`. The suffixes `K`, `M` and `G` are allowed.
  - `-o FILE`: also writes the results to `FILE`. Standard output is always written.
  - `-t`: prints the elapsed wall-clock time in milliseconds to stderr (`elapsed_ms <value>`), measured with `CLOCK_MONOTONIC`. Setting `MR_TIMING=1` does the same.

Example:

```bash
./mapreduce_thread 4 tests/sample_inputs/file1.txt tests/sample_inputs/file2.txt
```
```
File: file1.txt
linux          3
is             2
an             1
and            1
operating      1
File: file2.txt
memory         2
processes      2
shared         2
allows         1
communicate    1
```

### Word rules

- A word is a run of ASCII letters (`A-Z`, `a-z`), converted to lowercase.
- Digits, punctuation, whitespace and all other bytes separate words. For example, `world123test` becomes `world` and `test`.
- Words are sorted by descending count, with ties sorted alphabetically.
- A file with fewer than five distinct words lists all of them. An empty file, or one with no words, prints `No words found.`
- Files are never combined: each file has its own table.

### Chunk boundaries

A word belongs to the chunk that contains its **first letter**.

- If the byte just before a chunk is a letter, the mapper skips the leading letters, because that word belongs to the previous chunk.
- A mapper reads past the end of its range to finish a word that started inside its range.

This counts every word exactly once, wherever the byte cuts fall. The tests check this with chunk sizes of 1 to 7 bytes, which cut nearly every word.

## Test

```bash
make test
```

`tests/run_tests.sh` checks all three programs:

1. The sample inputs against `tests/expected_output.txt`, with N ∈ {1,2,4,8,16} and chunk sizes 1, 2, 3, 7, 64 bytes and 1 MiB.
2. The `-o` option.
3. Randomly generated files (long words, digits, mixed case, non-ASCII bytes, empty files) against an independent Python reference, `tests/reference.py`.
4. Error handling (missing file, `N=0`, more than 10 files) and that no `/dev/shm/mr_*` objects are left over.

## Benchmark

Put the official datasets (D1-5.rar from AYBÜZEM) into `bench/data`, so that you have `bench/data/D1/*.txt` through `bench/data/D5/*.txt`. Then run:

```bash
make bench        # runs all experiments and draws the graphs
```

If `bench/data/D1` does not exist, `make bench` first generates synthetic datasets of the same sizes.

The steps can also be run one at a time:

```bash
sh bench/run_bench.sh bench/data bench/results.csv       # 3 impl x 5 datasets x N in {1,2,4,8,16} x 5 reps
sh bench/run_extra.sh bench/data bench/extra.csv         # chunk sweep, small-file split, fixed overhead, malloc, D4 no-split
python3 bench/plot.py bench/results.csv bench/figures    # medians.csv + speedup_D*.png
```

The large-vocabulary experiment in §6 of the report used `python3 bench/gen_data.py <dir>` (synthetic text, 60 000 words). Its results are in `bench/synthetic/`.

`make report` rebuilds `report.pdf` from the measurements. It needs `matplotlib` and Node.js with Playwright. The student name and the test-computer table are set at the top of `report/build_report.py`.

## Submission archive

```bash
make dist STUDENT_ID=12345678     # creates OS_MapReduce_12345678.zip
```

The archive has the required layout: the three source directories, `Makefile`, `README.md` and `report.pdf`, plus `video_link.txt` with the YouTube link of the demo video. It also includes the small `tests/` and `bench/` scripts that this README refers to, but no datasets.
