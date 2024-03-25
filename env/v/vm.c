// See LICENSE for license details.

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "riscv_test.h"

#if __riscv_xlen == 32
#define SATP_MODE_CHOICE SATP_MODE_SV32
#elif defined(Sv48)
#define SATP_MODE_CHOICE SATP_MODE_SV48
#else
#define SATP_MODE_CHOICE SATP_MODE_SV39
#endif

void handler_super();
void exit_super(long int first_pc);

extern volatile uint64_t tohost;
extern volatile uint64_t fromhost;

static void do_tohost(uint64_t tohost_value) {
  while (tohost) fromhost = 0;
  tohost = tohost_value;
}

#define pa2kva(pa) ((void *)(pa)-DRAM_BASE - MEGAPAGE_SIZE)
#define uva2kva(pa) ((void *)(pa)-MEGAPAGE_SIZE)

#define flush_page(addr) asm volatile("sfence.vma %0" : : "r"(addr) : "memory")

static uint64_t lfsr63(uint64_t x) {
  uint64_t bit = (x ^ (x >> 1)) & 1;
  return (x >> 1) | (bit << 62);
}

static void cputchar(int x) { do_tohost(0x0101000000000000 | (unsigned char)x); }

static void cputstring(const char *s) {
  while (*s) cputchar(*s++);
}

static void terminate(int code) {
  do_tohost(code);
  while (1)
    ;
}

#define stringify1(x) #x
#define stringify(x) stringify1(x)
#define assert(x)                                       \
  do {                                                  \
    if (x) break;                                       \
    cputstring("Assertion failed: " stringify(x) "\n"); \
    terminate(3);                                       \
  } while (0)

#define l1pt pt[0]
#define user_l2pt pt[1]
#if SATP_MODE_CHOICE == SATP_MODE_SV48
#define NPT 6
#define kernel_l2pt pt[2]
#define kernel_l3pt pt[3]
#define user_l3pt pt[4]
#define user_llpt pt[5]
#elif SATP_MODE_CHOICE == SATP_MODE_SV39
#define NPT 11
#define kernel_l2pt pt[2]
#define get_user_llpt(x) pt[3 + x]
#elif SATP_MODE_CHOICE == SATP_MODE_SV32
#define NPT 2
#define user_llpt user_l2pt
#else
#error Unknown SATP_MODE_CHOICE
#endif
pte_t pt[NPT][PTES_PER_PT] __attribute__((aligned(PGSIZE)));

uintptr_t user_space_start = 0;
uintptr_t user_space_end = 0;
uintptr_t user_space_page_n = 0;
uintptr_t user_data_start = 0;
uintptr_t user_data_end = 0;
uintptr_t user_data_page_n = 0;
volatile uint64_t random_seed = 0;

void printhex(uint64_t x) {
  char str[17];
  for (int i = 0; i < 16; i++) {
    str[15 - i] = (x & 0xF) + ((x & 0xF) < 10 ? '0' : 'a' - 10);
    x >>= 4;
  }
  str[16] = 0;

  cputstring(str);
}

#define PTE_FIELD_MASK 0x03ff
#define FULL_PTE_FIELD (PTE_A | PTE_D | PTE_V | PTE_U | PTE_R | PTE_W | PTE_X)

