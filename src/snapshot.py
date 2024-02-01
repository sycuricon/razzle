import hjson
import logging
from riscv import *

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

def decode_mstatus(state_dict):
    return decode_fields(state_dict["csr"]["mstatus"], MSTATUS_META)

def decode_misa(state_dict):
    return decode_fields(state_dict["csr"]["misa"], MISA_META)

def decode_mcounteren(state_dict):
    return decode_fields(state_dict["csr"]["mcounteren"], MCOUNTEREN_META)

def decode_scounteren(state_dict):
    return decode_fields(state_dict["csr"]["scounteren"], MCOUNTEREN_META)

def decode_mie(state_dict):
    return decode_fields(state_dict["csr"]["mie"], MIE_META)

def decode_mideleg(state_dict):
    return decode_fields(state_dict["csr"]["mideleg"], MIE_META)

def decode_medeleg(state_dict):
    return decode_fields(state_dict["csr"]["medeleg"], MEDELEG_META)

def deccode_mtvec(state_dict):
    return decode_fields(state_dict["csr"]["mtvec"], MTVEC_META)

def deccode_stvec(state_dict):
    return decode_fields(state_dict["csr"]["stvec"], MTVEC_META)

def decode_satp(state_dict):
    return decode_fields(state_dict["csr"]["satp"], SATP_META)

class RISCVState:
    def __init__(self):
        self.xreg = None
        self.freg = None
        self.mstatus = None
        self.misa = None
        self.medeleg = None
        self.mideleg = None
        self.mie = None
        self.mtvec = None
        self.stvec = None
        self.mcounteren = None
        self.scounteren = None
        self.satp = None

    def dump_state(self):
        logging.info(f"{self}: {self.__dict__}")

    def load_state(self, init_state):
        self.xreg = [decode_reg(reg) for reg in init_state["xreg"]]
        self.freg = [decode_reg(reg) for reg in init_state["freg"]]
        self.mstatus = decode_mstatus(init_state)
        self.misa = decode_misa(init_state)
        self.medeleg = decode_medeleg(init_state)
        self.mideleg = decode_mideleg(init_state)
        self.mie = decode_mie(init_state)
        # self.mtvec = deccode_mtvec(init_state)
        # self.mcounteren = decode_mcounteren(init_state)
        # self.scounteren = decode_scounteren(init_state)
        # self.stvec = deccode_stvec(init_state)
        # self.satp = decode_satp(init_state)

class RISCVSnapshot:
    def __init__(self, march, pmp_num):
        self.xlen, self.extension = parse_march(march)
        self.pmp_num = pmp_num
        self.state = RISCVState()

    def dump_arch(self):
        logging.info(f"{self}: {self.__dict__}")

    def load_snapshot(self, init_file):
        init_state = hjson.load(open(init_file, "r"))
        self.state.load_state(init_state)
        self.state.dump_state()
        self.dump_arch()


def encode_bit(dict, name_set, offset_set, len_set):
    val = 0
    for name, offset, len in zip(name_set, offset_set, len_set):
        val |= (int(dict[name], base=2) & ((1 << len) - 1)) << offset
    return val

def encode_priv(dict):
    return int(dict, base=2)

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
