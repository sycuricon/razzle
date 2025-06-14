class Page:
    size = 0x1000


class Flag:
    D = 1 << 7
    A = 1 << 6
    G = 1 << 5
    U = 1 << 4
    X = 1 << 3
    W = 1 << 2
    R = 1 << 1
    V = 1


class Asmer:
    def global_inst(name):
        return [".global " + name + "\n"]

    def word_inst(imm):
        return ["\t" + ".word " + hex(imm) + "\n"]

    def quad_inst(imm):
        return ["\t" + ".quad " + hex(imm) + "\n"]

    def space_inst(imm):
        return ["\t" + ".space " + hex(imm) + "\n"]

    def section_inst(name, flag):
        flag_str = ""
        if flag & Flag.R:
            flag_str += "a"
        if flag & Flag.W:
            flag_str += "w"
        if flag & Flag.X:
            flag_str += "x"
        return ['.section "' + name + '","' + flag_str + '",@progbits\n']

    def string_inst(str):
        return ["\t" + '.string "' + str + '"\n']

    def label_inst(name):
        return [name + ":\n"]

    def fill_inst(repeat, size, value):
        return [
            "\t" + ".fill " + hex(repeat) + ", " + hex(size) + ", " + hex(value) + "\n"
        ]

    def byte_inst(byte_list):
        return ["\t.byte " + ",".join(list(map(str, byte_list))) + "\n"]

def isUnsigned(imm):
    return 0 <= imm and imm < 2**64

def isSigned(imm):
    return -(2**63) <= imm and imm < 2**63

def Unsigned2Signed(imm):
    if isUnsigned(imm):
        if imm < 2**63:
            return imm
        else:
            return imm - 2**64
    elif isSigned(imm):
        return imm
    else:
        raise Exception(f"{imm} is not 64 bit num")

def Signed2Unsigned(imm):
    if isSigned(imm):
        if imm > 0:
            return imm
        else:
            return imm + 2**64
    elif isUnsigned(imm):
        return imm
    else:
        raise Exception(f"{imm} is not 64 bit num")

def up_align(number, align):
    return (number + align - 1) // align * align

def down_align(number, align):
    return number // align * align

def get_symbol_file(file_name):
    symbol_table = {}
    for line in open(file_name, "rt"):
        address, _, symbol = line.strip().split()
        symbol_table[symbol] = int(address, base=16)
    return symbol_table
