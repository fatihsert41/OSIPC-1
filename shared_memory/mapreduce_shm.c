/*
 * mapreduce_shm.c - multiprocess version, POSIX shared memory
 * Operating Systems 2026-2027 Fall - Homework I
 * MapReduce word frequency analysis: top-5 words of every input file.
 *
 * Build: make    Run: ./mapreduce_shm <max_workers> file1 [file2 ... file10]
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

/* ======================================================================
 * Common part (identical in all three implementations)
 * ====================================================================== */

#define MAX_FILES           10
#define MAX_WORKERS         1024
#define TOP_K               5
#define DEFAULT_CHUNK_BYTES (8L << 20)  /* files larger than 8 MiB are split */
#define IO_BUF_SIZE         (1 << 16)   /* 64 KiB read buffer */
#define ARENA_BLOCK         (1 << 16)
#define FNV_OFFSET          2166136261u
#define FNV_PRIME           16777619u

/* lower_tab[c] = lowercase letter if c is an ASCII letter, 0 otherwise. */
static unsigned char lower_tab[256];

static void init_tables(void)
{
    for (int c = 'A'; c <= 'Z'; c++) lower_tab[c] = (unsigned char)(c - 'A' + 'a');
    for (int c = 'a'; c <= 'z'; c++) lower_tab[c] = (unsigned char)c;
}

static void die(const char *msg)
{
    fprintf(stderr, "error: %s\n", msg);
    exit(EXIT_FAILURE);
}

static void *xmalloc(size_t n)
{
    void *p = malloc(n ? n : 1);
    if (!p) die("out of memory");
    return p;
}

static void *xcalloc(size_t n, size_t sz)
{
    void *p = calloc(n ? n : 1, sz ? sz : 1);
    if (!p) die("out of memory");
    return p;
}

static double now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1e3 + ts.tv_nsec / 1e6;
}

/* ---------- arena allocator for word strings ---------- */

typedef struct arena_blk {
    struct arena_blk *next;
    size_t used, cap;
    char data[];
} arena_blk_t;

typedef struct {
    arena_blk_t *head;
} arena_t;

static char *arena_alloc(arena_t *a, size_t n)
{
    if (!a->head || a->head->cap - a->head->used < n) {
        size_t cap = n > ARENA_BLOCK ? n : ARENA_BLOCK;
        arena_blk_t *b = xmalloc(sizeof(*b) + cap);
        b->next = a->head;
        b->used = 0;
        b->cap = cap;
        a->head = b;
    }
    char *p = a->head->data + a->head->used;
    a->head->used += n;
    return p;
}

static void arena_free(arena_t *a)
{
    while (a->head) {
        arena_blk_t *n = a->head->next;
        free(a->head);
        a->head = n;
    }
}

/* ---------- word frequency table (open addressing hash table) ---------- */

typedef struct {
    char *word;      /* NUL-terminated, lowercase; NULL = empty slot */
    uint32_t len;
    uint32_t hash;
    uint64_t count;
} entry_t;

typedef struct {
    entry_t *slots;
    size_t cap;      /* power of two */
    size_t size;     /* number of distinct words */
    arena_t arena;
} wtable_t;

static uint32_t hash_bytes(const char *s, size_t n)
{
    uint32_t h = FNV_OFFSET;
    for (size_t i = 0; i < n; i++) h = (h ^ (unsigned char)s[i]) * FNV_PRIME;
    return h;
}

static void wt_init(wtable_t *t, size_t cap)
{
    size_t c = 16;
    while (c < cap) c <<= 1;
    t->slots = xcalloc(c, sizeof(entry_t));
    t->cap = c;
    t->size = 0;
    t->arena.head = NULL;
}

static void wt_free(wtable_t *t)
{
    free(t->slots);
    arena_free(&t->arena);
    t->slots = NULL;
    t->cap = t->size = 0;
}

