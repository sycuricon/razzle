    INFO_TEXE_START
    la t0, target_offset
    ld t1, 0(t0)
    la t0, trapoline
    add t0, t0, t1
    lb t0, 0(t0)