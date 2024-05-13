encode_block_0:
    la t1, secret_target
    ld t1, 0(t1)
    bne s0, t1, encode_exit
encode_success:
    la t0, array
    ld t1, 0(t0)
    ld t1, 8(t0)
    ld t1, 16(t0)
    ld t1, 24(t0)
    ld t1, 32(t0)
    ld t1, 40(t0)
    ld t1, 48(t0)
    ld t1, 56(t0)
    ld t1, 64(t0)
    ld t1, 72(t0)
    ld t1, 80(t0)
    ld t1, 88(t0)
    ld t1, 96(t0)
