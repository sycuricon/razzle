    INFO_BIM_START
    li t0, 400
init_bim_loop:
    addi t0, t0, -1
    bne t0, zero, init_bim_loop
    INFO_BIM_END