#ifndef __PARAFUZZ_H
#define __PARAFUZZ_H

#include <stdint.h>

#include "boom_conf.h"

#define static_assert(cond) switch(0) { case 0: case !!(long)(cond): ; }

#define __STR(name) #name
#define macro_2_str(name) __STR(name)

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
    // secret is "deadbeef is a magic number that used by prarafuzz to disclose transient execution vulnerability in the processor. :P"
    #define LEAK_SECRET     {100, 101, 97, 100, 98, 101, 101, 102, 32, 105, 115, 32, 97, 32, 109, 97, 103, 105, 99, 32, 110, 117, 109, 98, 101, 114, 32, 116, 104, 97, 116, 32, 117, 115, 101, 100, 32, 98, 121, 32, 112, 114, 97, 114, 97, 102, 117, 122, 122, 32, 116, 111, 32, 100, 105, 115, 99, 108, 111, 115, 101, 32, 116, 114, 97, 110, 115, 105, 101, 110, 116, 32, 101, 120, 101, 99, 117, 116, 105, 111, 110, 32, 118, 117, 108, 110, 101, 114, 97, 98, 105, 108, 105, 116, 121, 32, 105, 110, 32, 116, 104, 101, 32, 112, 114, 111, 99, 101, 115, 115, 111, 114, 46, 32, 58, 80, 0}
#endif

#define PARAFUZZ_DEFINE \
    uint64_t guess; \
    extern uint8_t secret[]; \
    extern uint8_t trapoline[]; \
    extern uint8_t array[];
extern uint8_t _secret_start[], _secret_end[];

void init_resetmanager();
uint64_t get_round_info();

void setup();
void exit(int code);
void dump_channel(uint64_t time, uint8_t* addr);
void next_round();

uint64_t access_time(uint8_t* base, int index, int offset);

extern void disable_fs();

void setup_pmp();

#define INFO_INLINE_ASM(x)          "slti zero, zero, " macro_2_str(x) "\n"
#define ENUM_INFO_VCTM_START        0
#define ENUM_INFO_VCTM_END          1
#define ENUM_INFO_DELAY_START       2
#define ENUM_INFO_DELAY_END         3
#define ENUM_INFO_TEXE_START        4
#define ENUM_INFO_TEXE_END          5
#define ENUM_INFO_LEAK_START        6
#define ENUM_INFO_LEAK_END          7

#define INFO_VCTM_START     asm("slti zero, zero, " macro_2_str(ENUM_INFO_VCTM_START)     "\n");   // 0x00002013
#define INFO_VCTM_END       asm("fence\nslti zero, zero, " macro_2_str(ENUM_INFO_VCTM_END)"\n");   // 0x00102013
#define INFO_DELAY_START    asm("slti zero, zero, " macro_2_str(ENUM_INFO_DELAY_START)    "\n");   // 0x00202013
#define INFO_DELAY_END      asm("slti zero, zero, " macro_2_str(ENUM_INFO_DELAY_END)      "\n");   // 0x00302013
#define INFO_TEXE_START     asm("slti zero, zero, " macro_2_str(ENUM_INFO_TEXE_START)     "\n");   // 0x00402013
#define INFO_TEXE_END       asm("slti zero, zero, " macro_2_str(ENUM_INFO_TEXE_END)       "\n");   // 0x00502013
#define INFO_LEAK_START     asm("slti zero, zero, " macro_2_str(ENUM_INFO_LEAK_START)     "\n");   // 0x00602013
#define INFO_LEAK_END       asm("slti zero, zero, " macro_2_str(ENUM_INFO_LEAK_END)       "\n");   // 0x00702013
#define INFO_CONTROL_LEAK   asm volatile(                           \
                                "csrr t0, cycle\n"                  \
                                "csrw 0x800, %[default_mode]\n"     \
                                "csrw 0x800, t0\n"                  \
                                :: [default_mode] "r" ((CMD_SWITCH_STATE | STATE_DEFAULT)));

#endif //__PARAFUZZ_H