int handle_fault(uintptr_t addr, uintptr_t cause) {
  long int llpt_idx = addr >> PGSHIFT >> 9;
  if (!(addr >= PGSIZE && addr < MAX_TEST_PAGES * PGSIZE)) {
    return 0;
  }
  addr = addr & (~PTE_FIELD_MASK);
  if (!user_l2pt[llpt_idx]) {
    user_l2pt[llpt_idx] = ((unsigned long long)get_user_llpt(llpt_idx) >> PGSHIFT << PTE_PPN_SHIFT) | PTE_V;
  } else {
    if ((user_l2pt[llpt_idx] & PTE_FIELD_MASK) != PTE_V) {
      user_l2pt[llpt_idx] = (user_l2pt[llpt_idx] >> PTE_PPN_SHIFT << PTE_PPN_SHIFT) | PTE_V;
      flush_page(addr);  // here we need to flush the page?
    }
  }

  uintptr_t *user_llpt = get_user_llpt(llpt_idx);

  long int user_offset = addr >> PGSHIFT & 0x1ff;
  if (user_llpt[user_offset]) {
    if ((user_llpt[user_offset] & PTE_FIELD_MASK) != FULL_PTE_FIELD) {
      user_llpt[user_offset] = (user_llpt[user_offset] & (~PTE_FIELD_MASK)) | FULL_PTE_FIELD;
      flush_page(addr);
      return 1;
    } else {
      return 0;
    }
  }

  // -1 for magic device
  uintptr_t text_addr = 0;
  if (addr >= 0x800000 && addr <= 0xffffff) {
    text_addr = (user_data_start / PGSIZE + (addr >> PGSHIFT) % user_data_page_n) * PGSIZE;
  } else {
    text_addr = (user_space_start / PGSIZE + (user_offset - 1) % user_space_page_n) * PGSIZE;
  }
  uintptr_t new_pte = (text_addr >> PGSHIFT << PTE_PPN_SHIFT);

#ifndef ENABLE_MAGIC_DEVICE
  long int pte_field = FULL_PTE_FIELD;
#else
  long int pte_field;
  MAGIC_ACCESS(pte_field, MAGIC_RDM_PTE);
#endif

  user_llpt[user_offset] = new_pte | pte_field;
  flush_page(addr);

  asm volatile("fence.i");
  return 1;
}

long int handle_trap(long int epc, long int cause, long int tval) {
  if (cause == CAUSE_FETCH_PAGE_FAULT || cause == CAUSE_LOAD_PAGE_FAULT || cause == CAUSE_STORE_PAGE_FAULT) {
    int pc_valid = handle_fault(tval, cause);
    if (!pc_valid) {
#ifndef ENABLE_MAGIC_DEVICE
      uintptr_t epc_pa = epc - 0x1000 + user_space_start;
      if ((*(unsigned short *)epc_pa & 3) != 3) {
        epc += 2;
      } else {
        epc += 4;
      }
#else
      MAGIC_ACCESS(epc, MAGIC_MEPC_NEXT);
#endif
    }
  } else {
#ifndef ENABLE_MAGIC_DEVICE
    uintptr_t epc_pa = epc - 0x1000 + user_space_start;
    if ((*(unsigned short *)epc_pa & 3) != 3) {
      epc += 2;
    } else {
      epc += 4;
    }
#else
    MAGIC_ACCESS(epc, MAGIC_MEPC_NEXT);
#endif
  }
  return epc;
}

static void coherence_torture() {
  // cause coherence misses without affecting program semantics
  uint64_t random = ENTROPY;
  while (1) {
    uintptr_t paddr = DRAM_BASE + ((random % (2 * (MAX_TEST_PAGES + 1) * PGSIZE)) & -4);
#ifdef __riscv_atomic
    if (random & 1)  // perform a no-op write
      asm volatile("amoadd.w zero, zero, (%0)" ::"r"(paddr));
    else  // perform a read
#endif
      asm volatile("lw zero, (%0)" ::"r"(paddr));
    random = lfsr63(random);
  }
}

