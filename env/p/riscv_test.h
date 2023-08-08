// See LICENSE for license details.

#ifndef _ENV_PHYSICAL_SINGLE_CORE_H
#define _ENV_PHYSICAL_SINGLE_CORE_H

#include "../encoding.h"
#include "../fuzzing.h"

//-----------------------------------------------------------------------
// Begin Macro
//-----------------------------------------------------------------------

#define RVTEST_RV64U                                                    \
  .macro init;                                                          \
  .endm

#define RVTEST_RV64UF                                                   \
  .macro init;                                                          \
  RVTEST_FP_ENABLE;                                                     \
  .endm

#define RVTEST_RV64VU                                                   \
  .macro init;                                                          \
  RVTEST_ENABLE_HYPERVISOR;                                             \
  .endm

#define RVTEST_RV64VUF                                                  \
  .macro init;                                                          \
  RVTEST_ENABLE_HYPERVISOR;                                             \
  RVTEST_VFP_ENABLE                                                     \
  RVTEST_FP_ENABLE;                                                     \
  .endm

#define RVTEST_RV64UV                                                   \
  .macro init;                                                          \
  RVTEST_VECTOR_ENABLE;                                                 \
  .endm

#define RVTEST_RV32U                                                    \
  .macro init;                                                          \
  .endm

#define RVTEST_RV32UF                                                   \
  .macro init;                                                          \
  RVTEST_FP_ENABLE;                                                     \
  .endm

#define RVTEST_RV32UV                                                   \
  .macro init;                                                          \
  RVTEST_VECTOR_ENABLE;                                                 \
  .endm

#define RVTEST_RV64M                                                    \
  .macro init;                                                          \
  RVTEST_ENABLE_MACHINE;                                                \
  .endm

#define RVTEST_RV64MF                                                   \
  .macro init;                                                          \
  RVTEST_ENABLE_MACHINE;                                                \
  RVTEST_FP_ENABLE;                                                     \
  .endm

#define RVTEST_RV64S                                                    \
  .macro init;                                                          \
  RVTEST_ENABLE_SUPERVISOR;                                             \
  .endm

#define RVTEST_RV64SF                                                   \
  .macro init;                                                          \
  RVTEST_ENABLE_SUPERVISOR;                                             \
  RVTEST_FP_ENABLE;                                                     \
  .endm

#define RVTEST_RV64VS                                                   \
  .macro init;                                                          \
  RVTEST_ENABLE_SUPERVISOR;                                             \
  RVTEST_ENABLE_HYPERVISOR;                                             \
  .endm

#define RVTEST_RV64VSF                                                  \
  .macro init;                                                          \
  RVTEST_ENABLE_SUPERVISOR;                                             \
  RVTEST_ENABLE_HYPERVISOR;                                             \
  RVTEST_VFP_ENABLE                                                     \
  RVTEST_FP_ENABLE;                                                     \
  .endm


#define RVTEST_RV32M                                                    \
  .macro init;                                                          \
  RVTEST_ENABLE_MACHINE;                                                \
  .endm

#define RVTEST_RV32MF                                                   \
  .macro init;                                                          \
  RVTEST_ENABLE_MACHINE;                                                \
  RVTEST_FP_ENABLE;                                                     \
  .endm

#define RVTEST_RV32S                                                    \
  .macro init;                                                          \
  RVTEST_ENABLE_SUPERVISOR;                                             \
  .endm

#define RVTEST_RV32SF                                                   \
  .macro init;                                                          \
  RVTEST_ENABLE_SUPERVISOR;                                             \
  RVTEST_FP_ENABLE;                                                     \
  .endm

#if __riscv_xlen == 64
# define CHECK_XLEN li a0, 1; slli a0, a0, 31; bgez a0, 1f; RVTEST_PASS; 1:
#else
# define CHECK_XLEN li a0, 1; slli a0, a0, 31; bltz a0, 1f; RVTEST_PASS; 1:
#endif


#if __riscv_xlen == 64
# define FMV__X    fmv.d.x
#else
# define FMV__X    fmv.w.x
#endif

