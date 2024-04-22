    la t0, trap_return_entry
    la t1, run_time_loop
    sd t1, 0(t0)
run_time_loop:
    ld t0, swap_mem_op
    csrw 0x800, t0
    fence.i
    INFO_VCTM_START
    j _text_swap_start
    INFO_VCTM_END
    j run_time_loop
