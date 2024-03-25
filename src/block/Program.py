from bisect import bisect_left

from bitstring import BitArray

import Utils
from Block import *


# RISC-V assembly program generator: main class to generate a RISC-V program


class Program:
    def __init__(self, section, output_path=None):
        self.section = {s: [] for s in section}
        self.output_path = output_path

    def add_to_section(self, section_name, instruction_list: list):
        for instr in instruction_list:
            self.section[section_name].append(instr)

    def write(self):
        with open(self.output_path, 'w') as file:
            for section_name in self.section.keys():
                for instr in self.section[section_name]:
                    file.write(instr + '\n')


class ProgramGenerator:

    def __init__(self, xlen, mode, vm, extension, hypervisor, case_weight, shuffle_cnt, output_path):
        self.xlen = xlen
        self.mode = mode
        self.vm = vm
        self.extension = extension
        self.hypervisor = hypervisor
        self.output_path = output_path
        self.case_weight = case_weight
        self.weight_prefix_sum = [case_weight[0]]
        self.shuffle_cnt = shuffle_cnt

        for i in range(1, len(case_weight)):
            self.weight_prefix_sum.append(
                self.weight_prefix_sum[-1] + case_weight[i])

    def init_gpr(self, program):
        instr_str = []
        for i in range(0, 32):
            reg_val = random.choice([
                BitArray(hex="0x0"),
                BitArray(hex="0x80000000"),
                BitArray(hex(random.randrange(0x1, 0xf))),
                BitArray(hex(random.randrange(0x10, 0xefffffff))),
                BitArray(hex(random.randrange(0xf0000000, 0xffffffff)))
            ])
            str = f"{Config.INDENT}li x{i}, 0x{reg_val.hex}"
            instr_str.append(str)
        program.add_to_section('text', instr_str)

    def gen_program_header(self, program):
        program.add_to_section('program_header', [Utils.program_include_instr])
        program.add_to_section('text_header', [
            'RVTEST_RV{}{}{}{}'.format(self.xlen, 'V' if self.hypervisor else '', self.mode,
                                       'F' if 'RV_F' in self.extension or 'RV_D' in self.extension else ''),
            Utils.program_code_begin_instr])

    def gen_program_exit(self, program):
        program.add_to_section('text_footer', [Utils.program_test_pass_instr])
        if not self.vm:
            program.add_to_section('text_footer', [Utils.program_stvec_handler_instr,
                                                   Utils.program_mtvec_handler_instr])
        program.add_to_section('text_footer', [Utils.program_code_end_instr])

    def gen_page_table(self, program):
        program.add_to_section('data_header', [Utils.program_data_start_instr])

        instr_str = []

        for page_n in range(10):
            instr_str.append("fuzzdata_data_page_{}:".format(page_n))
            instr_str.append(".align 12")

            for i in range(128):
                instr_str.append(
                    ".word 0x{:08x}, 0x{:08x}, 0x{:08x}, 0x{:08x}, 0x{:08x}, 0x{:08x}, 0x{:08x}, 0x{:08x}".format(
                        random.getrandbits(32), random.getrandbits(32), random.getrandbits(
                            32), random.getrandbits(32), random.getrandbits(32), random.getrandbits(32),
                        random.getrandbits(32), random.getrandbits(32)))

        program.add_to_section('data', instr_str)
        program.add_to_section('data_footer', [Utils.program_data_end_instr])

    def shuffle(self, block_list):
        for _ in range(self.shuffle_cnt):
            ptr_s = random.randint(0, len(block_list) - 1)
            ptr_i = random.randint(0, len(block_list[ptr_s].instr_list) - 1)
            if block_list[ptr_s].instr_list[ptr_i].protect:
                continue
            ptr_ni = ptr_i + 1
            ptr_ns = ptr_s
            if ptr_ni == len(block_list[ptr_s].instr_list):
                ptr_ni = 0
                ptr_ns = ptr_s + 1
            if ptr_ns >= len(block_list):
                continue
            if block_list[ptr_ns].instr_list[ptr_ni].protect:
                continue
            block_list[ptr_s].instr_list[ptr_i], block_list[ptr_ns].instr_list[
                ptr_ni] = block_list[ptr_ns].instr_list[ptr_ni], block_list[ptr_s].instr_list[ptr_i]
        return block_list

    def gen_program(self, block_cnt):
        program = Program(
            ['program_header', 'text_header', 'text', 'text_footer', 'data_header', 'data', 'data_footer'],
            self.output_path)
        self.gen_program_header(program)
        self.init_gpr(program)

        block_list = []
        i = 0
        # TODO: move to Configuration
        text_prefix = "fuzztext"
        data_prefix = "fuzzdata"
        while i < block_cnt:
            k = random.randint(0, self.weight_prefix_sum[-1] - 1)
            block = [
                IntArithmeticBlock(f"{text_prefix}_int_{i}", self.extension),
                FloatArithmeticBlock(
                    f"{text_prefix}_float_{i}", self.extension),
                LoadStoreBlock(
                    f"{text_prefix}_ls_{i}", self.extension,
                    f"{data_prefix}_data_page_{random.randint(1, 9)}", 4096),
                PteBlock(f"{text_prefix}_pte_{i}", self.extension,
                         self.vm, range(0x100, 0xfff)),
                CsrBlock(f"{text_prefix}_csr_{i}", self.extension, self.mode),
                SystemOperationBlock(
                    f"{text_prefix}_system_{i}", self.extension),
                MagicLoadBlock(f"{text_prefix}_magic_{i}", self.extension),
                MagicJumpBlock(
                    f"{text_prefix}_magic_jump_{i}", self.extension),
                AmoBlock(
                    f"{text_prefix}_amo_{i}", self.extension,
                    f"{data_prefix}_data_page_{random.randint(1, 9)}"),
                ZkBlock(f"{text_prefix}_zk_{i}", self.extension)
            ][bisect_left(self.weight_prefix_sum, k)]
            if block.work():
                block.gen_instr()
                block_list.append(block)
                i = i + 1

        block_list = self.shuffle(block_list)
        # add branch & jump

        ends = sorted(random.sample(list(range(1, 33)), 10))
        for i in range(len(ends)):
            if i == 0:
                start_p = 0
            else:
                start_p = ends[i - 1] * 3 + 1
            end_p = ends[i] * 3
            block_list[start_p].out_instr = new_branch_to(self.extension,
                                                          block_list[end_p].name)
            block_list[end_p].out_instr = new_jump_to(
                block_list[start_p + 1].name)
            block_list[end_p -
                       1].out_instr = new_jump_to(block_list[end_p + 1].name)

        instr_str = []

        for block in block_list:
            instr_str.append(block.name + ":")
            for item in block.instr_list:
                instr_str.append(Config.INDENT + item.to_asm())
            if block.out_instr is not None:
                for item in block.out_instr:
                    instr_str.append(Config.INDENT + item.to_asm())

        program.add_to_section('text', instr_str)

        self.gen_program_exit(program)
        self.gen_page_table(program)

        return program


