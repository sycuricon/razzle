import sys
import json
import struct
from copy import copy


def encode_bit(dict, name_set, offset_set, len_set):
    val = 0
    for name, offset, len in zip(name_set, offset_set, len_set):
        val |= (int(dict[name], base=2) & ((1 << len) - 1)) << offset
    return val


def encode_tvec(dict):
    return int(dict["BASE"], base=16) | int(dict["MODE"], base=2)


def encode_countern(dict):
    name = [
        "CY",
        "TM",
        "IR",
        "HPM3",
        "HPM4",
        "HPM5",
        "HPM6",
        "HPM7",
        "HPM8",
        "HPM9",
        "HPM10",
        "HPM11",
        "HPM12",
        "HPM13",
        "HPM14",
        "HPM15",
        "HPM16",
        "HPM17",
        "HPM18",
        "HPM19",
        "HPM20",
        "HPM21",
        "HPM22",
        "HPM23",
        "HPM24",
        "HPM25",
        "HPM26",
        "HPM27",
        "HPM28",
        "HPM29",
        "HPM30",
        "HPM31",
    ]
    offset = [
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        15,
        16,
        17,
        18,
        19,
        20,
        21,
        22,
        23,
        24,
        25,
        26,
        27,
        28,
        29,
        30,
        31,
    ]
    len = [
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
    ]
    return encode_bit(dict, name, offset, len)


def encode_reg(dict):
    return int(dict, base=16)


def encode_priv(dict):
    return int(dict, base=2)


def encode_satp(dict):
    return (
        (int(dict["PPN"], base=16) >> 12)
        | (int(dict["ASID"], base=16) << 44)
        | (int(dict["MODE"], base=16) << 60)
    )


def encode_misa(dict):
    name = [
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
        "H",
        "I",
        "J",
        "M",
        "N",
        "P",
        "Q",
        "S",
        "U",
        "V",
        "X",
        "64",
    ]
    offset = [0, 1, 2, 3, 4, 5, 7, 8, 9, 12, 13, 15, 16, 18, 20, 21, 23, 63]
    len = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    return encode_bit(dict, name, offset, len)


def encode_medeleg(dict):
    name = [
        "Iaddr_Misalign",
        "Iaccess_Fault",
        "Illegal_Inst",
        "Breakpoint",
        "Laddr_Misalign",
        "Laccess_Fault",
        "Saddr_Misalign",
        "Saccess_Fault",
        "Ecall_U",
        "Ecall_S",
        "Ecall_H",
        "Ecall_M",
        "IPage_Fault",
        "LPage_Fault",
        "SPage_Fault",
    ]
    offset = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15]
    len = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    return encode_bit(dict, name, offset, len)


def encode_mideleg(dict):
    name = [
        "USI",
        "SSI",
        "HSI",
        "MSI",
        "UTI",
        "STI",
        "HTI",
        "MTI",
        "UEI",
        "SEI",
        "HEI",
        "MEI",
    ]
    offset = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    len = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    return encode_bit(dict, name, offset, len)


def encode_mie(dict):
    name = [
        "USIE",
        "SSIE",
        "HSIE",
        "MSIE",
        "UTIE",
        "STIE",
        "HTIE",
        "MTIE",
        "UEIE",
        "SEIE",
        "HEIE",
        "MEIE",
    ]
    offset = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    len = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    return encode_bit(dict, name, offset, len)