static void wt_grow(wtable_t *t)
{
    size_t ncap = t->cap * 2, mask = ncap - 1;
    entry_t *ns = xcalloc(ncap, sizeof(entry_t));
    for (size_t i = 0; i < t->cap; i++) {
        if (!t->slots[i].word) continue;
        size_t j = t->slots[i].hash & mask;
        while (ns[j].word) j = (j + 1) & mask;
        ns[j] = t->slots[i];
    }
    free(t->slots);
    t->slots = ns;
    t->cap = ncap;
}

/* Add `cnt` occurrences of word w (len bytes, already lowercase, hash h). */
static void wt_add(wtable_t *t, const char *w, uint32_t len, uint32_t h, uint64_t cnt)
{
    if ((t->size + 1) * 10 > t->cap * 7) wt_grow(t);
    size_t mask = t->cap - 1, i = h & mask;
    while (t->slots[i].word) {
        entry_t *e = &t->slots[i];
        if (e->hash == h && e->len == len && memcmp(e->word, w, len) == 0) {
            e->count += cnt;
            return;
        }
        i = (i + 1) & mask;
    }
    char *copy = arena_alloc(&t->arena, (size_t)len + 1);
    memcpy(copy, w, len);
    copy[len] = '\0';
    t->slots[i].word = copy;
    t->slots[i].len = len;
    t->slots[i].hash = h;
    t->slots[i].count = cnt;
    t->size++;
}

/* ---------- serialization (used to move a table through IPC) ----------
 * Layout: uint64 nentries, then per entry: uint32 len, uint64 count, bytes */

static size_t wt_serialized_size(const wtable_t *t)
{
    size_t n = sizeof(uint64_t);
    for (size_t i = 0; i < t->cap; i++)
        if (t->slots[i].word) n += sizeof(uint32_t) + sizeof(uint64_t) + t->slots[i].len;
    return n;
}

static void wt_serialize(const wtable_t *t, char *dst)
{
    uint64_t n = t->size;
    memcpy(dst, &n, sizeof n);
    dst += sizeof n;
    for (size_t i = 0; i < t->cap; i++) {
        const entry_t *e = &t->slots[i];
        if (!e->word) continue;
        memcpy(dst, &e->len, sizeof e->len);
        dst += sizeof e->len;
        memcpy(dst, &e->count, sizeof e->count);
        dst += sizeof e->count;
        memcpy(dst, e->word, e->len);
        dst += e->len;
    }
}

/* Merge a serialized table into t. Returns 0 on success, -1 if malformed. */
static int wt_merge_serialized(wtable_t *t, const char *src, size_t size)
{
    const char *p = src, *end = src + size;
    uint64_t n;
    if ((size_t)(end - p) < sizeof n) return -1;
    memcpy(&n, p, sizeof n);
    p += sizeof n;
    for (uint64_t k = 0; k < n; k++) {
        uint32_t len;
        uint64_t cnt;
        if ((size_t)(end - p) < sizeof len + sizeof cnt) return -1;
        memcpy(&len, p, sizeof len);
        p += sizeof len;
        memcpy(&cnt, p, sizeof cnt);
        p += sizeof cnt;
        if ((size_t)(end - p) < len) return -1;
        wt_add(t, p, len, hash_bytes(p, len), cnt);
        p += len;
    }
    return 0;
}

/* ---------- mapper: count words in byte range [start, end) of a file ----------
 * Chunk boundary rule: a word belongs to the chunk in which its FIRST letter
 * lies. Therefore a mapper
 *   - skips the leading letters of its range if the byte just before `start`
 *     is a letter (that word belongs to the previous chunk), and
 *   - keeps reading past `end` to finish a word that started inside its range.
 * Every word is thus counted exactly once, no matter where the cuts fall. */

