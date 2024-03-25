#ifndef _ZJV_FUZZING_MACRO_H
#define _ZJV_FUZZING_MACRO_H

#include "magic_device.h"

#ifdef __ASSEMBLER__

    #if __riscv_xlen == 64
    # define STORE    sd
    # define LOAD     ld
    #else
    # define STORE    sw
    # define LOAD     lw
    #endif

// TODO: pipeline depth parameter
    #ifdef ENABLE_MAGIC_MASKER
        #define ZJV_FUZZ_INSNRDM_CLEAN                                          \
                slti x0, x0, 1;                                                 \
                slti x0, x0, 2;                                                 \
                slti x0, x0, 2;                                                 \
                slti x0, x0, 2;                                                 \
                slti x0, x0, 2;
        #define ZJV_FUZZ_INSNRDM_ON                                             \
                slti x0, x0, 0;                                                 \
                slti x0, x0, 2;                                                 \
                slti x0, x0, 2;                                                 \
                slti x0, x0, 2;                                                 \
                slti x0, x0, 2;
        #define ZJV_FUZZ_INSNRDM_OFF                                            \
                slti x0, x0, -1;                                                \
                slti x0, x0, 2;                                                 \
                slti x0, x0, 2;                                                 \
                slti x0, x0, 2;                                                 \
                slti x0, x0, 2;
    #else
        #define ZJV_FUZZ_INSNRDM_CLEAN  nop;
        #define ZJV_FUZZ_INSNRDM_ON     nop;
        #define ZJV_FUZZ_INSNRDM_OFF    nop;
    #endif

    #ifdef ENABLE_MAGIC_DEVICE
        #define MAGIC_JUMP(rs1, rs2)                                            \
            LOAD rs1, MAGIC_RDM_TEXT_ADDR(zero);                                \
            jalr rs2, rs1, 0;
        #define MAGIC_LI(instr, rd, imm, value)     instr rd, imm(zero);
        #define MAGIC_LI_S(instr, rd, imm, value)   instr rd, imm(zero);
        #define MAGIC_LI_D(instr, rd, imm, value)   instr rd, imm(zero);
        #define MAGIC_LA(instr, rd, imm, value)     instr rd, imm(zero);
    #else
        #define MAGIC_JUMP(rs1, rs2)                nop;
        #define MAGIC_LI(instr, rd, imm, value)     li rd, value;
        #define MAGIC_LI_S(instr, rd, imm, value)                               \
            li t0, value;                                                       \
            fcvt.s.wu rd, t0;
        #define MAGIC_LI_D(instr, rd, imm, value)                               \
            li t0, value;                                                       \
            fcvt.d.lu rd, t0;
        #define MAGIC_LA(instr, rd, imm, value)     la rd, value;
    #endif

#else /* not define __ASSEMBLER__ */

    #if __riscv_xlen == 64
        #define MAGIC_ACCESS(__v, offset) __asm__ __volatile__ ("ld %0, %1(zero)" : "=r" (__v) : "I" (offset));
    #else
        #define MAGIC_ACCESS(__v, offset) __asm__ __volatile__ ("lw %0, %1(zero)" : "=r" (__v) : "I" (offset));
    #endif

#endif /* __ASSEMBLER__ */

#endif /* _ZJV_FUZZING_MACRO_H */