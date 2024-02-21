#include <stdio.h>
#include <string.h>

#include "util.h"
#include "encoding.h"
#include "parafuzz.h"
#include "boom_conf.h"

PARAFUZZ_DEFINE;

void victim(int64_t offset) {
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
      : [dummy2] "+r" (dummy2)
      : [dummy1] "r" (dummy1)
      : "fa4", "fa5");
  INFO_DELAY_END;

  if (dummy1 < dummy2) {
    INFO_TEXE_START;
    uint8_t secret = trapoline[offset];
    if (secret == guess) {
      asm("fcvt.s.lu ft0, %0\n"
          "fdiv.s ft0, ft0, ft0\n"
          "fdiv.s ft0, ft0, ft0\n"
          :: "r" (dummy1));
    }
    INFO_TEXE_END;
  }
  INFO_VCTM_END;
}

int main(int argc, char* argv[] ) {
  setup();
  guess = get_round_info();

  int64_t secret_offset = (unsigned char*)&secret[LEAK_TARGET] - (unsigned char*)&trapoline;
  INFO_LEAK_START;
  victim(secret_offset);
  INFO_LEAK_END;

  INFO_CONTROL_LEAK;
  exit(0);
  return 0;
}

