#include "encoding.h"    
    fence
    INFO_VCTM_END
#ifdef __TRAP_DEBUG__
dump_mtrap_info:
    ld t0, mtrap_ptr_mode
    csrw 0x800, t0
    csrr t0, mepc
    csrw 0x800, t0
    csrr t0, mcause
    csrw 0x800, t0
    csrr t0, mtval
    csrw 0x800, t0
    ld t0, mtrap_char_mode
    csrw 0x800, t0
    li t0, '\n'
    csrw 0x800, t0
#endif
set_mtrap_return_entry:
    ld t0, mtrap_swap_mem_op
    csrrw t0, 0x800, t0
    fence.i

    li t1, MSTATUS_MPP
    csrc mstatus, t1
    andi t1, t0, 0x3
    slli t1, t1, 11
    csrs mstatus, t1

    li t1, 0xF
    slli t1, t1, 60
    csrc satp, t1
    andi t1, t0, 0x4
    slli t1, t1, 61
    csrs satp, t1

    li t1, 0xFFFFFFFFFFFFFFF8
    and t1, t0, t1
    csrw mepc, t1

    INFO_VCTM_START
    mret