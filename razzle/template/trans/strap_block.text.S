    INFO_VCTM_END
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
    ld t0, strap_swap_mem_op
    csrw 0x800, t0
    fence.i
    la t0, _text_swap_start
#ifdef __VIRTUAL__
    li t1, 0x100000
    add t0, t0, t1
#endif
    csrw sepc, t0
    INFO_VCTM_START
    sret