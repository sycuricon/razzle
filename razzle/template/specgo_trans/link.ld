OUTPUT_ARCH( "riscv" )
ENTRY(_init_start)
SECTIONS
{
	. = 0x80000000;
	.init : {
        _init_start = .;
		*(.text.init)
        _init_end = .;
	}
    . = 0x80001000;
    .mtrap : {
        _mtrap_start = .;
		*(.mtrap)
        _mtrap_end = .;
    }
	. = 0x80001800;
    .strap : {
        _strap_start = .;
        *(.strap)
        _strap_end = .;
	}
    . = 0x80002000;
    .tohost : {
        *(.tohost)
    }
    . = 0x80006000;
    .data : {
        *(.data.random_data_block)
        *(.data.channel_block)
        *(.data.load_init_block)
    }
    . = 0x8000d000;
    .pagetable : {
        *(.pagetable)
    }
    . = 0x80200000;
    .train1 : {
        _train1_start = .;
        *(.text.arbtrary_block_0)
        *(.text.jmp_train_2)
        _train1_end = .;
    }
    . = 0x80400000;
    .train2 : {
        _train2_start = .;
        *(.text.arbtrary_block_1)
        *(.text.jmp_victim)
        _train2_end = .;
    }
    . = 0x80600000;
    .victim : {
        _victim_start = .;
        *(.text.load_init_block)
        *(.text.nop_block)
        *(.text.delay_block)
        *(.text.trigger_block)
        _victim_end = .;
    }
}
