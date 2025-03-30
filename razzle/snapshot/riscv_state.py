import os
import hjson
import logging
from razzle.snapshot.riscv_csr import *
from string import Template


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
        if type(reg_str) is int:
            return reg_str
        try:
            if len(reg_str) <= 2:
                return self.decode_dec(reg_str)
            if reg_str[1] == "x":
                return self.decode_hex(reg_str)
            elif reg_str[1] == "b":
                return self.decode_bin(reg_str)
            else:
                return self.decode_dec(reg_str)
        except ValueError:
            return reg_str

    def decode_fields(self, val_dict, meta_list):
        try:
            val = 0
            for name, offset, mask in meta_list:
                mask_temp = mask
                suffix_zero_num = 0
                while (mask_temp & 1) == 0 and suffix_zero_num < 64:
                    suffix_zero_num += 1
                    mask_temp >>= 1
                val |= (self.decode_reg(val_dict[name]) & mask) >> suffix_zero_num << offset
            return val
        except TypeError:
            return val_dict[name]

    def __save(self, func):
        if isinstance(self.data, list):
            return [func(d, i) for i, d in enumerate(self.data)]
        else:
            return [func(self.data, 0)]

    def save(self, format="hex"):
        match format:
            case "hex":
                return self.__save(lambda d, i: hex(d)[2:].zfill(self.width // 4))
            case "bin":
                return self.__save(lambda d, i: d.to_bytes(self.width // 8, "little"))
            case "asm":
                return self.__save(
                    lambda d, i: f"init_{self.init_name[i]}:\n "
                    + (f".dword {hex(d) if isinstance(d, int) else d}\n")
                )


for rf, (begin, end) in zip(["xreg", "freg"], [(1, 32), (0, 32)]):
    globals()[f"RISCVReg_{rf}"] = type(
        f"RISCVReg_{rf}",
        (RISCVReg,),
        {
            "name": rf,
            "init_name": [f"{rf}{i}" for i in range(begin, end)],
            "__init__": lambda self, width: RISCVReg.__init__(self, width),
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
            "init_name": [csr],
            "__init__": lambda self, width: RISCVReg.__init__(self, width),
            "decode": lambda self, init_state: setattr(
                self,
                "data",
                self.decode_fields(
                    init_state["csr"][self.name],
                    globals()[f"RV{self.width}_{self.name.upper()}_META"],
                ),
            ),
        },
    )


def pmp_addr_decode(self, init_state):
    mode = init_state["pmp"][f"pmp{self.pmp_addr_idx}"]["A"]
    addr = init_state["pmp"][f"pmp{self.pmp_addr_idx}"]["ADDR"]
    match mode:
        case "OFF" | "TOR" | "NA4":
            self.data = self.decode_fields(
                {"PMPADDR": addr}, globals()[f"RV{self.width}_PMPADDR_META"]
            )
        case "NAPOT":
            addr = self.decode_reg(addr)
            range = self.decode_reg(
                init_state["pmp"][f"pmp{self.pmp_addr_idx}"]["RANGE"]
            )
            self.data = self.decode_fields(
                {"PMPADDR": (addr & ~range | ((range - 1) >> 1))},
                globals()[f"RV{self.width}_PMPADDR_META"],
            )


def pmp_cfg_decode(self, init_state):
    cfg = 0
    for cfg_idx in range(self.width // 8):
        idx = self.pmp_cfg_idx * 4 + cfg_idx
        if f"pmp{idx}" in init_state["pmp"]:
            A_alias = {"OFF": "0b00", "TOR": "0b01", "NA4": "0b10", "NAPOT": "0b11"}
            cfg_state = dict(init_state["pmp"][f"pmp{idx}"])
            cfg_state["A"] = A_alias[cfg_state["A"]]
            cfg |= self.decode_fields(
                cfg_state, globals()[f"RV{self.width}_PMPCFG_META"]
            ) << (cfg_idx * 8)
    self.data = cfg


for pmp_idx in range(64):
    globals()[f"RISCVReg_pmpaddr{pmp_idx}"] = type(
        f"RISCVReg_pmpaddr{pmp_idx}",
        (RISCVReg,),
        {
            "name": f"pmpaddr{pmp_idx}",
            "init_name": [f"pmpaddr{pmp_idx}"],
            "pmp_addr_idx": pmp_idx,
            "__init__": lambda self, width: RISCVReg.__init__(self, width),
            "decode": pmp_addr_decode,
        },
    )
    if pmp_idx % 4 == 0:
        globals()[f"RISCVReg_pmpcfg{pmp_idx // 4}"] = type(
            f"RISCVReg_pmpcfg{pmp_idx // 4}",
            (RISCVReg,),
            {
                "name": f"pmpcfg{pmp_idx // 4}",
                "init_name": [f"pmpcfg{pmp_idx // 4}"],
                "pmp_cfg_idx": pmp_idx // 4,
                "__init__": lambda self, width: RISCVReg.__init__(self, width),
                "decode": pmp_cfg_decode,
            },
        )


class RISCVState:
    def __init__(self, xlen, target_list, pmp_num):
        self.xlen = xlen
        self.target_list = target_list
        self.pmp_num = pmp_num

        for t in self.target_list:
            setattr(self, t, globals()[f"RISCVReg_{t}"](self.xlen))

    def dump(self):
        logging.info(f"{self}: {self.__dict__}")

    def load_state(self, init_state):
        for t in self.target_list:
            getattr(self, t).decode(init_state)

    def save_state(self, target, format):
        return getattr(self, target).save(format)


class RISCVSnapshot:
    def __init__(self, march, pmp_num, selected_csr, fuzz=False):
        self.fuzz = fuzz
        self.xlen, self.extension = self.parse_march(march)
        self.selected_csr = selected_csr
        self.target_list = (
            selected_csr
            + self.gen_pmp_list(pmp_num)
            + [
                t
                for t in [
                    "freg" if self.extension.issuperset(["f", "d"]) else None,
                    "xreg",
                ]
                if t is not None
            ]
        )

        self.state = RISCVState(self.xlen, self.target_list, self.pmp_num)

    def gen_pmp_list(self, pmp_num):
        self.pmp_num = pmp_num
        pmp_addr_list = [f"pmpaddr{idx}" for idx in range(self.pmp_num)]
        if self.xlen == 32:
            pmp_cfg_list = [f"pmpcfg{idx}" for idx in range((self.pmp_num + 3) // 4)]
        elif self.xlen == 64:
            pmp_cfg_list = [
                f"pmpcfg{idx * 2}" for idx in range((self.pmp_num + 7) // 8)
            ]
        else:
            pmp_cfg_list = []

        return pmp_addr_list + pmp_cfg_list

    def parse_march(self, march):
        if len(march) < 5:
            return None, None
        march = (
            march.lower().replace("rv64g", "rv64imafd").replace("rv32g", "rv32imafd")
        )
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

    def load_state(self, init_state):
        self.state.load_state(init_state)

    def csr_map(self, init_state, csr_map, csr_state):
        def str2int(value):
            if type(value) is not int:
                try:
                    if value.startswith('0x'):
                        value = int(value, base=16)
                    elif value.startswith('0b'):
                        value = int(value, base=2)
                    else:
                        value = int(value, base=10)
                except ValueError:
                    value = value
            return value

        def rtl_parse(rtl_state):
            if '[' not in rtl_state:
                rtl_name, rtl_len, rtl_offset = rtl_state, 1, 0
            elif ':' not in rtl_state:
                rtl_name, suffix = rtl_state.split('[')
                rtl_offset = str2int(suffix[:-1])
                rtl_len = 1
            else:
                rtl_name, suffix = rtl_state.split('[')
                suffix = suffix[:-1]
                rtl_end, rtl_begin = suffix.split(':')
                rtl_end = str2int(rtl_end)
                rtl_begin = str2int(rtl_begin)
                rtl_len = rtl_end - rtl_begin + 1
                rtl_offset = rtl_begin
            return rtl_name, rtl_len, rtl_offset
        
        for rtl_name, rtl_value in csr_state.items():
            csr_state[rtl_name] = str2int(rtl_value)

        for i, value in enumerate(init_state['xreg']):
            init_state['xreg'][i] = str2int(value)

        for i, value in enumerate(init_state['freg']):
            init_state['freg'][i] = str2int(value)

        for csr_type in ['csr', 'pmp']:
            for csr_name, csr_field in init_state[csr_type].items():
                if csr_name not in csr_map[csr_type]:
                    for csr_sub_field, csr_sub_field_default in csr_field.items():
                        csr_field[csr_sub_field] = str2int(csr_sub_field_default)
                    continue
                
                for csr_sub_field, csr_sub_field_default in csr_field.items():
                    if csr_sub_field not in csr_map[csr_type][csr_name]:
                        csr_field[csr_sub_field] = str2int(csr_sub_field_default)
                        continue
                    
                    rtl_state = csr_map[csr_type][csr_name][csr_sub_field]
                    rtl_name, rtl_len, rtl_offset = rtl_parse(rtl_state)

                    if rtl_name not in csr_state:
                        csr_field[csr_sub_field] = str2int(csr_sub_field_default)
                        continue
                    
                    info_value = (str2int(csr_state[rtl_name]) >> rtl_offset) & ((1 << rtl_len) - 1)
                    match (csr_type, csr_name, csr_sub_field):
                        case ('pmp', _, 'A'):
                            pmp_format = ['OFF', 'TOR', 'NA4', 'NAPOT']
                            csr_value = pmp_format[info_value]
                        case ('pmp', _, 'ADDR'):
                            a_value = init_state['pmp'][csr_name]['A']
                            match a_value:
                                case 'OFF'|'TOR' | 'NA4':
                                    csr_value = info_value << 2
                                case 'NAPOT':
                                    pmp_addr = info_value << 2
                                    pmp_len = 0b100
                                    while (pmp_addr & pmp_len) != 0:
                                        pmp_len <<= 1
                                    pmp_len <<= 1
                                    pmp_addr = pmp_addr & ~(pmp_len - 1)
                                    csr_value = pmp_addr
                                    init_state['pmp'][csr_name]['RANGE'] = pmp_len
                                case _:
                                    raise Exception(f'undefine pmpaddr type {a_value}')
                        case ('csr', 'mtvec', 'BASE') | ('csr', 'stvec', 'BASE'):
                            csr_value = info_value << 2
                        case ('csr', 'satp', 'PPN'):
                            csr_value = info_value << 12
                        case _:
                            csr_value = info_value
                    csr_field[csr_sub_field] = csr_value
        return init_state
                    
    def load_snapshot(self, init_file, map_file, state_file):
        def get_hjson_value(filename):
            if filename is None:
                return None
            if type(filename) is str:
                return hjson.load(open(filename, "r"))
            return filename
        init_state = get_hjson_value(init_file)
        csr_map = get_hjson_value(map_file)
        csr_state = get_hjson_value(state_file)
        if not (csr_map is None) and not (state_file is None):
            init_state = self.csr_map(init_state, csr_map, csr_state) 
            with open('./config/temp', 'wt') as file:
                hjson.dump(init_state, file)
        self.state.load_state(init_state)

    def save(self, output_file, **kwargs):
        output_format = kwargs["output_format"]
        assert output_format in ["hex", "bin", "asm"], "Unsupported output format"

        format_state = []
        for t in self.target_list:
            format_state.extend(self.state.save_state(t, output_format))

        if output_format == "bin":
            with open(output_file, "wb") as output_file:
                for s in format_state:
                    output_file.write(s)
        elif output_format == "hex":
            with open(output_file, "wt") as output_file:
                output_buffer = []
                output_width = kwargs["output_width"]
                if output_width > self.xlen:
                    assert output_width % self.xlen == 0, "Misaligned output width"
                    chunk_size = output_width // self.xlen
                    for i in range(0, len(format_state), chunk_size):
                        output_buffer.append(
                            "".join(reversed(format_state[i : i + chunk_size]))
                        )
                elif output_width < self.xlen:
                    assert self.xlen % output_width == 0, "Misaligned output width"
                    chunk_size = output_width // 8 * 2
                    for s in format_state:
                        output_buffer.extend(
                            reversed(
                                [
                                    s[i : i + chunk_size]
                                    for i in range(0, self.xlen // 8 * 2, chunk_size)
                                ]
                            )
                        )
                else:
                    output_buffer = format_state
                output_file.write("\n".join(output_buffer))
        elif output_format == "asm":
            with open(output_file, "wt") as output_file:
                for s in format_state:
                    output_file.write(s)

    def __gen_load_asm(self, target, idx, base="x31", tmp="x30"):
        result = []
        match target:
            case "xreg":
                for i in range(0, 31):
                    result.append(f"pop_xreg(x{i + 1}, {base}, {idx + i})")
            case "freg":
                for i in range(0, 32):
                    result.append(f"pop_freg(f{i}, {base}, {idx + i})")
            case _:
                result.append(f"pop_csr({target}, {tmp}, {base}, {idx})")

        return result

    def gen_loader(self, asm_file, **kwargs):
        if all(attr in kwargs for attr in ["with_bin", "with_rom", "with_asm"]):
            raise ValueError("with_bin, with_rom and with_asm cannot be used together")

        load_offset = []
        offset = 0
        for t in self.target_list:
            asm_list = self.__gen_load_asm(t, offset)
            load_offset.extend(asm_list)
            offset += len(asm_list)

        include_bin = ""
        if "with_bin" in kwargs:
            load_base_addr = "la x31, reg_info"
            binary_file = kwargs["with_bin"]
            include_bin = f'.incbin "{binary_file}"'
        elif "with_asm" in kwargs:
            load_base_addr = "la x31, reg_info"
            data_asm_file = kwargs["with_asm"]
            include_bin = f'#include "{data_asm_file}"'
        else:
            rom_addr = kwargs["with_rom"]
            load_base_addr = f"la x31, {hex(rom_addr)}"

        with open(asm_file, "wt") as asm_file:
            RAZZLE_ROOT = os.environ["RAZZLE_ROOT"]
            if self.fuzz:
                template = Template(
                    open(f"{RAZZLE_ROOT}/template/loader/init_fuzz.tmp", "r").read()
                )
            else:
                template = Template(
                    open(f"{RAZZLE_ROOT}/template/loader/init.tmp", "r").read()
                )
            done = template.substitute(
                load_state_setup=load_base_addr,
                load_state_body="\n".join(load_offset),
                load_state_extra=include_bin,
            )

            asm_file.write(done)
