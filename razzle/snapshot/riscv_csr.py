SUPPORTED_CSR = [
    "mepc",
    "sepc",
    "mstatus",
    "misa",
    "mideleg",
    "mie",
    "medeleg",
    "mtvec",
    "stvec",
    "mcounteren",
    "scounteren",
    "mscratch",
    "sscratch",
    "satp",
    "fcsr",
]

RV64_MEPC_META = [
#   (name,    offset,   mask)
    ("EPC",     0,      0xffff_ffff_ffff_ffff),
]

RV64_SEPC_META = RV64_MEPC_META

RV64_MSTATUS_META = [
#   (name,    offset,   mask)
    ("SIE",     1,      0x1),
    ("MIE",     3,      0x1),
    ("SPIE",    5,      0x1),
    ("UBE",     6,      0x1),
    ("MPIE",    7,      0x1),
    ("SPP",     8,      0x1),
    ("VS",      9,      0x3),
    ("MPP",     11,     0x3),
    ("FS",      13,     0x3),
    ("XS",      15,     0x3),
    ("MPRV",    17,     0x1),
    ("SUM",     18,     0x1),
    ("MXR",     19,     0x1),
    ("TVM",     20,     0x1),
    ("TW",      21,     0x1),
    ("TSR",     22,     0x1),
    ("UXL",     32,     0x3),
    ("SXL",     34,     0x3),
    ("SBE",     36,     0x1),
    ("MBE",     37,     0x1),
    ("SD",      63,     0x1),
]

RV64_MISA_META = [
#   (name,    offset,   mask)
    ("A",       0,      0x1),
    ("B",       1,      0x1),
    ("C",       2,      0x1),
    ("D",       3,      0x1),
    ("E",       4,      0x1),
    ("F",       5,      0x1),
    ("H",       7,      0x1),
    ("I",       8,      0x1),
    ("J",       9,      0x1),
    ("M",       12,     0x1),
    ("N",       13,     0x1),
    ("P",       15,     0x1),
    ("Q",       16,     0x1),
    ("S",       18,     0x1),
    ("U",       20,     0x1),
    ("V",       21,     0x1),
    ("X",       23,     0x1),
    ("MXL",     62,     0x3),
]

RV64_MCOUNTEREN_META = [
#   (name,    offset,   mask)
    ("CY",      0,      0x1),
    ("TM",      1,      0x1),
    ("IR",      2,      0x1),
    ("HPM3",    3,      0x1),
    ("HPM4",    4,      0x1),
    ("HPM5",    5,      0x1),
    ("HPM6",    6,      0x1),
    ("HPM7",    7,      0x1),
    ("HPM8",    8,      0x1),
    ("HPM9",    9,      0x1),
    ("HPM10",   10,     0x1),
    ("HPM11",   11,     0x1),
    ("HPM12",   12,     0x1),
    ("HPM13",   13,     0x1),
    ("HPM14",   14,     0x1),
    ("HPM15",   15,     0x1),
    ("HPM16",   16,     0x1),
    ("HPM17",   17,     0x1),
    ("HPM18",   18,     0x1),
    ("HPM19",   19,     0x1),
    ("HPM20",   20,     0x1),
    ("HPM21",   21,     0x1),
    ("HPM22",   22,     0x1),
    ("HPM23",   23,     0x1),
    ("HPM24",   24,     0x1),
    ("HPM25",   25,     0x1),
    ("HPM26",   26,     0x1),
    ("HPM27",   27,     0x1),
    ("HPM28",   28,     0x1),
    ("HPM29",   29,     0x1),
    ("HPM30",   30,     0x1),
    ("HPM31",   31,     0x1),
]

RV64_SCOUNTEREN_META = RV64_MCOUNTEREN_META

RV64_MIE_META = [
#   (name,    offset,  mask)
    ("USI",     0,     0x1),
    ("SSI",     1,     0x1),
    ("HSI",     2,     0x1),
    ("MSI",     3,     0x1),
    ("UTI",     4,     0x1),
    ("STI",     5,     0x1),
    ("HTI",     6,     0x1),
    ("MTI",     7,     0x1),
    ("UEI",     8,     0x1),
    ("SEI",     9,     0x1),
    ("HEI",     10,    0x1),
    ("MEI",     11,    0x1),
]

RV64_MIDELEG_META = RV64_MIE_META

RV64_MEDELEG_META = [
#   (      name,             offset,    mask)
    ("Inst_Addr_Misalign",      0,      0x1),
    ("Inst_Access_Fault",       1,      0x1),
    ("Illegal_Inst",            2,      0x1),
    ("Breakpoint",              3,      0x1),
    ("Load_Addr_Misalign",      4,      0x1),
    ("Load_Access_Fault",       5,      0x1),
    ("Store_Addr_Misalign",     6,      0x1),
    ("Store_Access_Fault",      7,      0x1),
    ("Ecall_U",                 8,      0x1),
    ("Ecall_S",                 9,      0x1),
    ("Ecall_H",                 10,     0x1),
    ("Ecall_M",                 11,     0x1),
    ("Inst_Page_Fault",         12,     0x1),
    ("Load_Page_Fault",         13,     0x1),
    ("Store_Page_Fault",        15,     0x1),
]

RV64_MTVEC_META = [
#   (name,    offset,   mask)
    ("MODE",    0,      0x3),
    ("BASE",    2,      0xffff_ffff_ffff_fffc),
]

RV64_STVEC_META = RV64_MTVEC_META

RV64_SATP_META = [
#   (name,    offset,   mask)
    ("PPN",     0,      0x00ff_ffff_ffff_f000),
    ("ASID",    44,     0xffff),
    ("MODE",    60,     0xf),
]

RV64_MSCRATCH_META = [
#   (name,    offset,   mask)
    ("SCRATCH", 0,      0xffff_ffff_ffff_ffff),
]

RV64_SSCRATCH_META = RV64_MSCRATCH_META

RV64_PMPADDR_META = [
#   (name,    offset,   mask)
    ("PMPADDR",    0,   0x00ff_ffff_ffff_ffff),
]

RV64_PMPCFG_META = [
#   (name,    offset,   mask)
    ("R",       0,      0x1),
    ("W",       1,      0x1),
    ("X",       2,      0x1),
    ("A",       3,      0x3),
    ("L",       7,      0x1),
]

RV64_MEPC_META = [
#   (name,    offset,   mask)
    ("EPC",     0,      0xffff_ffff_ffff_ffff),
]

RV64_FCSR_META = [
#   (name,    offset,   mask)
    ("NX",      0,      0x1),
    ("UF",      1,      0x1),
    ("OF",      2,      0x1),
    ("DZ",      3,      0x1),
    ("NV",      4,      0x1),
    ("FRM",     5,      0x7),
]
