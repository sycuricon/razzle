    la t1, secret_target
    ld t1, 0(t1)
    bne t0, t1, encode_fail
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
encode_fail:
    INFO_TEXE_END
