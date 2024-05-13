encode_block_0:
    la t1, array
    slli s0, s0, 6
    add s0, s0, t1
    lb s0, 0(s0)