static int count_range(int fd, off_t start, off_t end, wtable_t *t)
{
    char *buf = xmalloc(IO_BUF_SIZE);
    size_t wcap = 64, wlen = 0;
    char *word = xmalloc(wcap);
    uint32_t h = FNV_OFFSET;
    int skipping = 0, rc = 0, done = 0;

    if (start > 0) {
        unsigned char c;
        ssize_t r;
        do r = pread(fd, &c, 1, start - 1); while (r < 0 && errno == EINTR);
        if (r < 0) { rc = -1; goto out; }
        if (r == 1 && lower_tab[c]) skipping = 1;
    }

    off_t pos = start;
    while (!done) {
        size_t want = IO_BUF_SIZE;
        if (pos < end) {
            if ((off_t)want > end - pos) want = (size_t)(end - pos);
        } else if (wlen == 0) {
            break;               /* past our range and not inside a word */
        }
        ssize_t n = pread(fd, buf, want, pos);
        if (n < 0) {
            if (errno == EINTR) continue;
            rc = -1;
            goto out;
        }
        if (n == 0) break;       /* end of file */
        for (ssize_t i = 0; i < n; i++) {
            unsigned char lc = lower_tab[(unsigned char)buf[i]];
            if (lc) {
                if (skipping) continue;
                if (wlen == wcap) {
                    wcap *= 2;
                    word = realloc(word, wcap);
                    if (!word) die("out of memory");
                }
                word[wlen++] = (char)lc;
                h = (h ^ lc) * FNV_PRIME;
            } else {
                skipping = 0;
                if (wlen) {
                    wt_add(t, word, (uint32_t)wlen, h, 1);
                    wlen = 0;
                    h = FNV_OFFSET;
                }
                if (pos + i + 1 >= end) { done = 1; break; }
            }
        }
        pos += n;
    }
    if (wlen) wt_add(t, word, (uint32_t)wlen, h, 1);   /* word ending at EOF */
out:
    free(buf);
    free(word);
    return rc;
}

/* ---------- Stage 1: input & partitioning ---------- */

typedef struct {
    int file;        /* index into the input file list */
    off_t start;     /* byte range [start, end) */
    off_t end;
} task_t;

/* Split every file into tasks. Files larger than chunk_bytes are divided into
 * ceil(size / chunk_bytes) nearly equal byte ranges. Every file (even an empty
 * one) gets at least one task, i.e. at least one mapper. */
static task_t *build_tasks(int nfiles, char **files, off_t chunk_bytes, size_t *ntasks_out)
{
    off_t sizes[MAX_FILES];
    size_t total = 0;
    for (int f = 0; f < nfiles; f++) {
        struct stat st;
        if (stat(files[f], &st) < 0) {
            fprintf(stderr, "error: cannot access '%s': %s\n", files[f], strerror(errno));
            exit(EXIT_FAILURE);
        }
        if (!S_ISREG(st.st_mode)) {
            fprintf(stderr, "error: '%s' is not a regular file\n", files[f]);
            exit(EXIT_FAILURE);
        }
        if (access(files[f], R_OK) < 0) {
            fprintf(stderr, "error: cannot read '%s': %s\n", files[f], strerror(errno));
            exit(EXIT_FAILURE);
        }
        sizes[f] = st.st_size;
        total += st.st_size > chunk_bytes ? (size_t)((st.st_size + chunk_bytes - 1) / chunk_bytes) : 1;
    }
    task_t *tasks = xmalloc(total * sizeof(task_t));
    size_t k = 0;
    for (int f = 0; f < nfiles; f++) {
        uint64_t s = (uint64_t)sizes[f];
        uint64_t n = sizes[f] > chunk_bytes ? (s + chunk_bytes - 1) / chunk_bytes : 1;
        for (uint64_t i = 0; i < n; i++) {
            tasks[k].file = f;
            tasks[k].start = (off_t)(s * i / n);
            tasks[k].end = (off_t)(s * (i + 1) / n);
            k++;
        }
    }
    *ntasks_out = k;
    return tasks;
}

/* ---------- Stage 4: output ---------- */

static int entry_before(const entry_t *a, const entry_t *b)
{
    if (a->count != b->count) return a->count > b->count;
    return strcmp(a->word, b->word) < 0;
}