def gen_program(seed, output_path):
    # TODO: add seed parser class
    # seed [63  , 62-61 , 60 , 59, 58, 57, 56, 55, 54
    #       XLEN, M/S/U , P/V,  M,  A,  F,  D,  C, Zk
    xlen = 64 if getbit(seed, 63) else 32

    if getbits(seed, 62, 61) == 0b00:
        mode = 'U'
    else:
        mode = 'S' if getbits(seed, 62, 61) == 0b01 else 'M'
    vm = getbit(seed, 60) if mode == 'U' else False
    extension = ['RV_I', 'RV64_I', 'RV_ZICSR']
    hypervisor = getbit(seed, 80) and mode != 'M' and not vm

    if getbit(seed, 54) and Config.ENABLE_ZK:
        extension.extend(['RV_ZK', 'RV64_ZBKB', 'RV_ZBKX',
                          'RV_ZBKB', 'RV_ZBKC', 'RV64_ZK'])

    if getbit(seed, 55):
        extension.extend(['RV_C', 'RV64_C'])

    if getbit(seed, 56):
        extension.extend(['RV_D', 'RV64_D'])

    if getbit(seed, 57):
        extension.extend(['RV_F', 'RV64_F'])

    if getbit(seed, 58):
        extension.extend(['RV_A', 'RV64_A'])

    if getbit(seed, 59):
        extension.extend(['RV_M', 'RV64_M'])

    if getbit(seed, 55) and getbit(seed, 56):
        extension.append('RV_C_D')

    Config.XLEN = xlen

    case_weight = []
    weight = getbits(seed, 79, 64)
    for i in range(Config.CASE_N):
        weight = (weight ** 2 + weight + 1)
        case_weight.append((weight & 0xf) + 1)
    shuffle_cnt = getbits(seed, 127, 112)
    instance = ProgramGenerator(
        xlen, mode, vm, extension, hypervisor, case_weight, shuffle_cnt, output_path)

    logging.info(f"SEED       = {seed}")
    logging.info(f"MODE       = RV{xlen}{mode}")
    logging.info(f"VM         = {vm}")
    logging.info(f"GROUP      = {extension}")
    logging.info(f"HYPERVISOR = {hypervisor}")
    logging.info(f"WEIGHT     = {case_weight}")
    logging.info(f"SHUFFLE    = {shuffle_cnt}")
    program = instance.gen_program(100)
    program.write()
