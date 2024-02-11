RISCV_PREFIX ?= riscv64-unknown-elf-
RISCV_GCC ?= $(RISCV_PREFIX)gcc
RISCV_GCC_OPTS ?= -march=rv64g_zicsr -mabi=lp64f -mcmodel=medany -nostdlib -nostartfiles -DNOBRANCH -D__riscv
RISCV_OBJCOPY ?= $(RISCV_PREFIX)objcopy -O binary  
RISCV_OBJDUMP ?= $(RISCV_PREFIX)objdump -Mno-aliases -D
RISCV_LD  ?= $(RISCV_PREFIX)ld
BUILD_PATH  ?= $(CURDIR)/build

include $(BUILD_PATH)/origin_list.mk
include $(BUILD_PATH)/variant_list.mk
ORIGIN_OBJ   = $(patsubst %.c,%.o,$(ORIGIN_SRC_C)) $(patsubst %.S,%.o,$(ORIGIN_SRC_S))
VARIANT_OBJ   = $(patsubst %.c,%.o,$(VARIANT_SRC_C)) $(patsubst %.S,%.o,$(VARIANT_SRC_S))

ORIGIN_TARGET = $(BUILD_PATH)/Testbench
VARIANT_TARGET = $(BUILD_PATH)/Testbench.variant
ORIGIN_TARGET_HEX = $(ORIGIN_TARGET).hex
VARIANT_TARGET_HEX = $(VARIANT_TARGET).hex

all:$(ORIGIN_TARGET_HEX) $(VARIANT_TARGET_HEX)

$(ORIGIN_TARGET_HEX):$(ORIGIN_TARGET)
	$(RISCV_OBJCOPY) $< tmp.bin
	od -v -An -tx8 tmp.bin > $@.hex
	rm -f tmp.bin

$(VARIANT_TARGET_HEX):$(VARIANT_TARGET)
	$(RISCV_OBJCOPY) $< tmp.bin
	od -v -An -tx8 tmp.bin > $@.hex
	rm -f tmp.bin

$(ORIGIN_TARGET):$(ORIGIN_OBJ)
	$(RISCV_LD) -T $(BUILD_PATH)/link.ld $^ -o $@

$(VARIANT_TARGET):$(VARIANT_OBJ)
	$(RISCV_LD) -T $(BUILD_PATH)/link.ld $^ -o $@

%.o:%.c
	$(RISCV_GCC) $(RISCV_GCC_OPTS) -c $< -o $@

%.o:%.S
	$(RISCV_GCC) $(RISCV_GCC_OPTS) -c $< -o $@

clean:
	rm -f $(BUILD_PATH)/*
