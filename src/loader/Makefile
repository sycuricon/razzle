ROOT_DIR	?=	$(dir $(abspath $(lastword $(MAKEFILE_LIST))))
SRC_DIR		:= 	$(ROOT_DIR)/firmware/rvsnap/src/loader
BUILD_DIR	:=	$(ROOT_DIR)/build/firmware/rvsnap

CC			=	$(RISCV)/bin/riscv64-unknown-elf-gcc
OBJCOPY		=	$(RISCV)/bin/riscv64-unknown-elf-objcopy
OBJDUMP		=	$(RISCV)/bin/riscv64-unknown-elf-objdump

elf	:= $(BUILD_DIR)/init.elf
bin	:= $(BUILD_DIR)/init.bin
img	:= $(BUILD_DIR)/init.img

all: $(img)

elf: $(elf)
$(elf): $(BUILD_DIR)/init.S link.ld
	mkdir -p $(BUILD_DIR)
	$(CC) -Tlink.ld -I$(SRC_DIR) $< -nostdlib -static -Wl,--no-gc-sections -o $@

bin: $(bin)
$(bin): $(elf)
	mkdir -p $(BUILD_DIR)
	$(OBJCOPY) -O binary $< $@

img: $(img)
$(img): $(bin)
	mkdir -p $(BUILD_DIR)
	dd if=$< of=$@ bs=512 count=1
