import json
import struct
from copy import copy
import logging
import argparse
from snapshot import *

def generate_bin(filename, targetname):
    binary_filename = targetname
    reg_state = json.load(open(filename))
    with open(binary_filename, "wb") as f:
        reg_encoder = [
            ("stvec", deccode_stvec),
            ("scounteren", decode_scounteren),
            ("sscratch", decode_reg),
            ("satp", decode_satp),
            ("misa", decode_misa),
            ("medeleg", decode_medeleg),
            ("mideleg", decode_mideleg),
            ("mie", decode_mie),
            ("mtvec", deccode_mtvec),
            ("mcounteren", decode_mcounteren),
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
        mstatus = decode_mstatus(target_set["mstatus"])
        priv = encode_priv(target_set["priv"])
        mstatus = (mstatus & ~(0b11 << 11)) | ((priv & 0b11) << 11)
        mstatus |= (mstatus & (0b1 << 3)) << 4
        f.write(struct.pack("Q", mstatus))
        pc = decode_reg(target_set["address"])
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
            f.write(struct.pack("Q", decode_reg(reg_state["GPR"][name])))


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
            ("stvec", deccode_stvec),
            ("scounteren", decode_scounteren),
            ("sscratch", decode_reg),
            ("satp", decode_satp),
            ("misa", decode_misa),
            ("medeleg", decode_medeleg),
            ("mideleg", decode_mideleg),
            ("mie", decode_mie),
            ("mtvec", deccode_mtvec),
            ("mcounteren", decode_mcounteren),
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
        mstatus = decode_mstatus(target_set["mstatus"])
        priv = encode_priv(target_set["priv"])
        mstatus = (mstatus & ~(0b11 << 11)) | ((priv & 0b11) << 11)
        mstatus |= (mstatus & (0b1 << 3)) << 4
        word.extend(word2hex(mstatus))
        pc = decode_reg(target_set["address"])
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
            word.extend(word2hex(decode_reg(reg_state["GPR"][name])))
        if len(word) % 4 != 0:
            word.extend(["00000000", "00000000"])
        word_line = [" ".join(word[i : i + 4]) + "\n" for i in range(0, len(word), 4)]
        f.writelines(word_line)
        f.close()


if __name__ == "__main__":
    parse = argparse.ArgumentParser(description="RVSnap is a RISC-V processor snapshot generator with a user-friendly interface that allows editing in JSON format.")
    parse.add_argument("-I", "--input", dest="input", required=True, help="input json")
    parse.add_argument("-O", "--output", dest="output", help="output file")
    parse.add_argument("-f", "--format", dest="format", default="hex", help="snapshot format")
    parse.add_argument("-d", "--debug", dest="debug", action="store_true", help="enable debug mode")
    args = parse.parse_args()

    if args.output is None:
        args.output = f"default.{args.format}"
    
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    design = RISCVSnapshot("rv64gc", 8)
    design.load_snapshot(args.input)

    # if args.format == "bin":
    #     generate_bin(args.input, args.output)
    # else:
    #     generate_hex(args.input, args.output)