#define INIT_XREG                                                       \
  li x1, 0;                                                             \
  li x2, 0;                                                             \
  li x3, 0;                                                             \
  li x4, 0;                                                             \
  li x5, 0;                                                             \
  li x6, 0;                                                             \
  li x7, 0;                                                             \
  li x8, 0;                                                             \
  li x9, 0;                                                             \
  li x10, 0;                                                            \
  li x11, 0;                                                            \
  li x12, 0;                                                            \
  li x13, 0;                                                            \
  li x14, 0;                                                            \
  li x15, 0;                                                            \
  li x16, 0;                                                            \
  li x17, 0;                                                            \
  li x18, 0;                                                            \
  li x19, 0;                                                            \
  li x20, 0;                                                            \
  li x21, 0;                                                            \
  li x22, 0;                                                            \
  li x23, 0;                                                            \
  li x24, 0;                                                            \
  li x25, 0;                                                            \
  li x26, 0;                                                            \
  li x27, 0;                                                            \
  li x28, 0;                                                            \
  li x29, 0;                                                            \
  li x30, 0;                                                            \
  li x31, 0;

#define INIT_FREG                                                       \
  FMV__X f0, x0;                                                        \
  FMV__X f1, x0;                                                        \
  FMV__X f2, x0;                                                        \
  FMV__X f3, x0;                                                        \
  FMV__X f4, x0;                                                        \
  FMV__X f5, x0;                                                        \
  FMV__X f6, x0;                                                        \
  FMV__X f7, x0;                                                        \
  FMV__X f8, x0;                                                        \
  FMV__X f9, x0;                                                        \
  FMV__X f10, x0;                                                        \
  FMV__X f11, x0;                                                        \
  FMV__X f12, x0;                                                        \
  FMV__X f13, x0;                                                        \
  FMV__X f14, x0;                                                        \
  FMV__X f15, x0;                                                        \
  FMV__X f16, x0;                                                        \
  FMV__X f17, x0;                                                        \
  FMV__X f18, x0;                                                        \
  FMV__X f19, x0;                                                        \
  FMV__X f20, x0;                                                        \
  FMV__X f21, x0;                                                        \
  FMV__X f22, x0;                                                        \
  FMV__X f23, x0;                                                        \
  FMV__X f24, x0;                                                        \
  FMV__X f25, x0;                                                        \
  FMV__X f26, x0;                                                        \
  FMV__X f27, x0;                                                        \
  FMV__X f28, x0;                                                        \
  FMV__X f29, x0;                                                        \
  FMV__X f30, x0;                                                        \
  FMV__X f31, x0;


#define INIT_PMP                                                        \
  la t0, 1f;                                                            \
  csrrw t1, mtvec, t0;                                                  \
  /* Set up a PMP to protect magic device */                            \
  li t0, (1 << 29);                                                     \
  csrw pmpaddr0, t0;                                                    \
  li t0, PMP_L | PMP_TOR | PMP_R;                                       \
  csrw pmpcfg0, t0;                                                     \
  la t0, _fuzz_main_loop_exit;                                          \
  srli t0, t0, 2;                                                       \
  csrw pmpaddr1, t0;                                                    \
  li t0, (PMP_L | PMP_TOR | PMP_R | PMP_X) << 8;                        \
  csrs pmpcfg0, t0;                                                     \
  /* Set up a PMP to permit all accesses */                             \
  li t0, (1 << (31 + (__riscv_xlen / 64) * (53 - 31))) - 1;             \
  csrw pmpaddr7, t0;                                                    \
  li t0, (PMP_L | PMP_NAPOT | PMP_R | PMP_W) << 56;                     \
  csrs pmpcfg0, t0;                                                     \
  csrr t0, pmpcfg0;                                                     \
  .align 2;                                                             \
1:                                                                      \
  csrw mtvec, t1;

#define INIT_SATP                                                      \
  la t0, 1f;                                                            \
  csrw mtvec, t0;                                                       \
  csrwi satp, 0;                                                       \
  .align 2;                                                             \
1:

#define DELEGATE_NO_TRAPS                                               \
  csrwi mie, 0;                                                         \
  la t0, 1f;                                                            \
  csrw mtvec, t0;                                                       \
  csrwi medeleg, 0;                                                     \
  csrwi mideleg, 0;                                                     \
  .align 2;                                                             \
1:

#define RVTEST_ENABLE_SUPERVISOR                                        \
  li a0, MSTATUS_MPP & (MSTATUS_MPP >> 1);                              \
  csrs mstatus, a0;                                                     \
  li a0, SIP_SSIP | SIP_STIP;                                           \
  csrs mideleg, a0;                                                     \

