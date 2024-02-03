RISCV_PREFIX ?= riscv64-unknown-elf-
RISCV_GCC ?= $(RISCV_PREFIX)gcc
RISCV_GCC_OPTS ?= -march=rv64gc -mabi=lp64f -mcmodel=medany -nostdlib -nostartfiles -DNOBRANCH -D__riscv
RISCV_OBJCOPY ?= $(RISCV_PREFIX)objcopy -O binary  
RISCV_OBJDUMP ?= $(RISCV_PREFIX)objdump -Mno-aliases -D
RISCV_LD  ?= $(RISCV_PREFIX)ld
SRC_PATH  ?= $(CURDIR)/build

SRC_C = $(shell find $(SRC_PATH) -name "*.c")
SRC_S = $(shell find $(SRC_PATH) -name "*.S")
OBJ   = $(patsubst %.c,%.o,$(SRC_C)) $(patsubst %.S,%.o,$(SRC_S))

TARGET = $(SRC_PATH)/Testbench

$(TARGET):$(OBJ)
	$(RISCV_LD) -T $(SRC_PATH)/link.ld $^ -o $@

%.o:%.c
	$(RISCV_GCC) $(RISCV_GCC_OPTS) -c $< -o $@

%.o:%.S
	$(RISCV_GCC) $(RISCV_GCC_OPTS) -c $< -o $@

clean:
	rm -f $(SRC_PATH)/*.o $(SRC_PATH)/*.c $(SRC_PATH)/*.S $(TARGET)