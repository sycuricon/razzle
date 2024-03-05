    la t0, secret
    la t1, leak_target
    ld t1, 0(t1)
    add t0, t0, t1
    la t1, trapoline
    sub t0, t0, t1
    la t1, param_table
    addi t1, t1, 9*8
    sd t0, 0(t1)
    li s0, 5
    la s1, param_table
train_loop:
    ld a0, 0(s1)
    ld a1, 8(s1)
    INFO_VCTM_START
    call func_begin
    INFO_VCTM_END
    addi s0, s0, -1
    addi s1, s1, 16
    bne s0, zero, train_loop
