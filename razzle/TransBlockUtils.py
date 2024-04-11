import os
import random
import sys
from BuildManager import *
from SectionUtils import *

from payload.Instruction import *
from payload.MagicDevice import *
from payload.Block import *

class BaseBlock:
    def __init__(self, name, extension, graph, mutate):
        self.name = name
        self.extension = extension
        self.graph = graph
        self.mutate = mutate
        self.inst_list = []

    def _get_data_base(self):
        return self.graph['random_data_block_1'].base_label
    
    def _gen_load_address(self):
        instr_la = Instruction()
        instr_la.set_label_constraint(self._get_data_base())
        instr_la.set_name_constraint(['LA'])
        instr_la.solve()
        return instr_la

    def _gen_int_arithmetic(self):
        extension = [extension_i for extension_i in [
            'RV64_C', 'RV64_M', 'RV64_I', 'RV_M', 'RV_I', 'RV_C'] if extension_i in self.extension]
        instr = rand_instr(instr_extension=extension, instr_category=['ARITHMETIC'])
        def instr_c_name(name):
            return name not in ['LA']
        instr.add_constraint(instr_c_name,['NAME'])
        instr.solve()
        return [instr]
    
    def _gen_load_store(self):
        extension = [extension_i for extension_i in [
            'RV_I', 'RV64_I', 'RV_D', 'RV64_D', 'RV_F', 'RV64_F',
            'RV_C', 'RV32_C', 'RV64_C', 'RV32_C_F', 'RV_C_D'] if extension_i in self.extension]
        instr_la = self._gen_load_address()

        rd = instr_la['RD']
        def instr_c_reg(reg):
            return reg == rd
        instr = rand_instr(instr_extension=extension, instr_category=[
            'LOAD', 'STORE', 'FLOAT_LOAD', 'FLOAT_STORE'], imm_range=range(-0x800, 0x7ff))
        instr.add_constraint(instr_c_reg, ['RS1'])
        instr.solve()

        return [instr_la, instr]

    def _gen_atomic(self):
        extension = [extension_i for extension_i in ['RV_A', 'RV64_A'] if extension_i in self.extension]
        instr_la = self._gen_load_address()
        
        instr_off = Instruction()
        instr_off.set_name_constraint(['ADDI'])
        offset = random.randint(-0x800, 0x7ff)
        instr_off.set_imm_constraint(range(offset, offset+1))
        rd = instr_la['RD']
        def c_rd_rd1(r1, r2):
            return r1 == rd and r2 == rd
        instr_off.add_constraint(c_rd_rd1, ['RD', 'RS1'])
        instr_off.solve()

        def reg_c(rs1):
            return rs1 == rd
        instr_amo = rand_instr(instr_extension=extension, instr_category=['AMO'])
        instr_amo.add_constraint(reg_c, ['RS1'])
        instr_amo.solve()

        return [instr_la, instr_off, instr_amo]
    
    def _gen_float_arithmetic(self):
        extension = [extension for extension in [
            'RV_D', 'RV64_D',
            'RV_F', 'RV64_F',
            'RV32_C_F', 'RV_C_D'
        ] if extension in self.extension]

        instr = rand_instr(instr_extension=extension,instr_category=['FLOAT'])
        instr.solve()

        return [instr]

    def _gen_csr(self):
        extension = [extension for extension in [
            'RV_ZICSR'] if extension in self.extension]

        instr = rand_instr(instr_extension=extension,
                           instr_category=['CSR'])
        instr.solve()

        return [instr]
    
    def _gen_system(self):
        extension = [extension for extension in [
            'RV_I', 'RV64_I'] if extension in self.extension]
        instr = rand_instr(instr_extension=extension,
                           instr_category=['SYSTEM', 'SYNCH'])
        instr.solve()
        return [instr]

    def gen_asm(self):
        str_list = []
        str_list.append(f'{self.name}:\n')
        for inst in self.inst_list:
            str_list.append(inst.to_asm()+'\n')
        return str_list

