#include "parafuzz.h"

uint64_t current_round = 0;
volatile uint64_t *state_ptr = (uint64_t *)0x4000;
volatile uint64_t *reset_ptr = (uint64_t *)0x4008;

extern char secret[];

void init_resetmanager() {
  current_round = get_round_info();
  if (current_round == 0) {
    *state_ptr = GUESS_START;
  }
  current_round = *state_ptr;
}

void setup() {
  current_round = GUESS_TARGET;
}

uint64_t get_round_info() {
  return current_round;
}

void dump_channel(uint64_t time, uint8_t* addr) {
  asm volatile(
    "csrw 0x800, %[ptr_mode]\n"
    "csrw 0x800, %[addr]\n"
    "csrw 0x800, %[num_mode]\n"
    "csrw 0x800, %[guess]\n"
    "csrw 0x800, %[time]\n"
    "csrw 0x800, %[char_mode]\n"
    "csrw 0x800, %[done]\n"
    : :
      [num_mode] "r" ((CMD_SWITCH_STATE | STATE_DUMP_NUM)), 
      [ptr_mode] "r" ((CMD_SWITCH_STATE | STATE_DUMP_ADDR)),
      [char_mode] "r" ((CMD_SWITCH_STATE | STATE_DUMP_CHAR)),
      [time] "r" (time),
      [guess] "r" (current_round),
      [addr] "r" (addr),
      [done] "r" ('\n')
  );
}

void next_round() {
  if (current_round >= GUESS_END) {
    // asm volatile(
    //   "csrw 0x800, %[default_mode]\n"
    //   "csrw 0x800, %[secret]\n"
    //   : :
    //     [default_mode] "r" ((CMD_SWITCH_STATE | STATE_DEFAULT)), 
    //     [secret] "r" (secret[LEAK_TARGET])
    // );
    exit(0);
  } else {
    *state_ptr = *state_ptr + 1;
    *reset_ptr = 50;
  }
}

void exit(int code) {
  asm volatile(
    "csrw 0x800, %[stop]\n"
    : :
      [stop] "r" (CMD_POWER_OFF | code)
  );

  __builtin_unreachable();
}

void setup_pmp() {
  uintptr_t cfg0, addr0;
  addr0 = ((uintptr_t) _secret_start | ((0x1000 - 1)>>1)) >> 2;
  write_csr(pmpaddr0, addr0);
  cfg0 = PMP_NAPOT | PMP_L;
  write_csr(pmpcfg0, cfg0);
}
