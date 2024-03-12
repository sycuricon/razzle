SPIKE_BUILD ?= /home/zyy/starship-parafuzz/spike-parafuzz/build
SPIKE_INCLUDE := $(SPIKE_BUILD)/include
SPIKE_LIB	  := $(SPIKE_BUILD)/lib
TESTCASE	?= 

export LD_LIBRARY_PATH=$(SPIKE_LIB)

all:
	g++ -std=c++17 -o spike_sim spike_sim.cc\
		-I $(SPIKE_INCLUDE)/cosim -I $(SPIKE_INCLUDE)/fdt -I $(SPIKE_INCLUDE)/fesvr -I $(SPIKE_INCLUDE)/riscv -I $(SPIKE_INCLUDE)/softfloat \
		-L $(SPIKE_LIB) -lcosim -lfdt -lriscv -lfesvr -ldisasm -lsoftfloat
	./spike_sim $(TESTCASE)

clean:
	rm log* spike_sim
	
