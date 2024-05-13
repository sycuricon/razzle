encode_block_0:
    la t1, secret_target
    ld t1, 0(t1)
    bne s0, t1, encode_exit
encode_success:
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

