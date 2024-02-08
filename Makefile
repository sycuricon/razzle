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

all:$(ORIGIN_TARGET) $(VARIANT_TARGET)

$(ORIGIN_TARGET):$(ORIGIN_OBJ)
	$(RISCV_LD) -T $(BUILD_PATH)/link.ld $^ -o $@
	nm $@ >  $(BUILD_PATH)/System.map

$(VARIANT_TARGET):$(VARIANT_OBJ)
	$(RISCV_LD) -T $(BUILD_PATH)/link.ld $^ -o $@
	nm $@ >  $(BUILD_PATH)/System.variant.map

%.o:%.c
	$(RISCV_GCC) $(RISCV_GCC_OPTS) -c $< -o $@

%.o:%.S
	$(RISCV_GCC) $(RISCV_GCC_OPTS) -c $< -o $@

clean:
	rm -f $(BUILD_PATH)/*
