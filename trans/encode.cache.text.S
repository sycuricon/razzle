    INFO_TEXE_START
    la t0, trapoline
    add t0, t0, a1
    lb t0, 0(t0)
    la t1, array
    slli t0, t0, 6
    add t0, t0, t1
    lb t0, 0(t0)
    INFO_TEXE_END