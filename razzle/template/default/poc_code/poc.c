#include "encoding.h"
#include "parafuzz.h"

__attribute__((optimize("align-functions=64")))
__attribute__((section (".poc.text")))
uint64_t access_time(uint8_t* base, int index, int offset) {
  INFO_LEAK_START;
  uint64_t time1 = 0, time2;
  uint8_t *addr = base + index*CACHE_BLOCK + offset;
  int junk = 0;
  time1 = read_csr(cycle);
  junk = *(addr);
  time2 = read_csr(cycle);
  INFO_LEAK_END;

  // printf(
  //   "[*] Access time for array[%4d*%4d~%4d]@%p=%ld, takes %ld CPU cycles\n", 
  //     index, CACHE_BLOCK, offset,
  //     addr, junk, 
  //     time2-time1);

  return time2-time1;
}