#define RVTEST_ENABLE_MACHINE                                           \
  li a0, MSTATUS_MPP;                                                   \
  csrs mstatus, a0;                                                     \

#define RVTEST_FP_ENABLE                                                \
  li a0, MSTATUS_FS & (MSTATUS_FS >> 1);                                \
  csrs mstatus, a0;                                                     \
  csrwi fcsr, 0;                                                        \
  INIT_FREG;

#define RVTEST_VFP_ENABLE                                               \
  li a0, MSTATUS_FS & (MSTATUS_FS >> 1);                                \
  csrs vsstatus, a0;                                                    \

#define RVTEST_VECTOR_ENABLE                                            \
  li a0, (MSTATUS_VS & (MSTATUS_VS >> 1)) |                             \
         (MSTATUS_FS & (MSTATUS_FS >> 1));                              \
  csrs mstatus, a0;                                                     \
  csrwi fcsr, 0;                                                        \
  csrwi vcsr, 0;

#define RISCV_MULTICORE_DISABLE                                         \
  csrr a0, mhartid;                                                     \
  1: bnez a0, 1b
  

#define EXTRA_TVEC_USER
#define EXTRA_TVEC_MACHINE
#define EXTRA_INIT                                                      \
        csrw mip, x0;                                                   \
        li a0, MIP_MSIP;                                                \
        csrs mie, a0;                                                   \
        li a0, MSTATUS_MIE | MSTATUS_MPIE;                              \
        csrs mstatus, a0;

#ifndef ENABLE_MULTI_ROUND
#define EXTRA_EXIT                                                      \
        li gp, 1;                                                       \
        sw TESTNUM, tohost, t5;                                         \
        j write_tohost;
#else
#define EXTRA_EXIT                                                      \
        li gp, 3;                                                       \
        sw gp, tohost, t5;                                              \
        la t0, _fuzz_main_loop_entry;                                   \
        csrw mepc, t0;                                                  \
        sw x0, tohost, t5;                                              \
        ZJV_FUZZ_INSNRDM_CLEAN;                                         \
        ZJV_FUZZ_INSNRDM_ON;                                            \
        mret;
#endif

#define EXTRA_INIT_TIMER
#ifndef ENABLE_MULTI_ROUND
#define INTERRUPT_HANDLER                                               \
        li gp, 1;                                                       \
        sw TESTNUM, tohost, t5;                                         \
        j write_tohost;
#else
#define INTERRUPT_HANDLER                                               \
        li gp, 3;                                                       \
        sw gp, tohost, t5;                                              \
        ld t0, MAGIC_RDM_TEXT_ADDR(x0);                                 \
        csrw mepc, t0;                                                  \
        sw x0, tohost, t5;                                              \
        ZJV_FUZZ_INSNRDM_CLEAN;                                         \
        ZJV_FUZZ_INSNRDM_ON;                                            \
        mret;
#endif

#define RVTEST_CODE_BEGIN                                               \
        .section .text.init;                                            \
        .align  6;                                                      \
        .weak stvec_handler;                                            \
        .weak mtvec_handler;                                            \
        .globl _start;                                                  \
_start:                                                                 \
        /* reset vector */                                              \
        ZJV_FUZZ_INSNRDM_OFF;                                           \
        j reset_vector;                                                 \
        .align 2;                                                       \
trap_vector:                                                            \
        .align 2;                                                       \
        .option push;                                                   \
        .option norvc;                                                  \
        /* test whether the test came from pass/fail */                 \
        csrr t5, mtval;                                                 \
        csrr t5, mcause;                                                \
        li t0, 0xdead;                                                  \
        bne a1, t0, trap_vector_no_check;                               \
        li t6, CAUSE_USER_ECALL;                                        \
        beq t5, t6, write_tohost;                                       \
        li t6, CAUSE_SUPERVISOR_ECALL;                                  \
        beq t5, t6, write_tohost;                                       \
        li t6, CAUSE_MACHINE_ECALL;                                     \
        beq t5, t6, write_tohost;                                       \
        li t6, CAUSE_HYPERVISOR_ECALL;                                  \
        beq t5, t6, write_tohost;                                       \
