OUTPUT_ARCH( "riscv" )
ENTRY(_text_start)
SECTIONS
{
	. = 0x80000000;
	.init : {
		*(.init)
	}
    . = 0x80001000;
    .trap : {
		*(.mtrap)
		. = 0x80001800;
        *(.strap)
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
        *(.text.arbtrary_block_0)
        *(.text.jmp_train_1)
    }
    . = 0x80400000;
    .train2 : {
        *(.text.arbtrary_block_1)
        *(.text.jmp_victim)
    }
    . = 0x80600000;
    .victim : {
        *(.text.load_init_block)
        *(.text.nop_block)
        *(.text.delay_block)
        *(.text.trigger_block)
    }
}
