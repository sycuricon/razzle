SPIKE_DIR		?= /work/riscv-isa-cosim
SPIKE_BUILD 	:= $(SPIKE_DIR)/build

SIMULATE		:= $(CURDIR)/solve
TESTCASE		?= $(CURDIR)/tmp
DUMPLOG			?= $(CURDIR)/dump

export LD_LIBRARY_PATH=$(SPIKE_BUILD)

sim: $(TESTCASE) $(SIMULATE)
	$(SIMULATE) $(TESTCASE) $(DUMPLOG)

$(SIMULATE): $(SIMULATE).cc
	g++ -std=c++17 -o $@ $<	\
		-I $(SPIKE_BUILD) -I $(SPIKE_DIR)/cosim -I $(SPIKE_DIR)/fdt -I $(SPIKE_DIR)/fesvr -I $(SPIKE_DIR)/riscv -I $(SPIKE_DIR)/softfloat \
		-L $(SPIKE_BUILD) -lcosim -lfdt -lriscv -lfesvr -ldisasm -lsoftfloat

clean:
	rm log* spike_sim
