CC      = gcc
CFLAGS  = -O2 -Wall -Wextra -std=gnu11
LDLIBS_SHM    = -lrt
LDLIBS_THREAD = -pthread

BINS = mapreduce_shm mapreduce_pipe mapreduce_thread

.PHONY: all clean test bench report dist

all: $(BINS)

mapreduce_shm: shared_memory/mapreduce_shm.c
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS_SHM)

mapreduce_pipe: message_passing/mapreduce_pipe.c
	$(CC) $(CFLAGS) -o $@ $<

mapreduce_thread: multithreading/mapreduce_thread.c
	$(CC) $(CFLAGS) -pthread -o $@ $< $(LDLIBS_THREAD)

# Correctness tests (sample inputs, many worker counts and chunk sizes)
test: all
	sh tests/run_tests.sh

# Performance experiments (generates ~400 MB of data under bench/data)
bench: all
	python3 bench/gen_data.py bench/data
	sh bench/run_bench.sh bench/data bench/results.csv
	python3 bench/plot.py bench/results.csv bench/figures

# Rebuild report.pdf from bench/results.csv, bench/extra.csv and the figures
report:
	python3 bench/plot.py bench/results.csv bench/figures
	python3 report/build_report.py
	node report/html2pdf.js report/report.html report.pdf

# Submission archive: required layout (+ tests/ and bench/ scripts used by the README)
STUDENT_ID ?= StudentID
dist:
	rm -rf OS_MapReduce_$(STUDENT_ID) OS_MapReduce_$(STUDENT_ID).zip
	mkdir -p OS_MapReduce_$(STUDENT_ID)/shared_memory OS_MapReduce_$(STUDENT_ID)/message_passing OS_MapReduce_$(STUDENT_ID)/multithreading
	cp shared_memory/mapreduce_shm.c OS_MapReduce_$(STUDENT_ID)/shared_memory/
	cp message_passing/mapreduce_pipe.c OS_MapReduce_$(STUDENT_ID)/message_passing/
	cp multithreading/mapreduce_thread.c OS_MapReduce_$(STUDENT_ID)/multithreading/
	cp Makefile README.md report.pdf OS_MapReduce_$(STUDENT_ID)/
	mkdir -p OS_MapReduce_$(STUDENT_ID)/tests OS_MapReduce_$(STUDENT_ID)/bench
	cp -r tests/sample_inputs tests/expected_output.txt tests/reference.py tests/run_tests.sh OS_MapReduce_$(STUDENT_ID)/tests/
	cp bench/*.py bench/*.sh OS_MapReduce_$(STUDENT_ID)/bench/
	zip -r OS_MapReduce_$(STUDENT_ID).zip OS_MapReduce_$(STUDENT_ID)

clean:
	rm -f $(BINS)