static void print_result(FILE *out, const char *path, const wtable_t *t)
{
    const entry_t *top[TOP_K];
    size_t k = 0;
    for (size_t i = 0; i < t->cap; i++) {
        const entry_t *e = &t->slots[i];
        if (!e->word) continue;
        if (k == TOP_K && !entry_before(e, top[TOP_K - 1])) continue;
        size_t j = k < TOP_K ? k++ : TOP_K - 1;
        while (j > 0 && entry_before(e, top[j - 1])) {
            top[j] = top[j - 1];
            j--;
        }
        top[j] = e;
    }
    const char *base = strrchr(path, '/');
    fprintf(out, "File: %s\n", base ? base + 1 : path);
    if (k == 0) fprintf(out, "No words found.\n");
    for (size_t i = 0; i < k; i++)
        fprintf(out, "%-14s %llu\n", top[i]->word, (unsigned long long)top[i]->count);
}

/* ---------- command line ---------- */

typedef struct {
    int workers;
    int nfiles;
    char *files[MAX_FILES];
    off_t chunk_bytes;
    const char *out_path;  /* optional: also write results to this file */
    int timing;            /* print elapsed time to stderr */
} options_t;

static off_t parse_size(const char *s)
{
    char *end;
    errno = 0;
    long long v = strtoll(s, &end, 10);
    if (errno || end == s || v <= 0) return -1;
    switch (*end) {
    case 'k': case 'K': v <<= 10; end++; break;
    case 'm': case 'M': v <<= 20; end++; break;
    case 'g': case 'G': v <<= 30; end++; break;
    }
    if (*end == 'B' || *end == 'b') end++;
    return *end ? -1 : (off_t)v;
}

static void usage(const char *prog)
{
    fprintf(stderr,
            "usage: %s <max_workers> [-c chunk_size] [-o output_file] [-t] file1 [file2 ... file10]\n"
            "  max_workers   maximum number of concurrently active mappers (1..%d)\n"
            "  -c SIZE       split files larger than SIZE bytes into chunks (default 8M; K/M/G suffix)\n"
            "  -o FILE       also write the results to FILE\n"
            "  -t            print the elapsed time (ms) to stderr\n",
            prog, MAX_WORKERS);
    exit(EXIT_FAILURE);
}

static void parse_args(int argc, char **argv, options_t *o)
{
    memset(o, 0, sizeof *o);
    o->chunk_bytes = DEFAULT_CHUNK_BYTES;
    if (argc < 3) usage(argv[0]);
    char *end;
    long w = strtol(argv[1], &end, 10);
    if (*end || w < 1 || w > MAX_WORKERS) {
        fprintf(stderr, "error: invalid worker count '%s'\n", argv[1]);
        usage(argv[0]);
    }
    o->workers = (int)w;
    const char *env = getenv("MR_TIMING");
    if (env && *env && *env != '0') o->timing = 1;
    int only_files = 0;
    for (int i = 2; i < argc; i++) {
        const char *a = argv[i];
        if (!only_files && strcmp(a, "--") == 0) {
            only_files = 1;
        } else if (!only_files && strcmp(a, "-c") == 0) {
            if (++i >= argc || (o->chunk_bytes = parse_size(argv[i])) <= 0) {
                fprintf(stderr, "error: invalid chunk size\n");
                usage(argv[0]);
            }
        } else if (!only_files && strcmp(a, "-o") == 0) {
            if (++i >= argc) usage(argv[0]);
            o->out_path = argv[i];
        } else if (!only_files && strcmp(a, "-t") == 0) {
            o->timing = 1;
        } else {
            if (o->nfiles == MAX_FILES) {
                fprintf(stderr, "error: at most %d input files are supported\n", MAX_FILES);
                exit(EXIT_FAILURE);
            }
            o->files[o->nfiles++] = argv[i];
        }
    }
    if (o->nfiles == 0) usage(argv[0]);
}

/* Print all results (in command-line order) to stdout and optionally a file. */
static void emit_results(const options_t *o, wtable_t *tables)
{
    FILE *extra = NULL;
    if (o->out_path && !(extra = fopen(o->out_path, "w"))) {
        fprintf(stderr, "error: cannot open output file '%s': %s\n", o->out_path, strerror(errno));
        exit(EXIT_FAILURE);
    }
    for (int f = 0; f < o->nfiles; f++) {
        print_result(stdout, o->files[f], &tables[f]);
        if (extra) print_result(extra, o->files[f], &tables[f]);
    }
    fflush(stdout);
    if (extra && fclose(extra) != 0) die("cannot write output file");
}

