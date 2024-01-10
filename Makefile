RISCV_OPT ?= -march=rv64i_zicsr -mabi=lp64 -mcmodel=medany -nostdlib -nostartfiles -DNOBRANCH

bin:
	$(RISCV)/bin/riscv64-unknown-linux-gnu-gcc $(RISCV_OPT) -T link.ld dump_initial.S -o dump_initial.out
	$(RISCV)/bin/riscv64-unknown-linux-gnu-objcopy -O binary dump_initial.out dump_initial.bin
	od -v -An -tx4 dump_initial.bin > dump_initial.hex
	# rm -rf dump_initial.bin

dummy:
	$(RISCV)/bin/riscv64-unknown-linux-gnu-gcc $(RISCV_OPT) -T link.ld dummy.S -o dummy.out
	$(RISCV)/bin/riscv64-unknown-linux-gnu-objcopy -O binary dummy.out dummy.bin
	od -v -An -tx4 dummy.bin > dummy.hex
	# rm -rf dummy.bin
