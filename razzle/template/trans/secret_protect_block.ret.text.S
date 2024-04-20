secret_protect_exit:
    la t0, mtrap_block_entry
    csrw mtvec, t0
    csrr t0, mepc
    addi t0, t0, 4
    csrw mepc, t0
    mret