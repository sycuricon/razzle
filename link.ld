OUTPUT_ARCH( "riscv" )
ENTRY(_start)

SECTIONS
{
  . = 0x20000;
  .text : {*(.text)}
  . = ALIGN(0x10);
  .data : {*(.data)}
}