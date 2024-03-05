//a0 time
//a1 guess
dump_channel:
    ld t0, ptr_mode
    csrw 0x800, t0
    la t0, array
    slli t1, a1, 6
    add t0, t0, t1
    csrw 0x800, t0
    ld t0, num_mode
    csrw 0x800, t0
    csrw 0x800, a1
    csrw 0x800, a0
    ld t0, char_mode
    csrw 0x800, t0
    li t0, '\n'
    csrw 0x800, t0
do_exit:
    ld t0, exit_stop
    csrw 0x800, t0