class RandomBlock(BaseBlock):
    def __init__(self, name, extension, graph, transient):
        super().__init__(name, extension, graph, True)
        self.transient = transient
        self.gen_func = [
            RandomBlock._gen_atomic,
            RandomBlock._gen_float_arithmetic,
            RandomBlock._gen_float_arithmetic,
            RandomBlock._gen_int_arithmetic,
            RandomBlock._gen_int_arithmetic,
            RandomBlock._gen_load_store,
        ]
        if transient:
            self.gen_func.extend(
                [
                    RandomBlock._gen_system,
                    RandomBlock._gen_csr,
                ]
            )

    def gen_instr(self):
        for _ in range(random.randint(3,6)):
            gen_func = random.choice(self.gen_func)
            self.inst_list.extend(gen_func(self))
            if len(self.inst_list) > 6:
                break

class TransBlock:
    def __init__(self, name, depth, extension, fuzz_param, output_path):
        self.name = f'{name}_{depth}'
        self.depth = depth
        self.entry = self.name + "_entry"
        self.inst_block_list = []
        self.data_list = []
        self.extension = extension
        self.strategy = fuzz_param["strategy"]
        self.transient = False
        self.baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]},
            os.path.join(output_path, self.name),
        )

    def _load_inst_file(self, file_name, mutate = False):
        file_list_format = self._load_file_asm(file_name)
        self._load_inst_str(file_list_format, mutate)
    
    def _load_data_file(self, file_name):
        file_list_format = self._load_file_asm(file_name)
        self._load_data_str(file_list_format)

    def _load_file_asm(self, file_name):
        with open(file_name, "rt") as file:
            file_list = file.readlines()
        
        file_list_format = []
        for line in file_list:
            line = line.strip()
            if line == '':
                continue
            if line.startswith('//') or line.startswith('#'):
                continue
            file_list_format.append(line)
        
        return file_list_format

    def _load_inst_str(self, str_list, mutate=False):
        if str_list[0].endswith(':'):
            block = BaseBlock(str_list[0][0:-1], self.extension, None, mutate)
            str_list.pop(0)
        else:
            block = BaseBlock(self.entry, self.extension, None, mutate)

        for line in str_list:
            if line.endswith(':'):
                self.inst_block_list.append(block)
                block = BaseBlock(line[0:-1], self.extension, None, mutate)
                continue
            
            if block.mutate:
                block.inst_list.append(Instruction(line))
            else:
                block.inst_list.append(RawInstruction(line))

        self.inst_block_list.append(block)
    
    def _load_data_str(self, str_list):
        for line in str_list:
            self.data_list.append(RawInstruction(line))

    def gen_instr(self, graph):
        match self.strategy:
            case "default":
                self.gen_default(graph)
            case "random":
                self.gen_random(graph)
            case _:
                self.gen_strategy(graph)
    
    def _gen_random(self, graph, block_cnt=3):
        block_list = []
        for i in range(block_cnt):
            block = RandomBlock(f'{self.name}_{i}', self.extension, graph, self.transient)
            block.gen_instr()
            block_list.append(block)

        start_p = 0
        while(start_p + 2 < block_cnt - 1):
            end_p = random.randint(start_p + 2, block_cnt -2)
            block_list[start_p].out_instr = new_branch_to(self.extension,block_list[end_p].name)
            block_list[end_p].out_instr = new_jump_to(block_list[start_p + 1].name)
            block_list[end_p -1].out_instr = new_jump_to(block_list[end_p + 1].name)
            start_p = end_p + 1

        return block_list

    def gen_random(self, graph):
        raise "Error: gen_random not implemented!"

    def gen_default(self, graph):
        raise "Error: gen_default not implemented!"

    def gen_strategy(self, graph):
        raise "Error: gen_dstrategy not implemented!"

    def gen_asm(self):
        inst_asm_list = []
        inst_asm_list.append(f"{self.name}:\n")
        for block in self.inst_block_list:
            inst_asm_list.extend(block.gen_asm())

        data_asm_list = []
        data_asm_list.append(f"{self.name}_data:\n")
        for item in self.data_list:
            data_asm_list.append(item.to_asm() + "\n")
        return inst_asm_list, data_asm_list

    def work(self):
        return len(self.extension) > 0