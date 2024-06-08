import os
import random
import sys
from enum import *
from BuildManager import *
from SectionUtils import *
from SectionManager import *
from TransBlockUtils import *

from payload.Instruction import *
from payload.MagicDevice import *
from payload.Block import *

class ArbitraryBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('arbitrary_block', extension, output_path)

    def gen_default(self):
        block_list = []
        block_cnt = random.randint(4, 8)
        for i in range(block_cnt):
            block = RandomBlock(f'{self.name}_{i}', self.extension)
            block.gen_instr()
            block_list.append(block)

        start_p = 0
        while(start_p + 2 < block_cnt - 1):
            end_p = random.randint(start_p + 2, block_cnt -2)
            block_list[start_p].inst_list.extend(new_branch_to(self.extension,block_list[end_p].name))
            block_list[end_p].inst_list.extend(new_jump_to(block_list[start_p + 1].name))
            block_list[end_p -1].inst_list.extend(new_jump_to(block_list[end_p + 1].name))

            block_list[start_p].add_succeed(block_list[end_p])
            block_list[start_p].add_succeed(block_list[start_p + 1])
            block_list[end_p].add_succeed(block_list[start_p + 1])
            for i in range(start_p + 1, end_p - 1):
                block_list[i].add_succeed(block_list[i+1])
            block_list[end_p - 1].add_succeed(block_list[end_p + 1])

            start_p = end_p + 1

        for i in range(start_p, len(block_list)-1):
            block_list[i].add_succeed(block_list[i+1])

        self._add_inst_block_list(block_list)

class ReturnBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('return_block', extension, output_path)

    def gen_default(self):
        self._load_inst_str(
            [
                'fence',
                'INFO_VCTM_END',
                'ebreak'
            ]
        )

