#define pop(a0,a1,imm) \
    ld a0, (imm*8)(a1);
#define pop_csr(csr,a0,a1,imm) \
    ld a0, (imm*8)(a1); \
    csrw csr, a0
#define CMD_POWER_OFF           0xAF1B608E883B0000ul
#define PROBEBUF                0x800

.section .text
.global _start
_start:
    la x31,reg_info
    pop_csr(stvec,x1,x31,0)
    pop_csr(scounteren,x1,x31,1)
    pop_csr(sscratch,x1,x31,2)
    pop_csr(satp,x1,x31,3)
    pop_csr(misa,x1,x31,4)
    pop_csr(medeleg,x1,x31,5)
    pop_csr(mideleg,x1,x31,6)
    pop_csr(mie,x1,x31,7)
    pop_csr(mtvec,x1,x31,8)
    pop_csr(mcounteren,x1,x31,9)
    pop_csr(pmpcfg0,x1,x31,10)
    pop_csr(pmpcfg2,x1,x31,11)
    pop_csr(pmpaddr0,x1,x31,12)
    pop_csr(pmpaddr1,x1,x31,13)
    pop_csr(pmpaddr2,x1,x31,14)
    pop_csr(pmpaddr3,x1,x31,15)
    pop_csr(pmpaddr4,x1,x31,16)
    pop_csr(pmpaddr5,x1,x31,17)
    pop_csr(pmpaddr6,x1,x31,18)
    pop_csr(pmpaddr7,x1,x31,19)
    pop_csr(pmpaddr8,x1,x31,20)
    pop_csr(pmpaddr9,x1,x31,21)
    pop_csr(pmpaddr10,x1,x31,22)
    pop_csr(pmpaddr11,x1,x31,23)
    pop_csr(pmpaddr12,x1,x31,24)
    pop_csr(pmpaddr13,x1,x31,25)
    pop_csr(pmpaddr14,x1,x31,26)
    pop_csr(pmpaddr15,x1,x31,27)
    pop_csr(mstatus,x1,x31,28)
    pop_csr(mepc,x1,x31,29)
    pop(x1,x31,30)
    pop(x2,x31,31)
    pop(x3,x31,32)
    pop(x4,x31,33)
    pop(x5,x31,34)
    pop(x6,x31,35)
    pop(x7,x31,36)
    pop(x8,x31,37)
    pop(x9,x31,38)
    pop(x10,x31,39)
    pop(x11,x31,40)
    pop(x12,x31,41)
    pop(x13,x31,42)
    pop(x14,x31,43)
    pop(x15,x31,44)
    pop(x16,x31,45)
    pop(x17,x31,46)
    pop(x18,x31,47)
    pop(x19,x31,48)
    pop(x20,x31,49)
    pop(x21,x31,50)
    pop(x22,x31,51)
    pop(x23,x31,52)
    pop(x24,x31,53)
    pop(x25,x31,54)
    pop(x26,x31,55)
    pop(x27,x31,56)
    pop(x28,x31,57)
    pop(x29,x31,58)
    pop(x30,x31,59)
    pop(x31,x31,60)
    mret

stop_handler:
    li t0,CMD_POWER_OFF
    csrw PROBEBUF,t0

.section .data
reg_info:
    .incbin REG_STATE_BIN