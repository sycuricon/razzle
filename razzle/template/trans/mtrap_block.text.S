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
    csrw 0x800, t0
    fence.i
    la t0, _text_swap_start
    csrw mepc, t0
    INFO_VCTM_START
    mret