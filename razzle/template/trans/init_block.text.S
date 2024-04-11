    la t0, secret
    ld t1, leak_target
    add t1, t0, t1
    lb t0, 0(t1)
secret_protect_call:
    ecall
start_bim_init:
    INFO_BIM_START
    li t0, 180
init_bim_loop:
    addi t0, t0, -1
    bne t0, zero, init_bim_loop
finish_bim_init:
    INFO_BIM_END