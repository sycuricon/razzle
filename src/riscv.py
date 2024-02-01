MSTATUS_META = [
#   (name,    offset,  width)
    ("SIE",     1,      1),
    ("MIE",     3,      1),
    ("SPIE",    5,      1),
    ("UBE",     6,      1),
    ("MPIE",    7,      1),
    ("SPP",     8,      1),
    ("VS",      9,      2),
    ("MPP",     11,     2),
    ("FS",      13,     2),
    ("XS",      15,     2),
    ("MPRV",    17,     1),
    ("SUM",     18,     1),
    ("MXR",     19,     1),
    ("TVM",     20,     1),
    ("TW",      21,     1),
    ("TSR",     22,     1),
    ("UXL",     32,     2),
    ("SXL",     34,     2),
    ("SBE",     36,     1),
    ("MBE",     37,     1),
    ("SD",      63,     1),
]

MISA_META = [
#   (name,    offset,  width)
    ("A",       0,      1),
    ("B",       1,      1),
    ("C",       2,      1),
    ("D",       3,      1),
    ("E",       4,      1),
    ("F",       5,      1),
    ("H",       7,      1),
    ("I",       8,      1),
    ("J",       9,      1),
    ("M",       12,     1),
    ("N",       13,     1),
    ("P",       15,     1),
    ("Q",       16,     1),
    ("S",       18,     1),
    ("U",       20,     1),
    ("V",       21,     1),
    ("X",       23,     1),
    ("MXL",     62,     2),
]

MCOUNTEREN_META = [
#   (name,    offset,  width)
    ("CY",      0,      1),
    ("TM",      1,      1),
    ("IR",      2,      1),
    ("HPM3",    3,      1),
    ("HPM4",    4,      1),
    ("HPM5",    5,      1),
    ("HPM6",    6,      1),
    ("HPM7",    7,      1),
    ("HPM8",    8,      1),
    ("HPM9",    9,      1),
    ("HPM10",   10,     1),
    ("HPM11",   11,     1),
    ("HPM12",   12,     1),
    ("HPM13",   13,     1),
    ("HPM14",   14,     1),
    ("HPM15",   15,     1),
    ("HPM16",   16,     1),
    ("HPM17",   17,     1),
    ("HPM18",   18,     1),
    ("HPM19",   19,     1),
    ("HPM20",   20,     1),
    ("HPM21",   21,     1),
    ("HPM22",   22,     1),
    ("HPM23",   23,     1),
    ("HPM24",   24,     1),
    ("HPM25",   25,     1),
    ("HPM26",   26,     1),
    ("HPM27",   27,     1),
    ("HPM28",   28,     1),
    ("HPM29",   29,     1),
    ("HPM30",   30,     1),
    ("HPM31",   31,     1),
]

MIE_META = [
#   (name,    offset,  width)
    ("USI",     0,     1),
    ("SSI",     1,     1),
    ("HSI",     2,     1),
    ("MSI",     3,     1),
    ("UTI",     4,     1),
    ("STI",     5,     1),
    ("HTI",     6,     1),
    ("MTI",     7,     1),
    ("UEI",     8,     1),
    ("SEI",     9,     1),
    ("HEI",     10,    1),
    ("MEI",     11,    1),
]

MEDELEG_META = [
#   (      name,             offset,  width)
    ("Inst_Addr_Misalign",      0,      1),
    ("Inst_Access_Fault",       1,      1),
    ("Illegal_Inst",            2,      1),
    ("Breakpoint",              3,      1),
    ("Load_Addr_Misalign",      4,      1),
    ("Load_Access_Fault",       5,      1),
    ("Store_Addr_Misalign",     6,      1),
    ("Store_Access_Fault",      7,      1),
    ("Ecall_U",                 8,      1),
    ("Ecall_S",                 9,      1),
    ("Ecall_H",                 10,     1),
    ("Ecall_M",                 11,     1),
    ("Inst_Page_Fault",         12,     1),
    ("Load_Page_Fault",         13,     1),
    ("Store_Page_Fault",        15,     1),
]

MTVEC_META = [
#   (name,    offset,   mask)
    ("MODE",    0,      0x3),
    ("BASE",    2,      0xffff_ffff_ffff_fffc),
]

SATP_META = [
#   (name,    offset,   mask)
    ("PPN",     0,      0x00ff_ffff_ffff_f000),
    ("ASID",    44,     0xffff),
    ("MODE",    60,     0xf),
]
