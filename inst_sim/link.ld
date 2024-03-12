OUTPUT_ARCH( "riscv" )
ENTRY(_text_start)
SECTIONS
{
	. = 0x80000000;
	.text : {
		_text_start = .;
		*(.text)
		_text_end = .;
	}
    . = ALIGN(0x1000);
	.data : {
		_data_start = .;
		*(.data)
		_data_end = .;
	}
	_end = .;
}