/* ======================================================================
 * Implementation-specific part
 * ====================================================================== */
/*
 * Implementation I - multiprocess MapReduce, POSIX shared memory.
 *
 * Master                                    Worker (one fork() per task)
 * ------                                    ----------------------------
 * shm_open/ftruncate/mmap control region    inherits control region mapping
 * (one task_ctl_t per task)                 reads its task (file, byte range)
 * fork() at most N workers at a time        counts words in that range
 *                                           shm_open/ftruncate/mmap its OWN
 *                                           result segment, serializes table,
 *                                           stores size + status in control
 * waitpid() -> worker finished writing      _exit(0)
 * shm_open/mmap result segment, merge
 * munmap/close/shm_unlink
 *
 * Synchronization: a worker writes its result segment and control entry
 * strictly before it exits; the master touches them only after waitpid()
 * has reported that worker's exit. Each control entry and each result
 * segment is written by exactly one worker, so no locks are needed.
 */
#include <signal.h>
#include <sys/mman.h>
#include <sys/wait.h>

typedef struct {
    int file;
    int status;              /* 0 = pending, 1 = result ready, -1 = error */
    off_t start, end;
    uint64_t result_bytes;   /* size of the worker's result segment */
} task_ctl_t;

static pid_t master_pid;

static void ctl_name(char *buf, size_t n) { snprintf(buf, n, "/mr_ctl_%d", (int)master_pid); }
static void res_name(char *buf, size_t n, size_t task) { snprintf(buf, n, "/mr_res_%d_%zu", (int)master_pid, task); }

/* ---------- worker process ---------- */

static int worker_write_result(size_t idx, const wtable_t *t, task_ctl_t *ctl)
{
    char name[64];
    res_name(name, sizeof name, idx);
    size_t size = wt_serialized_size(t);
    int fd = shm_open(name, O_CREAT | O_EXCL | O_RDWR, 0600);
    if (fd < 0) return -1;
    if (ftruncate(fd, (off_t)size) < 0) { close(fd); return -1; }
    char *p = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (p == MAP_FAILED) { close(fd); return -1; }
    wt_serialize(t, p);
    munmap(p, size);
    close(fd);
    ctl[idx].result_bytes = size;
    ctl[idx].status = 1;     /* published; master reads it only after waitpid() */
    return 0;
}

static void worker_main(size_t idx, char **files, task_ctl_t *ctl)
{
    wtable_t t;
    int rc = -1;
    int fd = open(files[ctl[idx].file], O_RDONLY);
    if (fd >= 0) {
        wt_init(&t, 1024);
        if (count_range(fd, ctl[idx].start, ctl[idx].end, &t) == 0)
            rc = worker_write_result(idx, &t, ctl);
        wt_free(&t);
        close(fd);
    }
    if (rc != 0) ctl[idx].status = -1;
    _exit(rc == 0 ? 0 : 1);   /* _exit: never flush the master's stdio buffers */
}

/* ---------- master ---------- */

static int master_consume(size_t idx, const task_ctl_t *ctl, wtable_t *tables)
{
    char name[64];
    res_name(name, sizeof name, idx);
    int fd = shm_open(name, O_RDONLY, 0);
    if (fd < 0) return -1;
    size_t size = ctl[idx].result_bytes;
    int rc = -1;
    char *p = mmap(NULL, size, PROT_READ, MAP_SHARED, fd, 0);
    if (p != MAP_FAILED) {
        rc = wt_merge_serialized(&tables[ctl[idx].file], p, size);
        munmap(p, size);
    }
    close(fd);
    shm_unlink(name);
    return rc;
}

