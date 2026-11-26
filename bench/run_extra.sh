#!/bin/sh
# Extra experiments used in the report (median of REPS runs each):
#  1) chunk-size sweep: D2 (100 MB), N=4, chunk = 64K .. 128M
#  2) small file split: D1 (1 MB) with 128 KiB chunks, N = 1..16
#  3) fixed overhead: 10 tiny files (sample inputs), N = 1 and N = 10
DATA=${1:-bench/data}; OUT=${2:-bench/extra.csv}
REPS=${REPS:-5}
cd "$(dirname "$0")/.." || exit 1
med() { sort -n | awk '{a[NR]=$1} END{print a[int((NR+1)/2)]}'; }
run() { # impl reps args...
    impl=$1; shift
    i=0; while [ $i -lt $REPS ]; do ./mapreduce_$impl "$@" -t 2>&1 >/dev/null | awk '/elapsed_ms/{print $2}'; i=$((i+1)); done | med
}
echo "experiment,impl,param,workers,median_ms" > "$OUT"
for c in 64K 256K 1M 4M 8M 16M 32M 128M; do
    for impl in shm pipe thread; do echo "chunk,$impl,$c,4,$(run $impl 4 -c $c $DATA/D2/*.txt)" >> "$OUT"; done
done
for n in 1 2 4 8 16; do
    for impl in shm pipe thread; do echo "d1split,$impl,128K,$n,$(run $impl $n -c 128K $DATA/D1/*.txt)" >> "$OUT"; done
done
S=tests/sample_inputs
TINY="$S/file1.txt $S/file2.txt $S/edge_cases.txt $S/fewer_than_five.txt $S/empty.txt $S/file1.txt $S/file2.txt $S/edge_cases.txt $S/fewer_than_five.txt $S/empty.txt"
for n in 1 10; do
    for impl in shm pipe thread; do REPS=21; echo "overhead,$impl,10tiny,$n,$(run $impl $n $TINY)" >> "$OUT"; done
done
echo "wrote $OUT"
