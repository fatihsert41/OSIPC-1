#!/bin/sh
# Correctness tests for all three implementations.
#  1) sample inputs vs. tests/expected_output.txt
#  2) tiny chunk sizes (1..7 bytes) so that chunk boundaries cut every word
#  3) random generated files vs. the Python reference (tests/reference.py)
#  4) error handling and resource cleanup (no leftover /dev/shm objects)
cd "$(dirname "$0")/.." || exit 1
S=tests/sample_inputs
FILES="$S/file1.txt $S/file2.txt $S/edge_cases.txt $S/fewer_than_five.txt $S/empty.txt"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
check() {  # name expected actual
    if cmp -s "$2" "$3"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; diff "$2" "$3" | head -5; fi
}
for impl in shm pipe thread; do
    bin=./mapreduce_$impl
    for n in 1 2 4 8 16; do
        $bin $n $FILES > "$TMP/out" 2>&1; check "$impl N=$n" tests/expected_output.txt "$TMP/out"
        for c in 1 2 3 7 64 1M; do
            $bin $n -c $c $FILES > "$TMP/out" 2>&1; check "$impl N=$n chunk=$c" tests/expected_output.txt "$TMP/out"
        done
    done
    # -o option writes the same output to a file
    $bin 3 -o "$TMP/o.txt" $FILES > /dev/null; check "$impl -o" tests/expected_output.txt "$TMP/o.txt"
done

# random files: long words, digits, punctuation, mixed case, no trailing newline
python3 - "$TMP" <<'PY'
import random, sys, os
random.seed(7)
vocab = ["".join(random.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(random.randint(1, 40))) for _ in range(3000)]
seps = [" ", "\n", ", ", ". ", "123", "\t", "--", "\xe7\xf6", "'", "_9_"]
for i in range(10):
    n = random.choice([0, 1, 50, 5000, 200000])
    with open(os.path.join(sys.argv[1], f"r{i}.txt"), "wb") as f:
        parts = []
        for _ in range(n):
            parts.append(random.choice(vocab[: random.randint(1, 3000)]).encode())
            parts.append(random.choice(seps).encode("latin-1"))
        f.write(b"".join(parts)[:-1] if parts else b"")
PY
R=$(ls "$TMP"/r*.txt)
python3 tests/reference.py $R > "$TMP/ref"
for impl in shm pipe thread; do
    for n in 1 3 8; do
        for c in 4099 65536 1M; do
            ./mapreduce_$impl $n -c $c $R > "$TMP/out" 2>&1; check "$impl random N=$n chunk=$c" "$TMP/ref" "$TMP/out"
        done
    done
done

# error handling
for impl in shm pipe thread; do
    if ./mapreduce_$impl 2 no_such_file.txt > /dev/null 2>&1; then fail=$((fail+1)); echo "FAIL: $impl missing file accepted"; else pass=$((pass+1)); fi
    if ./mapreduce_$impl 0 $S/file1.txt > /dev/null 2>&1; then fail=$((fail+1)); echo "FAIL: $impl N=0 accepted"; else pass=$((pass+1)); fi
    if ./mapreduce_$impl 2 $S/file1.txt $S/file1.txt $S/file1.txt $S/file1.txt $S/file1.txt $S/file1.txt \
         $S/file1.txt $S/file1.txt $S/file1.txt $S/file1.txt $S/file1.txt > /dev/null 2>&1; then
        fail=$((fail+1)); echo "FAIL: $impl 11 files accepted"; else pass=$((pass+1)); fi
done
if [ -d /dev/shm ] && ls /dev/shm 2>/dev/null | grep -q '^mr_'; then
    fail=$((fail+1)); echo "FAIL: leftover shared memory objects:"; ls /dev/shm | grep '^mr_'
else pass=$((pass+1)); fi

echo "passed: $pass  failed: $fail"
[ "$fail" -eq 0 ]
