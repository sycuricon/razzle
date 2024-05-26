do_exit:
    ld t0, exit_stop
    csrw 0x800, t0
exit_loop:
    j exit_loop