class DelayBlock(TransBlock):
    def __init__(self, extension, output_path, delay_len, delay_float_rate, delay_mem):
        super().__init__('delay_block', extension, output_path)
        self.float_rate = delay_float_rate
        self.delay_len = delay_len
        self.delay_mem = delay_mem

    def _gen_dep_list(self):
        if not self.delay_mem:
            self.GPR_list = [
                reg for reg in reg_range if reg not in ["A0", "ZERO"]
            ]
        else:
            self.GPR_list = [
                reg for reg in reg_range if reg not in ["A0", "ZERO", "T0"]
            ]

        self.FLOAT_list = float_range
        dep_list = []
        for _ in range(self.delay_len):
            if random.random() < self.float_rate:
                dep_list.append(random.choice(self.FLOAT_list))
            else:
                dep_list.append(random.choice(self.GPR_list))
        dep_list.append(random.choice(self.GPR_list))
        return dep_list

    def _gen_inst_list(self, dep_list):
        block = BaseBlock(f'{self.name}_body', self.extension, True)

        if self.delay_mem:
            block.inst_list.append(Instruction('la t0, random_data_block_page_base'))

        for i, src in enumerate(dep_list[0:-1]):
            dest = dep_list[i + 1]
            if src in self.GPR_list and dest in self.FLOAT_list:
                block.inst_list.append(
                    Instruction(f"fcvt.s.lu   {dest.lower()}, {src.lower()}")
                )
            elif src in self.FLOAT_list and dest in self.GPR_list:
                block.inst_list.append(
                    Instruction(f"fcvt.lu.s   {dest.lower()}, {src.lower()}")
                )
            elif src in self.FLOAT_list and dest in self.FLOAT_list:
                while True:
                    instr = Instruction()
                    instr.set_extension_constraint(
                        [
                            extension
                            for extension in [
                                "RV_D",
                                "RV64_D",
                                "RV_F",
                                "RV64_F",
                                "RV32_C_F",
                                "RV_C_D",
                            ]
                            if extension in self.extension
                        ]
                    )
                    instr.set_category_constraint(["FLOAT"])

                    def c_dest(name, frd):
                        return use_frd(name) and use_frs1(name) and frd == dest

                    instr.add_constraint(c_dest, ["NAME", "FRD"])
                    instr.solve()

                    freg_list = [
                        freg for freg in ["FRS1", "FRS2", "FRS3"] if instr.has(freg)
                    ]
                    for freg in freg_list:
                        if freg == src:
                            break
                    else:
                        instr[random.choice(freg_list)] = src

                    if instr.has("FRD"):
                        block.inst_list.append(instr)
                        break

            elif src in self.GPR_list and dest in self.GPR_list:
                while True:
                    instr = Instruction()
                    instr.set_extension_constraint(
                        [
                            extension
                            for extension in ["RV_M", "RV64_M"]
                            if extension in self.extension
                        ]
                    )
                    instr.set_category_constraint(["ARITHMETIC"])

                    def c_dest(name, rd):
                        return use_rs1(name) and rd == dest

                    instr.add_constraint(c_dest, ["NAME", "RD"])
                    instr.solve()

                    if instr.has("RS1") and instr["RS1"] != src:
                        if instr.has("RS2"):
                            if random.random() < 0.5:
                                instr["RS1"] = src
                            else:
                                instr["RS2"] = src
                        else:
                            instr["RS1"] = src

                    if instr.has("RS1") and instr["RS1"] not in self.GPR_list:
                        instr["RS1"] = random.choice(self.GPR_list)
                    if instr.has("RS2") and instr["RS2"] not in self.GPR_list:
                        instr["RS2"] = random.choice(self.GPR_list)

                    if instr.has("RD"):
                        block.inst_list.append(instr)
                        break
        
        if self.delay_mem:
            for i in range(2):
                instr = rand_instr(instr_extension=extension, instr_category=[
                    'LOAD', 'STORE', 'FLOAT_LOAD', 'FLOAT_STORE'], imm_range=range(-0x800, 0x800, 8))
                instr.solve()
                instr['RS1'] = 'T0'
                if instr['CATEGORY'] == 'LOAD' and instr['RD'] in dep_list:
                    instr['RD'] = random.choice([reg for reg in self.GPR_list if reg not in dep_list and reg != 'T0'])
                elif instr['CATEGORY'] == 'FLOAT_LOAD' and instr['FRD'] in dep_list:
                    instr['FRD'] = random.choice([freg for freg in self.FLOAT_list if freg not in dep_list])
                insert_place = random.randint(1, len(block.inst_list) - 1)
                block.inst_list.insert(insert_place, instr)

        self._add_inst_block(block)
    
    def _gen_block_begin(self):
        inst_begin = [
            'INFO_DELAY_START',
        ]
        self._load_inst_str(inst_begin)
    
    def _gen_block_end(self):

        inst_end = [
            f'{self.name}_delay_end:',
            'INFO_DELAY_END',
        ]
        self._load_inst_str(inst_end)
    
    def move_sync(self):
        self.inst_block_list[-1].inst_list[-1] = RawInstruction('INFO_DELAY_START')

    def gen_default(self):
        self._gen_block_begin()
        dep_list = self._gen_dep_list()
        self._gen_inst_list(dep_list)
        self.result_reg = dep_list[-1]
        reg = self.result_reg.lower()
        imm = random.randint(-0x800, 0x7ff)
        inst_offset = [
            'delay_offset:',
            f'addi {reg}, {reg}, {imm}',
        ]
        self._load_inst_str(inst_offset)

        self._gen_block_end()
    
    def load_template(self, template):
        super().load_template(template)
        final_inst = self.inst_block_list[-2].inst_list[-1]
        self.result_reg = final_inst['RD']