trap_vector_no_check:                                                   \
        /* was it an interrupt or an exception? */                      \
        bgez t5, handle_exception;                                      \
        INTERRUPT_HANDLER;                                              \
handle_exception:                                                       \
        /* if an mtvec_handler is defined, jump to it */                \
        la t5, mtvec_handler;                                           \
        jr t5;                                                          \
                                                                        \
write_tohost:                                                           \
        EXTRA_EXIT;                                                     \
reset_vector:                                                           \
        INIT_XREG;                                                      \
        RISCV_MULTICORE_DISABLE;                                        \
        INIT_SATP;                                                      \
        INIT_PMP;                                                       \
        DELEGATE_NO_TRAPS;                                              \
        li TESTNUM, 0;                                                  \
        la t0, trap_vector;                                             \
        csrw mtvec, t0;                                                 \
        CHECK_XLEN;                                                     \
        /* if an stvec_handler is defined, delegate exceptions to it */ \
        la t0, stvec_handler;                                           \
        beqz t0, 1f;                                                    \
        csrw stvec, t0;                                                 \
        li t0, (1 << CAUSE_LOAD_PAGE_FAULT) |                           \
               (1 << CAUSE_STORE_PAGE_FAULT) |                          \
               (1 << CAUSE_FETCH_PAGE_FAULT) |                          \
               (1 << CAUSE_MISALIGNED_FETCH) |                          \
               (1 << CAUSE_BREAKPOINT);                                 \
        csrw medeleg, t0;                                               \
1:      csrwi mstatus, 0;                                               \
        init;                                                           \
        EXTRA_INIT;                                                     \
        EXTRA_INIT_TIMER;                                               \
        la t0, _fuzz_main_loop_entry;                                   \
        csrw mepc, t0;                                                  \
        csrr a0, mhartid;                                               \
        .option pop;                                                    \
        ZJV_FUZZ_INSNRDM_CLEAN;                                         \
        ZJV_FUZZ_INSNRDM_ON;                                            \
        mret;                                                           \
                                                                        \
        .section .text;                                                 \
        .align  12;                                                     \
_fuzz_main_loop_entry:

//-----------------------------------------------------------------------
// End Macro
//-----------------------------------------------------------------------

#define RVTEST_CODE_END                                                 \
.section .text;                                                         \
.globl _fuzz_main_loop_exit;                                            \
.align 4;                                                               \
_fuzz_main_loop_exit:                                                   \
        unimp;

//-----------------------------------------------------------------------
// Pass/Fail Macro
//-----------------------------------------------------------------------

#define RVTEST_PASS                                                     \
        fence;                                                          \
        li TESTNUM, 1;                                                  \
        li a7, 93;                                                      \
        li a0, 0;                                                       \
        li a1, 0xdead;                                                  \
        ecall

#define TESTNUM gp
#define RVTEST_FAIL                                                     \
        fence;                                                          \
1:      beqz TESTNUM, 1b;                                               \
        sll TESTNUM, TESTNUM, 1;                                        \
        or TESTNUM, TESTNUM, 1;                                         \
        li a7, 93;                                                      \
        addi a0, TESTNUM, 0;                                            \
        ecall

//-----------------------------------------------------------------------
// Data Section Macro
//-----------------------------------------------------------------------

#define EXTRA_DATA

#define RVTEST_DATA_BEGIN                                               \
        EXTRA_DATA                                                      \
        .pushsection .tohost,"aw",@progbits;                            \
        .align 6; .global tohost; tohost: .dword 0;                     \
        .align 6; .global fromhost; fromhost: .dword 0;                 \
        .popsection;                                                    \
        .section .data;                                                 \
        .align 4; .global _fuzz_data_start; _fuzz_data_start:

#define RVTEST_DATA_END                                                 \
        .align 4; .global _fuzz_data_end; _fuzz_data_end:

#define PT_BASES    \
    .weak pt0;      \
    .weak pt1;      \
    .weak pt2;      \
    .weak pt3;      \
pt0:                \
pt1:                \
pt2:                \
pt3:   


#ifdef ENABLE_HYPERVISOR
#define RVTEST_ENABLE_HYPERVISOR    \
    li t1, 1 << 39;                 \
    csrs mstatus, t1;
#else
#define RVTEST_ENABLE_HYPERVISOR    \
    nop
#endif



#endif
