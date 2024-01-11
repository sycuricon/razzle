#define pop(a0,a1) \
    ld a0, 0(a1);   \
    addi a1, a1, 8
#define pop_csr(csr,a0,a1) \
    ld a0, 0(a1); \
    addi a1, a1, 8; \
    csrw csr, a0

.section .text
.global _start
_start:
    la x31,reg_info
    pop_csr(sstatus,x1,x31)
    pop_csr(sie,x1,x31)
    pop_csr(stvec,x1,x31)
    pop_csr(scounteren,x1,x31)
    pop_csr(sscratch,x1,x31)
    pop_csr(satp,x1,x31)
    pop_csr(misa,x1,x31)
    pop_csr(medeleg,x1,x31)
    pop_csr(mideleg,x1,x31)
    pop_csr(mie,x1,x31)
    pop_csr(mtvec,x1,x31)
    pop_csr(mcounteren,x1,x31)
    pop_csr(pmpcfg0,x1,x31)
    pop_csr(pmpcfg2,x1,x31)
    pop_csr(pmpaddr0,x1,x31)
    pop_csr(pmpaddr1,x1,x31)
    pop_csr(pmpaddr2,x1,x31)
    pop_csr(pmpaddr3,x1,x31)
    pop_csr(pmpaddr4,x1,x31)
    pop_csr(pmpaddr5,x1,x31)
    pop_csr(pmpaddr6,x1,x31)
    pop_csr(pmpaddr7,x1,x31)
    pop_csr(pmpaddr8,x1,x31)
    pop_csr(pmpaddr9,x1,x31)
    pop_csr(pmpaddr10,x1,x31)
    pop_csr(pmpaddr11,x1,x31)
    pop_csr(pmpaddr12,x1,x31)
    pop_csr(pmpaddr13,x1,x31)
    pop_csr(pmpaddr14,x1,x31)
    pop_csr(pmpaddr15,x1,x31)
    pop_csr(mstatus,x1,x31)
    pop_csr(mepc,x1,x31)
    pop(x1,x31)
    pop(x2,x31)
    pop(x3,x31)
    pop(x4,x31)
    pop(x5,x31)
    pop(x6,x31)
    pop(x7,x31)
    pop(x8,x31)
    pop(x9,x31)
    pop(x10,x31)
    pop(x11,x31)
    pop(x12,x31)
    pop(x13,x31)
    pop(x14,x31)
    pop(x15,x31)
    pop(x16,x31)
    pop(x17,x31)
    pop(x18,x31)
    pop(x19,x31)
    pop(x20,x31)
    pop(x21,x31)
    pop(x22,x31)
    pop(x23,x31)
    pop(x24,x31)
    pop(x25,x31)
    pop(x26,x31)
    pop(x27,x31)
    pop(x28,x31)
    pop(x29,x31)
    pop(x30,x31)
    ld x31,0(x31)
    mret

.section .data
reg_info:
    .incbin REG_STATE_BIN