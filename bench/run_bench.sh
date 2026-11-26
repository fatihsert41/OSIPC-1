#!/bin/sh
# Run every implementation on every dataset with N in {1,2,4,8,16},
# REPS repetitions each, and append "impl,dataset,N,rep,ms" to the CSV.
# Usage: sh bench/run_bench.sh [data_dir] [out.csv] [extra program options]
DATA=${1:-bench/data}; OUT=${2:-bench/results.csv}; shift 2 2>/dev/null
EXTRA="$*"
REPS=${REPS:-5}
cd "$(dirname "$0")/.." || exit 1
echo "impl,dataset,workers,rep,ms" > "$OUT"
for ds in D1 D2 D3 D4 D5; do
    files=$(ls "$DATA/$ds"/*.txt)
    cat $files > /dev/null                       # warm the page cache
    for impl in shm pipe thread; do
        ./mapreduce_$impl 1 $EXTRA $files > /dev/null   # warm-up run (not recorded)
        for n in 1 2 4 8 16; do
            r=1
            while [ $r -le $REPS ]; do
                ms=$(./mapreduce_$impl $n -t $EXTRA $files 2>&1 >/dev/null | awk '/elapsed_ms/{print $2}')
                echo "$impl,$ds,$n,$r,$ms" >> "$OUT"
                r=$((r+1))
            done
        done
        echo "done $ds $impl" >&2
    done
done
