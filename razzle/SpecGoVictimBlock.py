import os
import random
import sys
import copy
import hjson
from enum import *
from BuildManager import *
from SectionUtils import *
from SectionManager import *
from TransBlockUtils import *
from TransBodyBlock import *

from payload.Instruction import *
from payload.MagicDevice import *
from payload.Block import *

class SpecGoTriggerBlock(TransBlock):
    def __init__(self, root_info_path, dep_reg, extension, output_path):
        super().__init__('trigger_block', extension, output_path)
        with open(root_info_path, 'rt') as file:
            root_info = hjson.loads(file.read())
        inst_code = int(root_info['inst_code'], base=16)
        result_value = int(root_info['result_value'], base=16)
        temp_file = f'{random.randint(0, 2**64)}_temp'
        os.system(f'echo \'DASM({inst_code})\' | spike-dasm > {temp_file}')
        with open(temp_file, 'rt') as file:
            self.trigger_inst = Instruction(file.readlines()[0].strip())
        os.system(f'rm {temp_file}')
        self.dep_reg = dep_reg
        self.target_value = result_value

    def gen_instr(self):
        block = BaseBlock(self.entry, self.extension, True)
        try:
            print(self.trigger_inst._solution)
            use_reg = self.trigger_inst['RS1']
            block.inst_list.append(Instruction(f'add {use_reg}, {self.dep_reg}, a0'))
        except Exception as e:
            pass
        block.inst_list.append(self.trigger_inst)
        self._add_inst_block(block)

class SpecGoLoadInitBlock(LoadInitBlock):
    def __init__(self, depth, extension, output_path, init_block_list, delay_block, trigger_block, random_block, mode):
        super().__init__(depth, extension, output_path, init_block_list, mode)
        self.delay_block = delay_block
        self.trigger_block = trigger_block
        self.random_block = random_block

    def _compute_trigger_param(self):
        trigger_inst = self.trigger_block.trigger_inst
        try:
            imm = trigger_inst['IMM']
        except Exception:
            imm = 0

        return {'A0':self.trigger_block.target_value - self.dep_reg_result - imm}

    def _simulate_dep_reg_result(self):
        dump_result = inst_simlutor(self.baker, [self, self.delay_block, self.random_block])
        return dump_result[self.delay_block.result_reg]

    def gen_instr(self):
        self._gen_init_code()
        self.dep_reg_result = self._simulate_dep_reg_result()
        self.trigger_param = self._compute_trigger_param()

        if len(self.trigger_param) != 0:
            a0_data_asm = RawInstruction(f'.dword {self.trigger_param["A0"]}')
            if 'SP' in self.GPR_init_list:
                self.data_list[-2] = a0_data_asm
            else:
                self.data_list[-1] = a0_data_asm