void vm_boot(uintptr_t fuzz_loop_entry, uintptr_t fuzz_data_start, uintptr_t fuzz_data_end) {
  if (read_csr(mhartid) > 0) coherence_torture();

  _Static_assert(SIZEOF_TRAPFRAME_T == sizeof(trapframe_t), "xlen miss match");

#if (MAX_TEST_PAGES > PTES_PER_PT) || (DRAM_BASE % MEGAPAGE_SIZE) != 0
#error
#endif
  // map user to lowermost megapage
  l1pt[0] = ((pte_t)user_l2pt >> PGSHIFT << PTE_PPN_SHIFT) | PTE_V;
  // map kernel to uppermost megapage
#if SATP_MODE_CHOICE == SATP_MODE_SV48
  l1pt[PTES_PER_PT - 1] = ((pte_t)kernel_l2pt >> PGSHIFT << PTE_PPN_SHIFT) | PTE_V;
  kernel_l2pt[PTES_PER_PT - 1] = ((pte_t)kernel_l3pt >> PGSHIFT << PTE_PPN_SHIFT) | PTE_V;
  kernel_l3pt[PTES_PER_PT - 1] =
      (DRAM_BASE / RISCV_PGSIZE << PTE_PPN_SHIFT) | PTE_V | PTE_R | PTE_W | PTE_X | PTE_A | PTE_D;
  user_l2pt[0] = ((pte_t)user_l3pt >> PGSHIFT << PTE_PPN_SHIFT) | PTE_V;
  user_l3pt[0] = ((pte_t)user_llpt >> PGSHIFT << PTE_PPN_SHIFT) | PTE_V;
#elif SATP_MODE_CHOICE == SATP_MODE_SV39
  l1pt[PTES_PER_PT - 1] = ((pte_t)kernel_l2pt >> PGSHIFT << PTE_PPN_SHIFT) | PTE_V;
  kernel_l2pt[PTES_PER_PT - 1] =
      (DRAM_BASE / RISCV_PGSIZE << PTE_PPN_SHIFT) | PTE_V | PTE_R | PTE_W | PTE_X | PTE_A | PTE_D;
  user_l2pt[0] = ((pte_t)get_user_llpt(0) >> PGSHIFT << PTE_PPN_SHIFT) | PTE_V;
#elif SATP_MODE_CHOICE == SATP_MODE_SV32
  l1pt[PTES_PER_PT - 1] = (DRAM_BASE / RISCV_PGSIZE << PTE_PPN_SHIFT) | PTE_V | PTE_R | PTE_W | PTE_X | PTE_A | PTE_D;
#else
#error
#endif
  uintptr_t vm_choice = SATP_MODE_CHOICE;
  uintptr_t satp_value = ((uintptr_t)l1pt >> PGSHIFT) | (vm_choice * (SATP_MODE & ~(SATP_MODE << 1)));
  write_csr(satp, satp_value);
  if (read_csr(satp) != satp_value) assert(!"unsupported satp mode");

  // set up supervisor trap handling
  write_csr(stvec, pa2kva(handler_super));
  write_csr(sscratch, pa2kva(read_csr(mscratch)));
  write_csr(mideleg, 0);
  write_csr(medeleg, (1 << CAUSE_ILLEGAL_INSTRUCTION) | (1 << CAUSE_BREAKPOINT) | (1 << CAUSE_USER_ECALL) |
                         (1 << CAUSE_SUPERVISOR_ECALL) | (1 << CAUSE_HYPERVISOR_ECALL) | (1 << CAUSE_MACHINE_ECALL));

  // FPU on; accelerator on; vector unit on
  write_csr(mstatus, MSTATUS_FS | MSTATUS_XS | MSTATUS_VS | MSTATUS_SUM);

  // disable interrupt right now
  write_csr(mip, 0);
  write_csr(mie, MIP_MSIP);

  user_space_start = fuzz_loop_entry;
  user_data_end = user_space_end = fuzz_data_end;
  user_data_start = fuzz_data_start;
  user_space_page_n = user_space_end / PGSIZE - user_space_start / PGSIZE + 1;
  user_data_page_n = user_data_end / PGSIZE - user_data_start / PGSIZE + 1;

  // mapping magic device
  uintptr_t magic_device_entry = PTE_V | PTE_U | PTE_R | PTE_W | PTE_X | PTE_A | PTE_D;
  get_user_llpt(0)[0] = magic_device_entry;

  random_seed = ENTROPY;
  set_csr(mstatus, MSTATUS_MIE | MSTATUS_MPIE);
  exit_super(0x1000);
}
