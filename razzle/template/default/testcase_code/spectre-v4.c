#include <stdio.h>
#include <string.h>

#include "encoding.h"
#include "parafuzz.h"
#include "boom_conf.h"

PARAFUZZ_DEFINE;

void victim(int64_t offset) {
  INFO_VCTM_START;

  uint64_t dummy1 = 0xa234b057963aef89ul;
  uint64_t dummy2 = 0x46fea3467def0136ul;

  INFO_DELAY_START;
  asm("add  t0, zero, %[target_addr]\n"
      "add  t1, zero, %[target_addr]\n"
      "fcvt.s.lu	fa4, %[dummy1]\n"
      "fcvt.s.lu	fa5, %[dummy2]\n"
      "fdiv.s	fa5, fa5, fa4\n"
      "fdiv.s	fa5, fa5, fa4\n"
      "fdiv.s	fa5, fa5, fa4\n"
      "fdiv.s	fa5, fa5, fa4\n"
      "fdiv.s	fa5, fa5, fa4\n"
      "fdiv.s	fa5, fa5, fa4\n"
      "fcvt.lu.s	t5, fa5, rtz\n"
      "add t0, t5, t0\n"
      INFO_INLINE_ASM(ENUM_INFO_DELAY_END)
      "sd t5, 0(t0)\n"
      "ld t6, 0(t1)\n"
      INFO_INLINE_ASM(ENUM_INFO_TEXE_START)
      "add t6, t6, %[trapoline_addr]\n"
      "lbu t6, 0(t6)\n"
      "slliw t6, t6," macro_2_str(CACHE_BLOCK_SHIFT) "\n"
      "add t6, t6, %[base_addr]\n"
      "ld t6, 0(t6)\n"
      INFO_INLINE_ASM(ENUM_INFO_TEXE_END)
      :: [dummy1] "r" (dummy1),
         [dummy2] "r" (dummy2),
         [target_addr] "r" (&offset),
         [base_addr] "r" (&array[0]),
         [trapoline_addr] "r" (&trapoline)
      : "t0", "t1", "t5", "t6", "fa4", "fa5");
  
  INFO_VCTM_END;
}


int main(int argc, char* argv[]) {
  setup();
  guess = get_round_info();

  int64_t secret_offset = (unsigned char*)&secret[LEAK_TARGET] - (unsigned char*)&trapoline;

  victim(secret_offset);
  uint64_t res = access_time(&array[0], guess, 0);

  dump_channel(res, &array[0] + guess*CACHE_BLOCK);
  exit(0);
  return 0;
}

