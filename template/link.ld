OUTPUT_ARCH( "riscv" )
ENTRY(_start)

SECTIONS {
  . = 0x80000000;

  _fuzz_handler_start = .;
  .text.init : { 
    *(.text.init) 
    *build/vm*.o(.text .rela.text)
  }
  _fuzz_handler_end = .;

  . = ALIGN(0x1000);
  .text : { 
    EXCLUDE_FILE(*build/vm*.o) *(.text .rela.text) 
  }

  . = ALIGN(0x1000);
  .data : { 
    EXCLUDE_FILE(*build/vm*.o) *(.data .rodata) 
  }
  .bss : { 
    EXCLUDE_FILE(*build/vm*.o) *(.bss .sbss) 
  }
  . += 0x1000;

  . = ALIGN(0x1000);
  .data.init : { 
    *build/vm*.o(.data .rodata)
  }
  .bss.init : { 
    *build/vm*.o(.bss .sbss)
  }

  . = ALIGN(0x1000);
  .tohost : { *(.tohost) }
  _end = .;
}

