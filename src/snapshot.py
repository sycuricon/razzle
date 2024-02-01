import hjson
import logging

def parse_march(march):
    if len(march) < 5:
        return None, None
    march = march.lower().replace("rv64g", "rv64imafd").replace("rv32g", "rv32imafd")
    if march[0:5] not in ['rv64i', 'rv32i']:
        logging.error(f"Unsupported march {march[0:5]}")
        return None, None

    xlen = int(march[2:4])
    ext_list = march[4:].split('_')
    exts = set()

    for base_ext in ext_list[0]:
        if base_ext not in "imafdc":
            logging.error(f"Unsupported base extension {base_ext}")
            return None, None
        exts.add(base_ext)

    if len(ext_list) == 1:
        return xlen, exts

    for ext in ext_list[1:]:
        if ext[0] != 'z':
            logging.error(f"Unsupported extension {ext}")
            return None, None
        exts.add(ext)

    return xlen, exts

def decode_raw(reg_str, base):
    return int(reg_str, base=base)

def decode_hex(reg_str):
    return decode_raw(reg_str, 16)

def decode_dec(reg_str):
    return decode_raw(reg_str, 10)

def decode_bin(reg_str):
    return decode_raw(reg_str, 2)

def decode_reg(reg_str):
    if len(reg_str) <= 2:
        return decode_dec(reg_str)

    if reg_str[1] == 'x':
        return decode_hex(reg_str)
    elif reg_str[1] == 'b':
        return decode_bin(reg_str)
    else:
        return decode_dec(reg_str)

def decode_fields(val_dict, meta_list):
    val = 0
    for name, offset, width in meta_list:
        val |= (decode_reg(val_dict[name]) & ((1 << width) - 1)) << offset
    return val

class RISCVState:
    def __init__(self, width):
        self.width = width

    def dump_state(self):
        logging.info(f"{self}: {self.__dict__}")

class RISCVSnapshot:
    def __init__(self, march, pmp_num):
        self.xlen, self.extension = parse_march(march)
        self.pmp_num = pmp_num
        self.state = RISCVState()

    def dump_arch(self):
        logging.info(f"{self}: {self.__dict__}")

    def load_snapshot(self, init_file):
        init_state = hjson.load(open(init_file, "r"))
        self.state.dump_state() 


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