static int run_mapreduce(const options_t *o, const task_t *tasks, size_t ntasks, wtable_t *tables)
{
    char cname[64];
    master_pid = getpid();
    ctl_name(cname, sizeof cname);

    size_t ctl_size = ntasks * sizeof(task_ctl_t);
    int cfd = shm_open(cname, O_CREAT | O_EXCL | O_RDWR, 0600);
    if (cfd < 0) { perror("shm_open"); return -1; }
    if (ftruncate(cfd, (off_t)ctl_size) < 0) {
        perror("ftruncate");
        close(cfd);
        shm_unlink(cname);
        return -1;
    }
    task_ctl_t *ctl = mmap(NULL, ctl_size, PROT_READ | PROT_WRITE, MAP_SHARED, cfd, 0);
    if (ctl == MAP_FAILED) {
        perror("mmap");
        close(cfd);
        shm_unlink(cname);
        return -1;
    }
    for (size_t i = 0; i < ntasks; i++) {
        ctl[i].file = tasks[i].file;
        ctl[i].start = tasks[i].start;
        ctl[i].end = tasks[i].end;
        ctl[i].status = 0;
        ctl[i].result_bytes = 0;
    }

    fflush(stdout);   /* nothing buffered may be duplicated into children */
    fflush(stderr);

    pid_t *pids = xcalloc(ntasks, sizeof(pid_t));
    size_t next = 0, finished = 0;
    int active = 0, failed = 0;

    while (finished < next || (!failed && next < ntasks)) {
        /* keep at most N workers alive */
        while (!failed && active < o->workers && next < ntasks) {
            pid_t pid = fork();
            if (pid < 0) { perror("fork"); failed = 1; break; }
            if (pid == 0) worker_main(next, (char **)o->files, ctl);
            pids[next++] = pid;
            active++;
        }
        if (active == 0) break;

        int st;
        pid_t pid = waitpid(-1, &st, 0);
        if (pid < 0) {
            if (errno == EINTR) continue;
            perror("waitpid");
            failed = 1;
            break;
        }
        size_t idx = 0;
        while (idx < next && pids[idx] != pid) idx++;
        if (idx == next) continue;          /* not one of ours */
        active--;
        finished++;
        pids[idx] = 0;
        if (!WIFEXITED(st) || WEXITSTATUS(st) != 0 || ctl[idx].status != 1 ||
            master_consume(idx, ctl, tables) != 0) {
            fprintf(stderr, "error: worker for task %zu (file '%s') failed\n", idx, o->files[ctl[idx].file]);
            failed = 1;
        }
    }

    if (failed) {   /* stop and reap anything still running, remove leftovers */
        for (size_t i = 0; i < next; i++)
            if (pids[i] > 0) kill(pids[i], SIGTERM);
        for (size_t i = 0; i < next; i++)
            if (pids[i] > 0) waitpid(pids[i], NULL, 0);
        for (size_t i = 0; i < next; i++) {
            char name[64];
            res_name(name, sizeof name, i);
            shm_unlink(name);
        }
    }
    free(pids);
    munmap(ctl, ctl_size);
    close(cfd);
    shm_unlink(cname);
    return failed ? -1 : 0;
}

/* ======================================================================
 * main (identical in all three implementations)
 * ====================================================================== */

int main(int argc, char **argv)
{
    options_t o;
    init_tables();
    parse_args(argc, argv, &o);

    /* timing starts right before partitioning / parallel setup */
    double t0 = now_ms();

    size_t ntasks;
    task_t *tasks = build_tasks(o.nfiles, o.files, o.chunk_bytes, &ntasks);
    wtable_t tables[MAX_FILES];
    for (int f = 0; f < o.nfiles; f++) wt_init(&tables[f], 1024);

    if (run_mapreduce(&o, tasks, ntasks, tables) != 0) {
        fprintf(stderr, "error: processing failed\n");
        return EXIT_FAILURE;
    }
    emit_results(&o, tables);   /* printed in command-line order */

    for (int f = 0; f < o.nfiles; f++) wt_free(&tables[f]);
    free(tasks);

    /* timing ends after results are produced and workers are cleaned up */
    double t1 = now_ms();
    if (o.timing) fprintf(stderr, "elapsed_ms %.3f\n", t1 - t0);
    return EXIT_SUCCESS;
}
