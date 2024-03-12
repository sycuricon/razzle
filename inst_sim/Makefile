SPIKE_BUILD ?= /home/zyy/starship-parafuzz/spike-parafuzz/build
SPIKE_INCLUDE := $(SPIKE_BUILD)/include
SPIKE_LIB	  := $(SPIKE_BUILD)/lib
SIMULATE	:=$(CURDIR)/Simulate

RISCV_PREFIX ?= riscv64-unknown-elf-
RISCV_GCC ?= $(RISCV_PREFIX)gcc
RISCV_GCC_OPTS ?= -march=rv64g_zicsr -mabi=lp64f -mcmodel=medany -nostdlib -nostartfiles -DNOBRANCH -g
RISCV_LD  ?= $(RISCV_PREFIX)ld
TESTCASE	:=$(CURDIR)/Testcase


export LD_LIBRARY_PATH=$(SPIKE_LIB)

sim:$(TESTCASE) $(SIMULATE)
	$(SIMULATE) $(TESTCASE)

$(SIMULATE):$(SIMULATE).cc
	g++ -std=c++17 -o $@ $<\
		-I $(SPIKE_INCLUDE)/cosim -I $(SPIKE_INCLUDE)/fdt -I $(SPIKE_INCLUDE)/fesvr -I $(SPIKE_INCLUDE)/riscv -I $(SPIKE_INCLUDE)/softfloat \
		-L $(SPIKE_LIB) -lcosim -lfdt -lriscv -lfesvr -ldisasm -lsoftfloat

$(TESTCASE):$(TESTCASE).o
	$(RISCV_LD) -T link.ld $^ -o $@

$(TESTCASE).o:$(TESTCASE).S
	$(RISCV_GCC) $(RISCV_GCC_OPTS) -c $< -o $@
	

clean:
	rm log* spike_sim
	