def encode_pmp(dict, pmpaddr_fore):
    a_map = {"OFF": "00", "TOR": "01", "NA4": "10", "NAPOT": "11"}
    dict["A"] = a_map[dict["A"]]
    name = ["R", "W", "X", "A", "L"]
    offset = [0, 1, 2, 3, 7]
    len = [1, 1, 1, 2, 1]
    cfg = encode_bit(dict, name, offset, len)
    mode = int(dict["A"], base=2)
    begin = int(dict["begin"], base=16)
    end = int(dict["end"], base=16)
    if mode == 0:
        end >>= 2
    elif mode == 1:
        if end < begin or pmpaddr_fore != begin >> 2:
            raise "this pmp section's begin is not equal to the fore pmpaddr's value"
        end >>= 2
    elif mode == 2:
        if begin >> 2 != end >> 2 or begin & 0b11 != 0 or end & 0b11 != 0b11:
            raise "NA4's begin and end's format is wrong"
        end >>= 2
    else:
        len = 1 + end - begin
        if len > 1 << 57 or len & (len - 1) != 0:
            raise "the length of the section is larger than 1^57 or is not aligned to 2^exp"
        mask = len - 1
        if begin & mask != 0:
            raise "the addr of the section is not aligned to 2^exp"
        mask >>= 1
        end = begin | mask
        end >>= 2
    return cfg, end


def encode_mstatus(dict):
    name = [
        "SIE",
        "MIE",
        "SPIE",
        "UBE",
        "MPIE",
        "SPP",
        "VS",
        "MPP",
        "FS",
        "XS",
        "MPRV",
        "SUM",
        "MXR",
        "TVM",
        "TW",
        "TSR",
        "UXL",
        "SXL",
        "SBE",
        "MBE",
        "SD",
    ]
    offset = [
        1,
        3,
        5,
        6,
        7,
        8,
        9,
        11,
        13,
        15,
        17,
        18,
        19,
        20,
        21,
        22,
        32,
        34,
        36,
        37,
        63,
    ]
    len = [1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 2, 2, 1, 1, 1]
    return encode_bit(dict, name, offset, len)


def generate_bin(filename, targetname):
    binary_filename = targetname
    reg_state = json.load(open(filename))
    with open(binary_filename, "wb") as f:
        reg_encoder = [
            ("stvec", encode_tvec),
            ("scounteren", encode_countern),
            ("sscratch", encode_reg),
            ("satp", encode_satp),
            ("misa", encode_misa),
            ("medeleg", encode_medeleg),
            ("mideleg", encode_mideleg),
            ("mie", encode_mie),
            ("mtvec", encode_tvec),
            ("mcounteren", encode_countern),
        ]
        for name, func in reg_encoder:
            f.write(struct.pack("Q", func(reg_state["csr"][name])))

        pmp_set = reg_state["pmp"]
        pmpcfg_name = [
            "pmp0cfg",
            "pmp1cfg",
            "pmp2cfg",
            "pmp3cfg",
            "pmp4cfg",
            "pmp5cfg",
            "pmp6cfg",
            "pmp7cfg",
            "pmp8cfg",
            "pmp9cfg",
            "pmp10cfg",
            "pmp11cfg",
            "pmp12cfg",
            "pmp13cfg",
            "pmp14cfg",
            "pmp15cfg",
        ]
        pmpcfg_set = []
        pmpcfg = 0
        pmpaddr_set = []
        for i, name in enumerate(pmpcfg_name):
            cfg, addr = encode_pmp(pmp_set[name], 0 if i == 0 else pmpaddr_set[-1])
            pmpcfg |= cfg << 64
            pmpcfg >>= 8
            if i % 8 == 0:
                pmpcfg_set.append(copy(pmpcfg))
                pmpcfg = 0
            pmpaddr_set.append(addr)
        for cfg in pmpcfg_set:
            f.write(struct.pack("Q", cfg))
        for addr in pmpaddr_set:
            f.write(struct.pack("Q", addr))

        target_set = reg_state["target"]
        mstatus = encode_mstatus(target_set["mstatus"])
        priv = encode_priv(target_set["priv"])
        mstatus = (mstatus & ~(0b11 << 11)) | ((priv & 0b11) << 11)
        mstatus |= (mstatus & (0b1 << 3)) << 4
        f.write(struct.pack("Q", mstatus))
        pc = encode_reg(target_set["address"])
        f.write(struct.pack("Q", pc))
        reg_name = [
            "x1",
            "x2",
            "x3",
            "x4",
            "x5",
            "x6",
            "x7",
            "x8",
            "x9",
            "x10",
            "x11",
            "x12",
            "x13",
            "x14",
            "x15",
            "x16",
            "x17",
            "x18",
            "x19",
            "x20",
            "x21",
            "x22",
            "x23",
            "x24",
            "x25",
            "x26",
            "x27",
            "x28",
            "x29",
            "x30",
            "x31",
        ]
        for name in reg_name:
            f.write(struct.pack("Q", encode_reg(reg_state["GPR"][name])))


