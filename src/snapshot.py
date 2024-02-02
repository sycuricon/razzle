import hjson
import logging
from riscv import *


class RISCVReg:
    def __init__(self, width):
        self.width = width

    def dump(self):
        logging.info(f"{self}: {self.__dict__}")

    def decode_raw(self, reg_str, base):
        return int(reg_str, base=base)

    def decode_hex(self, reg_str):
        return self.decode_raw(reg_str, 16)

    def decode_dec(self, reg_str):
        return self.decode_raw(reg_str, 10)

    def decode_bin(self, reg_str):
        return self.decode_raw(reg_str, 2)

    def decode_reg(self, reg_str):
        if len(reg_str) <= 2:
            return self.decode_dec(reg_str)

        if reg_str[1] == "x":
            return self.decode_hex(reg_str)
        elif reg_str[1] == "b":
            return self.decode_bin(reg_str)
        else:
            return self.decode_dec(reg_str)

    def decode_fields(self, val_dict, meta_list):
        val = 0
        for name, offset, mask in meta_list:
            val |= (
                (self.decode_reg(val_dict[name]) & mask) // ((mask) & ~((mask) << 1))
            ) << offset
        return val
    
    def __save(self, func):
        if isinstance(self.data, list):
            return [func(d) for d in self.data]
        else:
            return [func(self.data)]

    def save(self, format="hex"):
        match format:
            case "hex":
                return self.__save(lambda d: hex(d)[2:].zfill(self.width // 4))
            case "bin":
                return self.__save(lambda d: d.to_bytes(self.width // 8, "little"))

for rf in ["xreg", "freg"]:
    globals()[f"RISCVReg_{rf}"] = type(
        f"RISCVReg_{rf}",
        (RISCVReg,),
        {
            "name": rf,
            '__init__': lambda self, width: RISCVReg.__init__(self, width),
            "decode": lambda self, init_state: setattr(
                self, "data", [self.decode_reg(reg) for reg in init_state[self.name]]
            ),
        },
    )

for csr in SUPPORTED_CSR:
    globals()[f"RISCVReg_{csr}"] = type(
        f"RISCVReg_{csr}",
        (RISCVReg,),
        {
            "name": csr,
            '__init__': lambda self, width: RISCVReg.__init__(self, width),
            "decode": lambda self, init_state: setattr(
                self, "data",
                self.decode_fields(
                    init_state["csr"][self.name],
                    globals()[f"RV{self.width}_{self.name.upper()}_META"],
                ),
            ),
        },
    )


class RISCVState:
    def __init__(self, xlen, target_list):
        self.xlen = xlen
        self.target_list = target_list

        for t in self.target_list:
            setattr(self, t, globals()[f"RISCVReg_{t}"](self.xlen))

    def dump(self):
        logging.info(f"{self}: {self.__dict__}")

    def load_state(self, init_state):
        for t in self.target_list:
            getattr(self, t).decode(init_state)
            getattr(self, t).dump()
    
    def save_state(self, target, format):
        return getattr(self, target).save(format)


class RISCVSnapshot:
    def __init__(self, march, pmp_num, selected_csr):
        self.xlen, self.extension = self.parse_march(march)
        self.pmp_num = pmp_num
        self.target_list = [
            t for t in [
                "xreg",
                "freg" if self.extension.issuperset(["f", "d"]) else None,
            ] if t is not None
        ] + selected_csr

        self.state = RISCVState(self.xlen, self.target_list)

    def parse_march(self, march):
        if len(march) < 5:
            return None, None
        march = march.lower().replace("rv64g", "rv64imafd").replace("rv32g", "rv32imafd")
        if march[0:5] not in ["rv64i", "rv32i"]:
            logging.error(f"Unsupported march {march[0:5]}")
            return None, None

        xlen = int(march[2:4])
        ext_list = march[4:].split("_")
        exts = set()

        for base_ext in ext_list[0]:
            if base_ext not in "imafdc":
                logging.error(f"Unsupported base extension {base_ext}")
                return None, None
            exts.add(base_ext)

        if len(ext_list) == 1:
            return xlen, exts

        for ext in ext_list[1:]:
            if ext[0] != "z":
                logging.error(f"Unsupported extension {ext}")
                return None, None
            exts.add(ext)

        return xlen, exts

    def dump(self):
        logging.info(f"{self}: {self.__dict__}")

    def load_snapshot(self, init_file):
        init_state = hjson.load(open(init_file, "r"))
        self.state.load_state(init_state)
        self.state.dump()

    def save(self, output_file, **kwargs):
        assert kwargs["format"] in ["hex", "bin"], "Unsupported output format"

        format_state = []
        for t in self.target_list:
            format_state.extend(self.state.save_state(t, kwargs["format"]))

        if kwargs["format"] == "bin":
            with open(output_file, "wb") as output_file:
                for s in format_state:
                    output_file.write(s)
        elif kwargs["format"] == "hex":
            with open(output_file, "wt") as output_file:
                output_buffer = []
                if kwargs["output_width"] > self.xlen:
                    assert kwargs["output_width"] % self.xlen == 0, "Misaligned output width"
                    chunk_size = kwargs["output_width"] // self.xlen
                    for i in range(0, len(format_state), chunk_size):
                        output_buffer.append("".join(reversed(format_state[i:i + chunk_size])))
                elif kwargs["output_width"] < self.xlen:
                    assert self.xlen % kwargs["output_width"] == 0, "Misaligned output width"
                    chunk_size = kwargs["output_width"] // 8 * 2
                    for s in format_state:
                        output_buffer.extend(reversed([s[i:i + chunk_size] for i in range(0, self.xlen // 8 * 2, chunk_size)]))
                else:
                    output_buffer = format_state
                output_file.write("\n".join(output_buffer))

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
