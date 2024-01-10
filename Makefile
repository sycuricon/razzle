spike = $(CURDIR)/spike
spike_srcdir = $(CURDIR)/../riscv-isa-cosim
spike_wrkdir = build
RISCV_OPT ?= -march=rv64i_zicsr -mabi=lp64 -mcmodel=medany -nostdlib -nostartfiles -DNOBRANCH

$(spike): $(spike_srcdir)
	rm -rf $(spike_wrkdir)
	mkdir -p $(spike_wrkdir)
	mkdir -p $(dir $@)
	cd $(spike_wrkdir) && $</configure \
		--prefix=$(dir $(abspath $(dir $@)))
	$(MAKE) -C $(spike_wrkdir)
	$(MAKE) -C $(spike_wrkdir) install

bin:
	$(RISCV)/bin/riscv64-unknown-linux-gnu-gcc $(RISCV_OPT) -T link.ld dump_initial.S -o dump_initial.out
	$(RISCV)/bin/riscv64-unknown-linux-gnu-objcopy -O binary dump_initial.out dump_initial.bin
	od -v -An -tx4 dump_initial.bin > dump_initial.hex
	# rm -rf dump_initial.bin
