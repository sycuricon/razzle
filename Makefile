RISCV_OPT ?= -march=rv64i_zicsr -mabi=lp64 -mcmodel=medany -nostdlib -nostartfiles -DNOBRANCH
REG_STATE_FILE ?= reginfo.json
REG_STATE_BIN = $(REG_STATE_FILE).bin
REG_STATE_HEX = $(REG_STATE_FILE).hex
REG_STATE_DATA_HEX = $(REG_STATE_FILE).data.hex
REG_STATE_TEXT_HEX = $(REG_STATE_FILE).text.hex

bin:$(REG_STATE_BIN) dump_initial.S
	$(RISCV)/bin/riscv64-unknown-linux-gnu-gcc $(RISCV_OPT) -D REG_STATE_BIN=\"$(REG_STATE_BIN)\" \
		-T link.ld dump_initial.S -o dump_initial.out
	$(RISCV)/bin/riscv64-unknown-linux-gnu-objdump -D dump_initial.out > dump_initial.asm
	$(RISCV)/bin/riscv64-unknown-linux-gnu-objcopy -O binary dump_initial.out dump_initial.bin
	od -v -An -tx4 dump_initial.bin > $(REG_STATE_HEX)
	rm -rf dump_initial.bin

$(REG_STATE_BIN):$(REG_STATE_FILE)
	python3 reg_init.py $(REG_STATE_FILE) $(REG_STATE_FILE).bin bin

hex:$(REG_STATE_DATA_HEX) $(REG_STATE_TEXT_HEX)
	cat $(REG_STATE_TEXT_HEX) > $(REG_STATE_HEX)
	echo @00000068 >> $(REG_STATE_HEX)
	cat $(REG_STATE_DATA_HEX) >> $(REG_STATE_HEX) 

$(REG_STATE_TEXT_HEX):dump_initial.S
	$(RISCV)/bin/riscv64-unknown-linux-gnu-gcc $(RISCV_OPT) -D REG_STATE_BIN=\"$(REG_STATE_BIN)\" \
		-T link.ld dump_initial.S -o dump_initial.out
	$(RISCV)/bin/riscv64-unknown-linux-gnu-objcopy --only-section .text -O binary dump_initial.out dump_initial.bin
	od -v -An -tx4 dump_initial.bin > $(REG_STATE_TEXT_HEX)
	rm -rf dump_initial.bin

$(REG_STATE_DATA_HEX):$(REG_STATE_FILE) reg_init.py
	python3 reg_init.py $(REG_STATE_FILE) $(REG_STATE_DATA_HEX) hex

dummy:
	$(RISCV)/bin/riscv64-unknown-linux-gnu-gcc $(RISCV_OPT) -T link.ld dummy.S -o dummy.out
	$(RISCV)/bin/riscv64-unknown-linux-gnu-objcopy -O binary dummy.out dummy.bin
	od -v -An -tx4 dummy.bin > dummy.hex
	# rm -rf dummy.bin