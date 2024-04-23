    csrrw sp, sscratch, sp
    addi sp, sp, -8
    sd t0, 0(sp)
#ifdef __TRAP_DEBUG__
dump_strap_info:
    ld t0, strap_ptr_mode
    csrw 0x800, t0
    csrr t0, sepc
    csrw 0x800, t0
    csrr t0, scause
    csrw 0x800, t0
    csrr t0, stval
    csrw 0x800, t0
    ld t0, strap_char_mode
    csrw 0x800, t0
    li t0, '\n'
    csrw 0x800, t0
#endif
set_strap_return_entry:
    la t0, run_time_loop
    csrw sepc, t0
strap_exit:
    ld t0, 0(sp)
    addi sp, sp, 8
    csrrw sp, sscratch, sp
    sret