#include "encoding.h"
    INFO_TRAIN_END    
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
    fence
    sfence.vma

    andi t1, t0, 0x8
    slli t1, t1, 9
    csrr t2, mtvec
    add t2, t1, t2
    csrw mtvec, t2
    csrr t2, stvec
    add t2, t1, t2
    csrw stvec, t2

    li t1, 0xFFFFFFFFFFFFF000
    and t1, t0, t1
    csrw mepc, t1
    mret

.align 12

    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    INFO_VCTM_END
    j mtrap_block_entry