    csrrw sp, mscratch, sp
    addi sp, sp, -16
    sd t0, 0(sp)
    sd t1, 8(sp)
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
    la t0, run_time_loop
    csrw mepc, t0
mtrap_exit:
    ld t0, 0(sp)
    ld t1, 8(sp)
    addi sp, sp, 16
    csrrw sp, mscratch, sp
    mret