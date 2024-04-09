protect_M_mode:   
    li t0, 0x200011ff
    csrw pmpaddr0, t0
    csrr t0, pmpcfg0
    ori t0, t0, 0x98
    csrw pmpcfg0, t0
