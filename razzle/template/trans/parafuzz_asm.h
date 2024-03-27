#ifndef __PARAFUZZ_H
#define __PARAFUZZ_H

#include "boom_conf_asm.h"

#define CMD_SWITCH_STATE    0xAF1B608E883A0000ul
#define STATE_DEFAULT       0
#define STATE_DUMP_NUM      1
#define STATE_DUMP_CHAR     2
#define STATE_DUMP_ADDR     3

#define CMD_POWER_OFF       0xAF1B608E883B0000ul

// deprecated
#define GUESS_START         100
#define GUESS_END           105

#ifndef PARAFUZZ_PREDEFINE
    #define GUESS_TARGET    101
    #define LEAK_TARGET     1
#endif

#define ENUM_INFO_VCTM_START        0
#define ENUM_INFO_VCTM_END          1
#define ENUM_INFO_DELAY_START       2
#define ENUM_INFO_DELAY_END         3
#define ENUM_INFO_TEXE_START        4
#define ENUM_INFO_TEXE_END          5
#define ENUM_INFO_LEAK_START        6
#define ENUM_INFO_LEAK_END          7
#define ENUM_INFO_INIT_START        8
#define ENUM_INFO_INIT_END          9
#define ENUM_INFO_BIM_START         10
#define ENUM_INFO_BIM_END           11
#define ENUM_INFO_TRAIN_START       12
#define ENUM_INFO_TRAIN_END         13

#define INFO_VCTM_START     slti zero, zero, ENUM_INFO_VCTM_START
#define INFO_VCTM_END       fence; slti zero, zero, ENUM_INFO_VCTM_END
#define INFO_DELAY_START    slti zero, zero, ENUM_INFO_DELAY_START
#define INFO_DELAY_END      slti zero, zero, ENUM_INFO_DELAY_END
#define INFO_TEXE_START     slti zero, zero, ENUM_INFO_TEXE_START
#define INFO_TEXE_END       slti zero, zero, ENUM_INFO_TEXE_END
#define INFO_LEAK_START     slti zero, zero, ENUM_INFO_LEAK_START
#define INFO_LEAK_END       slti zero, zero, ENUM_INFO_LEAK_END
#define INFO_INIT_START     slti zero, zero, ENUM_INFO_INIT_START
#define INFO_INIT_END       slti zero, zero, ENUM_INFO_INIT_END
#define INFO_BIM_START      slti zero, zero, ENUM_INFO_BIM_START
#define INFO_BIM_END        slti zero, zero, ENUM_INFO_BIM_END
#define INFO_TRAIN_START    slti zero, zero, ENUM_INFO_TRAIN_START
#define INFO_TRAIN_END      slti zero, zero, ENUM_INFO_TRAIN_END
#define INFO_CONTROL_LEAK   csrr t0, cycle;\
                            li t1, CMD_SWITCH_STATE | STATE_DEFAULT;\
                            csrw 0x800, t1;\
                            csrw 0x800, t0   

#endif //__PARAFUZZ_H
