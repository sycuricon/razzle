#include "riscv_test.h"

#if __riscv_xlen == 64
# define STORE    sd
# define LOAD     ld
# define REGBYTES 8
#else
# define STORE    sw
# define LOAD     lw
# define REGBYTES 4
#endif

#define STACK_TOP (_end + 4096)

  .section ".text.init","ax",@progbits
  .globl _start
  .align 2
_start:
  j handle_reset

  /* NMI vector */
  .align 2
nmi_vector:
1:
  li gp, 1
  sw gp, tohost, t5
  j 1b

  .align 2
handler_machine:
  csrrw sp, mscratch, sp
  STORE  x1,1*REGBYTES(sp)
  
  STORE  x3,3*REGBYTES(sp)
  STORE  x4,4*REGBYTES(sp)
  STORE  x5,5*REGBYTES(sp)
  STORE  x6,6*REGBYTES(sp)
  STORE  x7,7*REGBYTES(sp)
  STORE  x8,8*REGBYTES(sp)
  STORE  x9,9*REGBYTES(sp)
  STORE  x10,10*REGBYTES(sp)
  STORE  x11,11*REGBYTES(sp)
  STORE  x12,12*REGBYTES(sp)
  STORE  x13,13*REGBYTES(sp)
  STORE  x14,14*REGBYTES(sp)
  STORE  x15,15*REGBYTES(sp)
  STORE  x16,16*REGBYTES(sp)
  STORE  x17,17*REGBYTES(sp)
  STORE  x18,18*REGBYTES(sp)
  STORE  x19,19*REGBYTES(sp)
  STORE  x20,20*REGBYTES(sp)
  STORE  x21,21*REGBYTES(sp)
  STORE  x22,22*REGBYTES(sp)
  STORE  x23,23*REGBYTES(sp)
  STORE  x24,24*REGBYTES(sp)
  STORE  x25,25*REGBYTES(sp)
  STORE  x26,26*REGBYTES(sp)
  STORE  x27,27*REGBYTES(sp)
  STORE  x28,28*REGBYTES(sp)
  STORE  x29,29*REGBYTES(sp)
  STORE  x30,30*REGBYTES(sp)
  STORE  x31,31*REGBYTES(sp)

  csrr t0, mscratch
  STORE  t0,2*REGBYTES(sp)
  
  csrw mscratch, sp

  csrr a1, mcause
  bltz a1, interrupt_handler
  csrr a0, mepc
  csrr a2, mtval
  call handle_trap
  csrw mepc, a0

  csrr sp, mscratch
  LOAD  x1,1*REGBYTES(sp)
  LOAD  x3,3*REGBYTES(sp)
  LOAD  x4,4*REGBYTES(sp)
  LOAD  x5,5*REGBYTES(sp)
  LOAD  x6,6*REGBYTES(sp)
  LOAD  x7,7*REGBYTES(sp)
  LOAD  x8,8*REGBYTES(sp)
  LOAD  x9,9*REGBYTES(sp)
  LOAD  x10,10*REGBYTES(sp)
  LOAD  x11,11*REGBYTES(sp)
  LOAD  x12,12*REGBYTES(sp)
  LOAD  x13,13*REGBYTES(sp)
  LOAD  x14,14*REGBYTES(sp)
  LOAD  x15,15*REGBYTES(sp)
  LOAD  x16,16*REGBYTES(sp)
  LOAD  x17,17*REGBYTES(sp)
  LOAD  x18,18*REGBYTES(sp)
  LOAD  x19,19*REGBYTES(sp)
  LOAD  x20,20*REGBYTES(sp)
  LOAD  x21,21*REGBYTES(sp)
  LOAD  x22,22*REGBYTES(sp)
  LOAD  x23,23*REGBYTES(sp)
  LOAD  x24,24*REGBYTES(sp)
  LOAD  x25,25*REGBYTES(sp)
  LOAD  x26,26*REGBYTES(sp)
  LOAD  x27,27*REGBYTES(sp)
  LOAD  x28,28*REGBYTES(sp)
  LOAD  x29,29*REGBYTES(sp)
  LOAD  x30,30*REGBYTES(sp)
  LOAD  x31,31*REGBYTES(sp)
  LOAD  x2,2*REGBYTES(sp)
  ZJV_FUZZ_INSNRDM_CLEAN
  mret


interrupt_handler:
  li gp, 3;
  sw gp, tohost, t5;
  ld t0, MAGIC_RDM_TEXT_ADDR(x0);
  csrw mepc, t0;
  sw x0, tohost, t5;
  li t0, MSTATUS_MPP;
  csrc mstatus, t0;
  ZJV_FUZZ_INSNRDM_CLEAN;
  ZJV_FUZZ_INSNRDM_ON;
  mret;



handle_reset:
  ZJV_FUZZ_INSNRDM_OFF
  li x1, 0
  li x2, 0
  li x3, 0
  li x4, 0
  li x5, 0
  li x6, 0
  li x7, 0
  li x8, 0
  li x9, 0
  li x10, 0
  li x11, 0
  li x12, 0
  li x13, 0
  li x14, 0
  li x15, 0
  li x16, 0
  li x17, 0
  li x18, 0
  li x19, 0
  li x20, 0
  li x21, 0
  li x22, 0
  li x23, 0
  li x24, 0
  li x25, 0
  li x26, 0
  li x27, 0
  li x28, 0
  li x29, 0
  li x30, 0
  li x31, 0

  la t0, handler_machine
  csrw mtvec, t0
  la sp, STACK_TOP - SIZEOF_TRAPFRAME_T
  csrr t0, mhartid
  slli t0, t0, 12
  add sp, sp, t0
  csrw mscratch, sp
  call extra_boot
  INIT_PMP
  la a0, _fuzz_main_loop_entry
  la a1, _fuzz_data_start
  la a2, _fuzz_data_end
  j vm_boot

  .global  handler_super
  .align 2
  .option push
  .option norvc
handler_super:
  csrr t5, scause
  li t0, 0xdead
  bne a1, t0, trap_vector_no_check
  li t6, CAUSE_USER_ECALL
  beq t5, t6, write_tohost
  li t6, CAUSE_SUPERVISOR_ECALL
  beq t5, t6, write_tohost
  li t6, CAUSE_MACHINE_ECALL
  beq t5, t6, write_tohost
trap_vector_no_check:
  csrr t0, stval;
  csrr t0, sepc;
#ifndef ENABLE_MAGIC_DEVICE
  lh   t1, 0(t0);
  andi t1, t1, 3;
  li   t2, 3;
  bne  t1, t2, stvec_handler_add_2;
stvec_handler_add_4:
  addi t0, t0, 4;
  csrw sepc, t0;
  sret;
stvec_handler_add_2:
  addi t0, t0, 2;
  csrw sepc, t0;
  sret;
#else
  ld t0, MAGIC_SEPC_NEXT(x0);
  csrw sepc, t0;
#ifdef ZJV_PTE_RDM
  mv a0, t0
  call handle_fault
#endif
  ZJV_FUZZ_INSNRDM_CLEAN;
  sret;
#endif
write_tohost:
  EXTRA_EXIT
.option pop


  .globl  exit_super
exit_super:
  csrw sepc, a0
  ZJV_FUZZ_INSNRDM_CLEAN;
  ZJV_FUZZ_INSNRDM_ON;
  sret