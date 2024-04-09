    csrrw sp, sscratch, sp
    addi sp, sp, -8
    sd t0, 0(sp)

    ld t0, strap_ptr_mode
    csrw 0x800, t0
    csrr t0, sepc
    csrw 0x800, t0
    csrr t0, scause
    csrw 0x800, t0
    csrr t0, stval
    csrw 0x800, t0
    ld t0, strap_char_mode
    csrw 0x800, t0
    li t0, '\n'
    csrw 0x800, t0

    la t0, trap_return_entry
    ld t0, 0(t0) 
    csrw sepc, t0
    
    ld t0, 0(sp)
    addi sp, sp, 8
    csrrw sp, sscratch, sp
    sret