class NopBlock(TransBlock):
    def __init__(self, extension, output_path, c_nop_len):
        super().__init__('nop_block', extension, output_path)
        assert c_nop_len >= 0
        self.c_nop_len = c_nop_len

    def gen_default(self):
        inst_list = [
            'c.nop' for _ in range(self.c_nop_len//2 - 2)
        ]
        inst_list.insert(0, 'fence')

        self._load_inst_str(inst_list)

class TriggerType(Enum):
    LOAD_MISALIGN = auto()
    LOAD_ACCESS_FAULT = auto()
    LOAD_PAGE_FAULT = auto()
    
    STORE_MISALIGN = auto()
    STORE_ACCESS_FAULT = auto()
    STORE_PAGE_FAULT = auto()
    
    AMO_MISALIGN = auto()
    AMO_PAGE_FAULT = auto()
    AMO_ACCESS_FAULT = auto()
    
    EBREAK = auto()
    ECALL = auto()
    ILLEGAL = auto()
    
    V4 = auto()

    BRANCH = auto()
    JALR = auto()
    RETURN = auto()
    JMP = auto()

    INT = auto()
    FLOAT = auto()
    LOAD = auto()
    STORE = auto()
    AMO = auto()

    def need_train(trigger_type):
        return trigger_type in [TriggerType.BRANCH, TriggerType.JALR, TriggerType.RETURN, TriggerType.JMP,\
            TriggerType.INT, TriggerType.FLOAT, TriggerType.LOAD, TriggerType.STORE, TriggerType.AMO]

class LoadInitBlock(TransBlock):
    def __init__(self, depth, extension, output_path, init_block_list):
        super().__init__(f'load_init_block', extension, output_path)
        self.depth = depth
        self.entry = f'{self.name}_{self.depth}_entry'
        self.init_block_list = init_block_list
    
    def _need_init_compute(self):
        for block in self.init_block_list:
            block._compute_need_inited()
        for i in range(1, len(self.init_block_list)):
            self.init_block_list[i]._inited_posted_process(self.init_block_list[i-1].succeed_inited)
        
        need_inited = set()
        for block in self.init_block_list:
            need_inited.update(block.need_inited)

        return need_inited

    def _gen_init_code(self):
        need_inited = self._need_init_compute()
        need_inited.difference_update({'A0', 'ZERO'})

        self.float_init_list = []
        self.GPR_init_list = []

        has_sp = False
        if 'SP' in need_inited:
            has_sp = True
            need_inited.difference_update({'SP'})

        for reg in need_inited:
            if reg.startswith('F'):
                self.float_init_list.append(reg)
            else:
                self.GPR_init_list.append(reg)
        self.GPR_init_list.append('A0')
        if has_sp:
            self.GPR_init_list.append('SP')
        
        inst_list = [
            f"la sp, {self.name}_{self.depth}_data_table",
        ]
        data_list = [
            f"{self.name}_{self.depth}_data_table:"
        ]

        table_index = 0
        for freg in self.float_init_list:
            inst_list.append(f"c.fldsp {freg.lower()}, {table_index*8}(sp)")
            data_list.append(f".dword {hex(random.randint(0, 2**64))}")
            table_index += 1
        for reg in self.GPR_init_list:
            inst_list.append(f"c.ldsp {reg.lower()}, {table_index*8}(sp)")
            data_list.append(f".dword {hex(random.randint(0, 2**64))}")
            table_index += 1

        self._load_inst_str(inst_list, True)
        self._load_data_str(data_list)

    def _compute_trigger_param(self):
        raise Exception("the _compute_trigger_param is not implemented!!!")
    
    def update_depth(self, depth):
        self.depth = depth
        self.name =self.entry = f'{self.name}_{self.depth}_entry'
        self.inst_block_list[0].name = self.entry
        self.inst_block_list[0].inst_list[0] = Instruction(f"la sp, {self.name}_{self.depth}_data_table")
        self.data_list[0] = RawInstruction(f"{self.name}_{self.depth}_data_table:")

    def load_template(self, template):
        super().load_template(template)
        self.update_depth(self.depth)
        self.float_init_list = []
        self.GPR_init_list = []
        for inst in self.inst_block_list[0].inst_list[1:]:
            if inst.has('RD'):
                self.GPR_init_list.append(inst['RD'])
            else:
                self.float_init_list.append(inst['FRD'])
    
    def gen_default(self):
        self._gen_init_code()