def generate_hex(filename, targetname):
    def word2hex(word):
        value = hex(word)[2:]
        value_16 = "0" * (16 - len(value)) + value
        return [value_16[8:16], value_16[0:8]]

    hex_filename = targetname
    reg_state = json.load(open(filename))
    word = []
    with open(hex_filename, "wt") as f:
        reg_encoder = [
            ("stvec", encode_tvec),
            ("scounteren", encode_countern),
            ("sscratch", encode_reg),
            ("satp", encode_satp),
            ("misa", encode_misa),
            ("medeleg", encode_medeleg),
            ("mideleg", encode_mideleg),
            ("mie", encode_mie),
            ("mtvec", encode_tvec),
            ("mcounteren", encode_countern),
        ]
        for name, func in reg_encoder:
            word.extend(word2hex(func(reg_state["csr"][name])))

        pmp_set = reg_state["pmp"]
        pmpcfg_name = [
            "pmp0cfg",
            "pmp1cfg",
            "pmp2cfg",
            "pmp3cfg",
            "pmp4cfg",
            "pmp5cfg",
            "pmp6cfg",
            "pmp7cfg",
            "pmp8cfg",
            "pmp9cfg",
            "pmp10cfg",
            "pmp11cfg",
            "pmp12cfg",
            "pmp13cfg",
            "pmp14cfg",
            "pmp15cfg",
        ]
        pmpcfg_set = []
        pmpcfg = 0
        pmpaddr_set = []
        for i, name in enumerate(pmpcfg_name):
            cfg, addr = encode_pmp(pmp_set[name], 0 if i == 0 else pmpaddr_set[-1])
            pmpcfg |= cfg << 64
            pmpcfg >>= 8
            print("cfg", hex(pmpcfg))
            if (i + 1) % 8 == 0:
                pmpcfg_set.append(copy(pmpcfg))
                pmpcfg = 0
            pmpaddr_set.append(addr)
        for cfg in pmpcfg_set:
            word.extend(word2hex(cfg))
        for addr in pmpaddr_set:
            word.extend(word2hex(addr))

        target_set = reg_state["target"]
        mstatus = encode_mstatus(target_set["mstatus"])
        priv = encode_priv(target_set["priv"])
        mstatus = (mstatus & ~(0b11 << 11)) | ((priv & 0b11) << 11)
        mstatus |= (mstatus & (0b1 << 3)) << 4
        word.extend(word2hex(mstatus))
        pc = encode_reg(target_set["address"])
        word.extend(word2hex(pc))
        reg_name = [
            "x1",
            "x2",
            "x3",
            "x4",
            "x5",
            "x6",
            "x7",
            "x8",
            "x9",
            "x10",
            "x11",
            "x12",
            "x13",
            "x14",
            "x15",
            "x16",
            "x17",
            "x18",
            "x19",
            "x20",
            "x21",
            "x22",
            "x23",
            "x24",
            "x25",
            "x26",
            "x27",
            "x28",
            "x29",
            "x30",
            "x31",
        ]
        for name in reg_name:
            word.extend(word2hex(encode_reg(reg_state["GPR"][name])))
        if len(word) % 4 != 0:
            word.extend(["00000000", "00000000"])
        word_line = [" ".join(word[i : i + 4]) + "\n" for i in range(0, len(word), 4)]
        f.writelines(word_line)
        f.close()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(
            "we need filename of register state, the out filename, the choice of hex or bin"
        )
    filename = sys.argv[1]
    targetname = sys.argv[2]
    choose = sys.argv[3]
    print("get the register state from", filename)
    print("genrate", choose)
    if choose == "bin":
        generate_bin(filename, targetname)
    else:
        generate_hex(filename, targetname)
