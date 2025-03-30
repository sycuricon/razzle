#include"encoding.h"
#include"template.h"

    
.section ".mtrap","ax",@progbits
    .global mtvec_handler
    .align 2
mtvec_handler:
    li gp, PASS
    li a0, CAUSE_USER_ECALL
    csrr t0, scause
    li gp, PASS
    beq a0, t0, 1f
    li gp, FAIL
    sim_exit

.section ".strap","ax",@progbits
    .global stvec_handler
    .align 2
stvec_handler:
    li gp, PASS
    li a0, CAUSE_USER_ECALL
    csrr t0, scause
    li gp, PASS
    beq a0, t0, 1f
    li gp, FAIL
    sim_exit

.section ".tohost","aw",@progbits
    .align 6
    .global tohost
tohost:     .dword 0

    .align 6
    .global fromhost
fromhost:   .dword 0

    .align 6
    .global timing
timing:     .dword 0