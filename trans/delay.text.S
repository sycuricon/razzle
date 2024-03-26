    INFO_DELAY_START
    la t0, delay_dummy1
    ld t0, 0(t0)
    la t1, delay_dummy2
    ld t1, 0(t1)
    fcvt.s.lu   fa4, t0
    fcvt.s.lu	fa5, t1
    fdiv.s	fa5, fa5, fa4
    fdiv.s	fa5, fa5, fa4
    fdiv.s	fa5, fa5, fa4
    fdiv.s	fa5, fa5, fa4
    fdiv.s	fa5, fa5, fa4
    fcvt.lu.s   t2, fa5, rtz
    INFO_DELAY_END