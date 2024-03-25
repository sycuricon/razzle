    INFO_TEXE_START
    la t0, trapoline
    add t0, t0, a1
    lb t0, 0(t0)
    la t1, secret_target
    ld t1, 0(t1)
    bne t0, t1, encode_fail
port_loop:
    mul t1, t1, t1
    mul t1, t1, t1
    mul t1, t1, t1
    mul t1, t1, t1
    mul t1, t1, t1
    mul t1, t1, t1
    mul t1, t1, t1
    mul t1, t1, t1
    mul t1, t1, t1
    mul t1, t1, t1
    mul t1, t1, t1
    mul t1, t1, t1
    mul t1, t1, t1
encode_fail:
    INFO_TEXE_END
