#ifndef RVSNAP_H
#define RVSNAP_H

#if __riscv_xlen == 64
#define LOAD_XREG       ld
#define LOAD_FREG       fld
#define REG_SIZE        8
#else
#define LOAD_XREG       lw
#define LOAD_FREG       flw
#define REG_SIZE        4
#endif

#define pop_xreg(target, base, idx)                 \
        LOAD_XREG target, (idx * REG_SIZE)(base);

#define pop_freg(target, base, idx)                 \
        LOAD_FREG target, (idx * REG_SIZE)(base);

#define pop_csr(target_csr, tmp, base, idx)         \
        LOAD_XREG tmp, (idx * REG_SIZE)(base);      \
        csrw target_csr, tmp

#endif // RVSNAP_H
