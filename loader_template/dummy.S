.section .text
.global _start
_start:
    li x1,0x80000000
    jalr x0,0(x1)