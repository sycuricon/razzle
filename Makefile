RISCV_PREFIX ?= riscv64-unknown-elf-
RISCV_GCC ?= $(RISCV_PREFIX)gcc
RISCV_GCC_OPTS ?= -march=rv64g_zicsr -mabi=lp64f -mcmodel=medany -nostdlib -nostartfiles -DNOBRANCH -D__riscv
RISCV_OBJCOPY ?= $(RISCV_PREFIX)objcopy -O binary  
RISCV_OBJDUMP ?= $(RISCV_PREFIX)objdump -Mno-aliases -D
RISCV_LD  ?= $(RISCV_PREFIX)ld
BUILD_PATH  ?= $(CURDIR)/build

SRC_C = $(shell find $(BUILD_PATH) -name "*.c")
SRC_S = $(shell find $(BUILD_PATH) -name "*.S")
OBJ   = $(patsubst %.c,%.o,$(SRC_C)) $(patsubst %.S,%.o,$(SRC_S))

TARGET = $(BUILD_PATH)/Testbench

$(TARGET):$(OBJ)
	$(RISCV_LD) -T $(BUILD_PATH)/link.ld $^ -o $@
	nm $@ >  $(BUILD_PATH)/System.map

%.o:%.c
	$(RISCV_GCC) $(RISCV_GCC_OPTS) -c $< -o $@

%.o:%.S
	$(RISCV_GCC) $(RISCV_GCC_OPTS) -c $< -o $@

clean:
	rm -f $(BUILD_PATH)/*
