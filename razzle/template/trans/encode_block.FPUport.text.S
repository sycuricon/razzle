    la t1, secret_target
    ld t1, 0(t1)
    bne t0, t1, encode_fail
    fcvt.s.lu	fa5, t1
    fdiv.s	fa5, fa5, fa5
    fdiv.s	fa5, fa5, fa5
    fdiv.s	fa5, fa5, fa5
    fdiv.s	fa5, fa5, fa5
    fdiv.s	fa5, fa5, fa5
    fdiv.s	fa5, fa5, fa5
    fdiv.s	fa5, fa5, fa5
    fdiv.s	fa5, fa5, fa5
    fdiv.s	fa5, fa5, fa5
    fdiv.s	fa5, fa5, fa5
encode_fail:
    INFO_TEXE_END
