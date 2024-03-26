    la t0, secret
    ld t1, leak_target
    add t1, t0, t1
    lb t0, 0(t1)

    ecall

    INFO_BIM_START
    li t0, 180
init_bim_loop:
    addi t0, t0, -1
    bne t0, zero, init_bim_loop
    INFO_BIM_END