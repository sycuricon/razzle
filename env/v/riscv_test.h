// See LICENSE for license details.

#ifndef _ENV_VIRTUAL_SINGLE_CORE_H
#define _ENV_VIRTUAL_SINGLE_CORE_H

#include "../p/riscv_test.h"

//-----------------------------------------------------------------------
// Begin Macro
//-----------------------------------------------------------------------

// #undef RVTEST_FP_ENABLE
// #define RVTEST_FP_ENABLE          \
//     fssr x0;                      \
//     INIT_FREG;

// #undef RVTEST_VECTOR_ENABLE
// #define RVTEST_VECTOR_ENABLE      \
//   csrwi fcsr, 0;                  \
//   csrwi vcsr, 0;

#undef RVTEST_CODE_BEGIN
#define RVTEST_CODE_BEGIN        \
  .section .text.init;           \
  .global extra_boot;            \
  extra_boot:                    \
  init;                          \
  EXTRA_INIT                     \
  ret;                           \
  .section .text;                \
  .global _fuzz_main_loop_entry; \
  .align  12;                    \
  _fuzz_main_loop_entry:

//-----------------------------------------------------------------------
// Pass/Fail Macro
//-----------------------------------------------------------------------

#undef RVTEST_PASS
#define RVTEST_PASS \
  li a0, 1;         \
  li a1, 0xdead;    \
  scall             

#undef RVTEST_FAIL
#define RVTEST_FAIL   \
  sll a0, TESTNUM, 1; \
  1 : beqz a0, 1b;    \
  or a0, a0, 1;       \
  scall;

#undef EXTRA_EXIT
#ifndef ENABLE_MULTI_ROUND
#define EXTRA_EXIT                                                      \
        li gp, 1;                                                       \
        sw gp, tohost, t5;                                              \
        j write_tohost;
#else
#define EXTRA_EXIT                                                      \
        li gp, 3;                                                       \
        sw gp, tohost, t5;                                              \
        li t0, 0x1000;                                                  \
        csrw sepc, t0;                                                  \
        sw x0, tohost, t5;                                              \
        ZJV_FUZZ_INSNRDM_CLEAN;                                         \
        ZJV_FUZZ_INSNRDM_ON;                                            \
        sret;
#endif

//-----------------------------------------------------------------------
// Data Section Macro
//-----------------------------------------------------------------------

//-----------------------------------------------------------------------
// Supervisor mode definitions and macros
//-----------------------------------------------------------------------

#define MAX_TEST_PAGES 63  // this must be the period of the LFSR below
#define LFSR_NEXT(x) (((((x) ^ ((x) >> 1)) & 1) << 5) | ((x) >> 1))

#define PGSHIFT 12
#define PGSIZE (1UL << PGSHIFT)

#define SIZEOF_TRAPFRAME_T ((__riscv_xlen / 8) * 36)

#ifndef __ASSEMBLER__

typedef unsigned long pte_t;
#define LEVELS (sizeof(pte_t) == sizeof(uint64_t) ? 3 : 2)
#define PTIDXBITS (PGSHIFT - (sizeof(pte_t) == 8 ? 3 : 2))
#define VPN_BITS (PTIDXBITS * LEVELS)
#define VA_BITS (VPN_BITS + PGSHIFT)
#define PTES_PER_PT (1UL << RISCV_PGLEVEL_BITS)
#define MEGAPAGE_SIZE (PTES_PER_PT * PGSIZE)

typedef struct {
  long gpr[32];
  long sr;
  long epc;
  long badvaddr;
  long cause;
} trapframe_t;
#endif

#endif
