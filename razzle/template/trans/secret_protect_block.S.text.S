protect_S_mode:    
    la t0, vaddr_0x4000_paddr_0x80004000
    ld t1, 0(t0)
    andi t1, t1, ~(1<<4)
    sd t1, 0(t0)
