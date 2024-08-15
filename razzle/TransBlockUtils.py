import os
import random
import sys
import copy
from enum import *
from BuildManager import *
from SectionUtils import *
from SectionManager import *

from payload.Instruction import *
from payload.MagicDevice import *
from payload.Block import *

class BaseBlockType(Enum):
    NULL = auto()
    INT = auto()
    FLOAT = auto()
    LOAD_STORE = auto()
    AMO = auto()
    CSR = auto()
    SYSTEM = auto()
    JMP = auto()
    CALLRET = auto()
    BRANCH = auto()

class BaseBlock:
    def __init__(self, name, extension, mutate, len=None):
        self.name = name
        self.extension = extension
        self.mutate = mutate
        self.len = len
        
        self.inst_list = []
        self.previous = []
        self.succeed = []

        self.previous_inited = set()
        self.need_inited = set()
        self.succeed_inited = set()
    
    def gen_random_block(self, normal_reg, taint_reg, normal_freg, taint_freg):
        for _ in range(self.len):
            inst_list = self.gen_random_inst(normal_reg, taint_reg, normal_freg, taint_freg)
            if self.get_inst_len() + len(inst_list) * 4 > self.len * 4:
                break
            else:
                self.inst_list.extend(inst_list)
        
        return [self]

    def get_block_list(self):
        return [self]
    
    def gen_random_inst(self, normal_reg, taint_reg, normal_freg, taint_freg):
        raise Exception("the gen_random_instr has not been implemented!!!")
    
    def get_random_reg(self, field, normal_reg, taint_reg):
        if field.endswith('RD'):
            if len(normal_reg) != 0:
                reg = random.choice(list(normal_reg))
                taint = False
            else:
                reg = random.choice(list(taint_reg))
                taint = True
        else:
            if len(normal_reg) == 0:
                reg = random.choice(list(taint_reg))
                taint = True
            elif len(taint_reg) == 0:
                reg = random.choice(list(normal_reg))
                taint = False
            elif random.random() < 0.15:
                reg = random.choice(list(normal_reg))
                taint = False
            else:
                reg = random.choice(list(taint_reg))
                taint = True
        
        return reg, taint
    
    def filter_reg(self, instr, reg):
        if instr['NAME'].startswith('C.'):
            return set(rvc_reg_range) & reg
        else:
            return reg
    
    def filter_freg(self, instr, freg):
        if instr['NAME'].startswith('C.'):
            return set(rvc_float_range) & freg
        else:
            return freg
    
    def set_instr_reg(self, instr, field, normal_reg, taint_reg):
        taint = False
        
        if instr.has(field):
            if field.startswith('F'):
                reg, taint = self.get_random_reg(field, self.filter_freg(instr, normal_reg), self.filter_freg(instr, taint_reg))
            else:
                reg, taint = self.get_random_reg(field, self.filter_reg(instr, normal_reg), self.filter_reg(instr, taint_reg))
            instr[field] = reg
        return taint

    def _gen_branch_to(self, normal_reg, taint_reg, target):
        extension = [extension_i for extension_i in [
            'RV_I', 'RV64_I', 'RV_C', 'RV32_C', 'RV64_C'] if extension_i in self.extension]
        instr = rand_instr(
            instr_extension=extension, instr_category=['BRANCH'])
        instr.set_label_constraint([target])
        instr.solve()

        self.set_instr_reg(instr, 'RS1', normal_reg, taint_reg)
        self.set_instr_reg(instr, 'RS2', normal_reg, taint_reg)

        self.inst_list.append(instr)
    
    def _gen_jump_to(self, target):
        instr = Instruction(f'jal zero, {target}')
        self.inst_list.append(instr)

    def compute_succeed_inited(self):
        if not self.mutate:
            return
        dest = ['RD', 'FRD']
        src  = ['RS1', 'RS2', 'FRS1', 'FRS2', 'FRS3']
        for inst in self.inst_list:
            for field in src:
                if inst.has(field):
                    reg = inst[field]
                    if reg not in self.succeed_inited:
                        self.need_inited.add(reg)
                    self.succeed_inited.add(reg)
            
            for field in dest:
                if inst.has(field):
                    self.succeed_inited.add(inst[field])
            

    def compute_need_inited(self):
        iter_valid = False

        previous_inited = set()
        if len(self.previous) != 0:
            previous_inited = self.previous[0].succeed_inited
            for block in self.previous[1:]:
                previous_inited.intersection_update(block.succeed_inited)

        if len(self.previous_inited) < len(previous_inited):
            iter_valid = True
            self.previous_inited = previous_inited
            self.succeed_inited.update(previous_inited)
            if self.mutate:
                self.need_inited.difference_update(self.previous_inited)
        
        return iter_valid

    def add_previous(self, node):
        self.previous.append(node)
        node.succeed.append(self)
    
    def add_succeed(self, node):
        self.succeed.append(node)
        node.previous.append(self)
        
    def get_inst_len(self):
        sum = 0
        for inst in self.inst_list:
            sum += inst.get_len()
        return sum

class RandomBlock(BaseBlock):
    def __init__(self, name, extension):
        super().__init__(name, extension, True)
        self.gen_func = [
            RandomBlock._gen_atomic,
            RandomBlock._gen_float_arithmetic,
            RandomBlock._gen_float_arithmetic,
            RandomBlock._gen_int_arithmetic,
            RandomBlock._gen_int_arithmetic,
            RandomBlock._gen_load_store,
        ]
    
    def _gen_int_arithmetic(self):
        extension = [extension_i for extension_i in [
            'RV64_C', 'RV64_M', 'RV64_I', 'RV_M', 'RV_I', 'RV_C'] if extension_i in self.extension]
        instr = rand_instr(instr_extension=extension, instr_category=['ARITHMETIC'])
        def instr_c_name(name):
            return name not in ['LA', 'LI']
        instr.add_constraint(instr_c_name,['NAME'])
        instr.solve()
        return [instr]
    
    def _gen_load_address(self):
        instr_la = Instruction()
        instr_la.set_label_constraint(['random_data_block_page_base', 'page_fault_data_block_page_base', 'access_fault_data_block_page_base'])
        instr_la.set_name_constraint(['LA'])
        instr_la.solve()
        return instr_la
    
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
    
    def _gen_system(self):
        extension = [extension for extension in [
            'RV_I', 'RV64_I'] if extension in self.extension]
        instr = rand_instr(instr_extension=extension,
                           instr_category=['SYSTEM', 'SYNCH'])
        instr.solve()
        return [instr]

    def gen_instr(self):
        for _ in range(random.randint(3,6)):
            gen_func = random.choice(self.gen_func)
            self.inst_list.extend(gen_func(self))
            if len(self.inst_list) >= 6:
                break

class NullBlock(BaseBlock):
    def __init__(self, name, extension, mutate, len):
        super().__init__(name, extension, mutate, len)
        self.block_type = BaseBlockType.NULL
        self.inst_list = [Instruction('c.nop')] * (len//2)

class IntBlock(BaseBlock):
    def __init__(self, name, extension, mutate, len):
        super().__init__(name, extension, mutate, len)
        self.block_type = BaseBlockType.INT
    
    def gen_random_inst(self, normal_reg, taint_reg, normal_freg, taint_freg):
        extension = [extension_i for extension_i in [
            'RV64_C', 'RV64_M', 'RV64_I', 'RV_M', 'RV_I', 'RV_C'] if extension_i in self.extension]
        instr = rand_instr(instr_extension=extension, instr_category=['ARITHMETIC'])
        
        def instr_c(name):
            return name not in ['LA', 'LI']
        instr.add_constraint(instr_c,['NAME'])
        instr.solve()

        taint_rs1 = self.set_instr_reg(instr, 'RS1', normal_reg, taint_reg)
        taint_rs2 = self.set_instr_reg(instr, 'RS2', normal_reg, taint_reg)
        taint_rd = self.set_instr_reg(instr, 'RD', normal_reg, taint_reg)
        if instr.has('RD'):
            if not taint_rd and (taint_rs1 or taint_rs2):
                normal_reg.difference_update({instr['RD']})
                taint_reg.add(instr['RD'])
            if taint_rd and (not taint_rs1 and not taint_rs2):
                taint_reg.difference_update({instr['RD']})
                normal_reg.add(instr['RD'])
        return [instr]

class FloatBlock(BaseBlock):
    def __init__(self, name, extension, mutate, len):
        super().__init__(name, extension, mutate, len)
        self.block_type = BaseBlockType.FLOAT
    
    def gen_random_block(self, normal_reg, taint_reg, normal_freg, taint_freg):
        if len(taint_reg) != 0:
            frd, _ = self.get_random_reg('FRD', normal_freg, taint_freg)
            rs = random.choice(list(taint_reg))
            instr = Instruction(f'fcvt.s.lu {frd.lower()}, {rs.lower()}')
            taint_freg.add(frd)
            self.inst_list.append(instr)
        return super().gen_random_block(normal_reg, taint_reg, normal_freg, taint_freg)
    
    def gen_random_inst(self, normal_reg, taint_reg, normal_freg, taint_freg):
        extension = [extension for extension in [
            'RV_D', 'RV64_D',
            'RV_F', 'RV64_F',
            'RV32_C_F', 'RV_C_D'
        ] if extension in self.extension]

        instr = rand_instr(instr_extension=extension,instr_category=['FLOAT'])
        instr.solve()

        taint_rs1 = self.set_instr_reg(instr, 'RS1', normal_reg, taint_reg)
        taint_rs2 = self.set_instr_reg(instr, 'RS2', normal_reg, taint_reg)
        taint_rd  = self.set_instr_reg(instr, 'RD', normal_reg, taint_reg)
        taint_frs1 = self.set_instr_reg(instr, 'FRS1', normal_freg, taint_freg)
        taint_frs2 = self.set_instr_reg(instr, 'FRS2', normal_freg, taint_freg)
        taint_frs3 = self.set_instr_reg(instr, 'FRS3', normal_freg, taint_freg)
        taint_frd = self.set_instr_reg(instr, 'FRD', normal_freg, taint_freg)
        
        if instr.has('RD'):
            if not taint_rd and (taint_rs1 or taint_rs2 or taint_frs1 or taint_frs2 or taint_frs3):
                normal_reg.difference_update({instr['RD']})
                taint_reg.add(instr['RD'])
            elif taint_rd and not (taint_rs1 or taint_rs2 or taint_frs1 or taint_frs2 or taint_frs3):
                taint_reg.difference_update({instr['RD']})
                normal_reg.add(instr['RD'])
        
        if instr.has('FRD'):
            if not taint_frd and (taint_rs1 or taint_rs2 or taint_frs1 or taint_frs2 or taint_frs3):
                normal_freg.difference_update({instr['FRD']})
                taint_freg.add(instr['FRD'])
            elif taint_frd and not (taint_rs1 or taint_rs2 or taint_frs1 or taint_frs2 or taint_frs3):
                taint_freg.difference_update({instr['FRD']})
                normal_freg.add(instr['FRD'])

        return [instr]

class RetCallBlock(BaseBlock):
    def __init__(self, name, extension, mutate, len):
        super().__init__(name, extension, mutate, len)
        self.block_type = BaseBlockType.CALLRET
    
    def gen_random_block(self, normal_reg, taint_reg, normal_freg, taint_freg):
        self.base_reg, taint_reg = self.get_random_reg('RD', normal_reg - {'RA'}, taint_reg - {'RA'})
        if taint_reg:
            normal_reg.add(self.base_reg)
            taint_reg.update_difference(self.base_reg)
        self.base_reg = self.base_reg.lower()
        self.inst_list.append(Instruction(f'auipc {self.base_reg}, 0'))
        self.inst_list.append(Instruction(f'add ra, {self.base_reg}, zero'))
        self.jalr_offset = 8
        return super().gen_random_block(normal_reg, taint_reg, normal_freg, taint_freg)

    def gen_random_inst(self, normal_reg, taint_reg, normal_freg, taint_freg):
        def update_jalr_offset(inst):
            self.jalr_offset += (2 if inst['NAME'].startswith('C.') else 4)
        
        inst_list = []
        if random.random() < 0.5:
            inst = Instruction(f'jalr zero, 0(ra)')
            update_jalr_offset(inst)
            inst['IMM'] = self.jalr_offset
            inst_list.append(inst)
        else:
            inst = Instruction(f'jalr ra, 0({self.base_reg})')
            update_jalr_offset(inst)
            inst['IMM'] = self.jalr_offset
            inst_list.append(inst)
            inst = Instruction(f'add ra, {self.base_reg}, zero')
            update_jalr_offset(inst)
            inst_list.append(inst)
        
        return inst_list

class JMPBlock(BaseBlock):
    def __init__(self, name, extension, mutate, len):
        super().__init__(name, extension, mutate, len)
        self.block_type = BaseBlockType.JMP
        self.block_list = [self]
    
    def gen_random_block(self, normal_reg, taint_reg, normal_freg, taint_freg):
        self.base_reg, taint_reg = self.get_random_reg('RD', normal_reg - {'RA'}, taint_reg - {'RA'})
        if taint_reg:
            normal_reg.add(self.base_reg)
            taint_reg.update_difference(self.base_reg)
        self.base_reg = self.base_reg.lower()
        self.inst_list.append(Instruction(f'auipc {self.base_reg}, 0'))
        self.jalr_offset = 4
        for _ in range(5):
            self.gen_random_inst()
        self.block_list[-1].inst_list.append(Instruction('c.nop'))
        return self.block_list
    
    def get_block_list(self):
        return self.block_list
    
    def gen_random_inst(self):
        def update_jalr_offset(inst):
            self.jalr_offset += (2 if inst['NAME'].startswith('C.') else 4)
        
        if random.random() < 0.75:
            inst = Instruction(f'jalr zero, 0({self.base_reg})')
            update_jalr_offset(inst)
            inst['IMM'] = self.jalr_offset
            self.block_list[-1].inst_list.append(inst)
        else:
            block = BaseBlock(f'{self.name}_{len(self.block_list)}', self.extension, True)
            inst = Instruction(f'jal zero, {block.name}')
            update_jalr_offset(inst)
            self.block_list[-1].inst_list.append(inst)
            self.block_list[-1].add_succeed(block)
            self.block_list.append(block)

class BranchBlock(BaseBlock):
    def __init__(self, name, extension, mutate, len):
        super().__init__(name, extension, mutate, len)
        self.block_type = BaseBlockType.BRANCH
        self.block_list = [self]
    
    def gen_random_block(self, normal_reg, taint_reg, normal_freg, taint_freg):
        for _ in range(6):
            self.gen_random_inst(normal_reg, taint_reg, normal_freg, taint_freg)
        self.block_list[-1].inst_list.append(Instruction('c.nop'))
        return self.block_list
    
    def get_block_list(self):
        return self.block_list
    
    def gen_random_inst(self, normal_reg, taint_reg, normal_freg, taint_freg):
        block = BaseBlock(f'{self.name}_{len(self.block_list)}', self.extension, True)
        inst = Instruction()
        inst.set_category_constraint(['BRANCH'])
        inst.set_label_constraint([block.name])
        inst.solve()
        _ = self.set_instr_reg(inst, 'RS1', normal_reg, taint_reg)
        _ = self.set_instr_reg(inst, 'RS2', normal_reg, taint_reg)
        self.block_list[-1].inst_list.append(inst)
        self.block_list[-1].add_succeed(block)
        self.block_list.append(block)

class MemBlock(BaseBlock):
    def __init__(self, name, extension, mutate, len):
        super().__init__(name, extension, mutate, len)
    
    def gen_random_block(self, normal_reg, taint_reg, normal_freg, taint_freg):
        inst_list = self.gen_random_inst(normal_reg, taint_reg, normal_freg, taint_freg)
        self.inst_list.extend(inst_list)

        return [self]
    
    def _gen_load_address(self, normal_reg, taint_reg):
        instr_la = Instruction()
        instr_la.set_label_constraint(['random_data_block_page_base', 'channel_page_base_0',\
            'channel_page_base_1', 'channel_page_base_2'])
        instr_la.set_name_constraint(['LA'])
        instr_la.solve()

        taint_rd = self.set_instr_reg(instr_la, 'RD', normal_reg, taint_reg)
        if taint_rd:
            taint_reg.difference_update({instr_la['RD']})
            normal_reg.add(instr_la['RD'])

        inst_list = [instr_la]
        
        if random.random() < 0.5:
            reg, taint = self.get_random_reg('RS1', normal_reg, taint_reg)
            inst_mask = Instruction(f'andi {reg.lower()}, {reg.lower()}, 0x7f8')
            inst_offset = Instruction(f'add {instr_la["RD"].lower()}, {instr_la["RD"].lower()}, {reg.lower()}')
            inst_list.extend([inst_mask, inst_offset])
            if taint:
                taint_reg.add(instr_la['RD'])
                normal_reg.difference_update({instr_la['RD']})
        
        return inst_list   

class AMOBlock(MemBlock):
    def __init__(self, name, extension, mutate, len):
        super().__init__(name, extension, mutate, len)
        self.block_type = BaseBlockType.AMO
    
    def gen_random_inst(self, normal_reg, taint_reg, normal_freg, taint_freg):
        extension = [extension_i for extension_i in ['RV_A', 'RV64_A'] if extension_i in self.extension]
        inst_list = self._gen_load_address(normal_reg, taint_reg)
        
        la_rd = inst_list[0]['RD']
        def instr_c_reg(rs1):
            return rs1 == la_rd
        normal_reg = copy.copy(normal_reg)
        taint_reg = copy.copy(taint_reg)
        normal_reg.difference({la_rd})
        taint_reg.difference({la_rd})
        
        for _ in range(4):
            instr = rand_instr(instr_extension=extension, instr_category=[
                'AMO_LOAD', 'AMO_STORE', 'AMO'], imm_range=range(-0x800, 0x7f8, 8))
            instr.add_constraint(instr_c_reg, ['RS1'])
            instr.solve()

            _ = self.set_instr_reg(instr, 'RS2', normal_reg, taint_reg)
            taint_rd = self.set_instr_reg(instr, 'RD', normal_reg, taint_reg)
            if instr.has('RD'):
                if la_rd in taint_reg and not taint_rd:
                    normal_reg.difference_update({instr['RD']})
                    taint_reg.add(instr['RD'])
                elif la_rd not in taint_reg and taint_rd:
                    taint_reg.difference_update({instr['RD']})
                    normal_reg.add(instr['RD'])

            inst_list.append(instr)

            if random.random() < 0.3:
                break

        return inst_list

class LSUBlock(MemBlock):
    def __init__(self, name, extension, mutate, len):
        super().__init__(name, extension, mutate, len)
        self.block_type = BaseBlockType.LOAD_STORE
    
    def gen_random_inst(self, normal_reg, taint_reg, normal_freg, taint_freg):
        extension = [extension_i for extension_i in [
            'RV_I', 'RV64_I', 'RV_D', 'RV64_D', 'RV_F', 'RV64_F',
            'RV_C', 'RV32_C', 'RV64_C', 'RV32_C_F', 'RV_C_D'] if extension_i in self.extension]
        inst_list = self._gen_load_address(normal_reg, taint_reg)

        la_rd = inst_list[0]['RD']
        def instr_c_reg(rs1):
            return rs1 == la_rd
        normal_reg = copy.copy(normal_reg)
        taint_reg = copy.copy(taint_reg)
        normal_reg.difference({la_rd})
        taint_reg.difference({la_rd})
        
        for _ in range(4):
            instr = rand_instr(instr_extension=extension, instr_category=[
                'LOAD', 'STORE', 'FLOAT_LOAD', 'FLOAT_STORE'], imm_range=range(-0x800, 0x7f8, 8))
            instr.add_constraint(instr_c_reg, ['RS1'])
            instr.solve()

            _ = self.set_instr_reg(instr, 'RS2', normal_reg, taint_reg)
            taint_rd = self.set_instr_reg(instr, 'RD', normal_reg, taint_reg)
            if instr.has('RD'):
                if la_rd in taint_reg and not taint_rd:
                    normal_reg.difference_update({instr['RD']})
                    taint_reg.add(instr['RD'])
                elif la_rd not in taint_reg and taint_rd:
                    taint_reg.difference_update({instr['RD']})
                    normal_reg.add(instr['RD'])

            inst_list.append(instr)

            if random.random() < 0.3:
                break

        return inst_list

class CSRBlock(BaseBlock):
    def __init__(self, name, extension, mutate, len):
        super().__init__(name, extension, mutate, len)
        self.block_type = BaseBlockType.CSR
    
    def gen_random_inst(self, normal_reg, taint_reg, normal_freg, taint_freg):
        extension = [extension for extension in [
            'RV_ZICSR'] if extension in self.extension]

        instr = rand_instr(instr_extension=extension,
                           instr_category=['CSR'])
        instr.solve()

        taint_rs1 = self.set_instr_reg(instr, 'RS1', normal_reg, taint_reg)
        taint_rd = self.set_instr_reg(instr, 'RD', normal_reg, taint_reg)
        if instr.has('RD'):
            if taint_rs1 and not taint_rd:
                normal_reg.difference_update({instr['RD']})
                taint_reg.add(instr['RD'])
            elif not taint_rs1 and taint_rd:
                taint_reg.difference_update({instr['RD']})
                normal_reg.add(instr['RD'])

        return [instr]

class SystemBlock(BaseBlock):
    def __init__(self, name, extension, mutate, len):
        super().__init__(name, extension, mutate, len)
        self.block_type = BaseBlockType.SYSTEM
    
    def gen_random_inst(self, normal_reg, taint_reg, normal_freg, taint_freg):
        extension = [extension for extension in [
            'RV_I', 'RV64_I'] if extension in self.extension]
        instr = rand_instr(instr_extension=extension,
                           instr_category=['SYSTEM', 'SYNCH'])
        instr.solve()
        return [instr]

class TransBlock:
    def __init__(self, name, extension, output_path):
        self.name = name
        self.output_path = output_path
        self.entry = self.name + "_entry"
        self.inst_block_list = []
        self.data_list = []
        self.extension = extension
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
            if line.startswith('//'):
                continue
            if line.startswith('.option'):
                continue
            file_list_format.append(line)
        
        return file_list_format

    def _load_inst_str(self, str_list, mutate=False):
        if len(str_list) == 0:
            block = BaseBlock(self.entry, self.extension, mutate)
        elif str_list[0].endswith(':'):
            block = BaseBlock(str_list[0][0:-1], self.extension, mutate)
            str_list.pop(0)
        else:
            block = BaseBlock(self.entry, self.extension, mutate)

        for line in str_list:
            if line.endswith(':'):
                self._add_inst_block(block)
                block = BaseBlock(line[0:-1], self.extension, mutate)
                continue
            
            if block.mutate:
                block.inst_list.append(Instruction(line))
            else:
                block.inst_list.append(RawInstruction(line))

        self._add_inst_block(block)
    
    def _load_data_str(self, str_list):
        for line in str_list:
            self.data_list.append(RawInstruction(line))
    
    def _add_inst_block(self, block):
        if len(self.inst_block_list) != 0:
            self.inst_block_list[-1].add_succeed(block)
        self.inst_block_list.append(block)
    
    def _add_inst_block_list(self, block_list):
        if len(self.inst_block_list) != 0:
            self.inst_block_list[-1].add_succeed(block_list[0])
        self.inst_block_list.extend(block_list)
    
    def _compute_need_inited(self):
        for block in self.inst_block_list:
            block.compute_succeed_inited()
        
        iter_valid = True
        while iter_valid:
            iter_valid = False
            for block in self.inst_block_list:
                iter_valid = iter_valid or block.compute_need_inited() 

        self.need_inited = set()
        for block in self.inst_block_list:
            self.need_inited.update(block.need_inited)
        self.succeed_inited = self.inst_block_list[-1].succeed_inited
    
    def _inited_posted_process(self, previous_inited):
        self.need_inited = self.need_inited - previous_inited
        self.succeed_inited.update(previous_inited)
    
    def _get_inst_len(self):
        inst_len = 0
        for block in self.inst_block_list:
            inst_len += block.get_inst_len()
        return inst_len

    def gen_instr(self):
        raise "the gen_instr has not been implementation!!!"
    
    def gen_inst_asm(self):
        inst_asm_list = []
        rvc_open = True
        inst_asm_list.append('.option rvc\n')
        # inst_asm_list.append(f"{self.name}:\n")
        for block in self.inst_block_list:
            inst_asm_list.append(f'{block.name}:\n')
            for inst in block.inst_list:
                rvc_type = inst.is_rvc()
                if rvc_type != rvc_open:
                    rvc_open = rvc_type
                    inst_asm_list.append('.option rvc\n' if rvc_open else '.option norvc\n')
                inst_asm_list.append(inst.to_asm()+'\n')
            inst_asm_list.append('\n')
        
        return inst_asm_list
    
    def gen_data_asm(self):
        data_asm_list = []
        # data_asm_list.append(f"{self.name}_data:\n")
        for item in self.data_list:
            data_asm_list.append(item.to_asm() + "\n")
        
        return data_asm_list

    def gen_asm(self):
        inst_asm_list = self.gen_inst_asm()
        data_asm_list = self.gen_data_asm()
        return inst_asm_list, data_asm_list

    def work(self):
        return len(self.extension) > 0

    def clear(self):
        self.inst_block_list = []
        self.data_list = []
    
    def record_fuzz(self):
        raise Exception("the record_fuzz is not implemented!!!")

class TransBaseManager(SectionManager):
    def __init__(self, config, extension, output_path):
        super().__init__(config)
        self.extension = extension
        self.output_path = output_path
    
    def gen_block(self):
        raise Exception("gen_block has not been implemented!!!")
    
    def _set_section(self, text_section, data_section, block_list):
        for block in block_list:
            inst_list, data_list = block.gen_asm()
            text_section.add_inst_list(inst_list)
            data_section.add_inst_list(data_list)
    
    def _distribute_address(self):
        offset = 0
        length = Page.size
        self.section[".text_swap"].get_bound(
            self.virtual_memory_bound[0][0] + offset, self.memory_bound[0][0] + offset, length
        )
    
    def _dump_trans_block(self, folder, block_list, return_front):
        return_front_file = os.path.join(folder, 'return_front')
        with open(return_front_file, "wt") as file:
            file.write("True" if return_front else "False")

        for block in block_list:
            block.store_template(folder)
    
    def add_symbol_table(self, symbol_table):
        self.symbol_table = symbol_table
    
    def register_swap_idx(self, swap_idx):
        self.swap_idx = swap_idx
    
    def register_memory_region(self, mem_region):
        self.mem_region = mem_region
    
    def _base_record_fuzz(self, block_list):
        record = {}
        record['swap_id'] = self.swap_idx
        record['block_info'] = {}
        record['mode'] = self.mode
        for block in block_list:
            key, value = block.record_fuzz()
            record['block_info'][key] = value
        return record

    def record_fuzz(self):
        raise Exception("the record_fuzz is not implemented!!!")
    
    def _write_headers(self, f):
        f.write(f'#include "parafuzz.h"\n')
        f.write(f'#include "fuzzing.h"\n')
        f.write('\n')


class FuzzSection(Section):
    def __init__(self, name, flag):
        super().__init__(name, flag)
        self.inst_list = []

    def add_inst_list(self, list):
        self.inst_list.extend(list)
        self.inst_list.append("\n")
    
    def clear(self):
        self.inst_list = []

    def _generate_body(self):
        return self.inst_list

class TransDataSection(FuzzSection):
    def __init__(self, name, flag):
        super().__init__(name, flag)
        self.inst_list = ['.space 0x200\n']

    def add_inst_list(self, list):
        self.inst_list.extend(list)
        self.inst_list.append("\n")
    
    def clear(self):
        self.inst_list = ['.space 0x200\n']

    def _generate_body(self):
        return self.inst_list

def inst_simlutor(baker, block_list):
    if not os.path.exists(baker.output_path):
        os.makedirs(baker.output_path)

    file_name = os.path.join(baker.output_path, "tmp.S")
    with open(file_name, "wt") as file:
        file.write('#include "boom_conf.h"\n')
        file.write('#include "encoding.h"\n')
        file.write('#include "parafuzz.h"\n')
        
        text_section = FuzzSection(
            ".text", Flag.U | Flag.X | Flag.R
        )
        data_section = FuzzSection(
            ".data", Flag.U | Flag.W | Flag.R
        )

        text_section.add_inst_list(
            [
                f"li t0, 0x8000000a00007800\n",
                "csrw mstatus, t0\n",
            ]
        )

        for block in block_list:
            text_list, data_list = block.gen_asm()
            text_section.add_inst_list(text_list)
            data_section.add_inst_list(data_list)
        
        file.writelines(text_section.generate_asm())
        file.writelines(data_section.generate_asm())

    gen_elf = ShellCommand(
        "riscv64-unknown-elf-gcc",
        [
            "-march=rv64gc_zicsr",
            "-mabi=lp64f",
            "-mcmodel=medany",
            "-nostdlib",
            "-nostartfiles",
            "-I$RAZZLE_ROOT/template",
            "-I$RAZZLE_ROOT/template/trans",
            "-T$RAZZLE_ROOT/template/tmp/link.ld",
        ],
    )
    baker.add_cmd(gen_elf.gen_cmd([file_name, "-o", "$OUTPUT_PATH/tmp"]))

    inst_cnt = ShellCommand(
        "riscv64-unknown-elf-objdump",
        ["-d", "$OUTPUT_PATH/tmp", "| grep -cE '^[[:space:]]+'"],
    )
    baker.add_cmd(inst_cnt.gen_result("INST_CNT"))

    gen_dump = ShellCommand(
        "spike-solve", ["$OUTPUT_PATH/tmp", "$INST_CNT", "$OUTPUT_PATH/dump"]
    )
    baker.add_cmd(gen_dump.gen_cmd())
    baker.run()

    with open(os.path.join(baker.output_path, "dump"), "rt") as file:
        reg_lines = file.readlines()
        dump_reg = {}
        for reg_line in reg_lines:
            key, value = reg_line.strip().split()
            dump_reg[key] = int(value, base=16)
        # print(dump_reg)
    return dump_reg

def random_choice(random_prob):
    prob = 0
    prob_data = random.random()
    for rand_type, rand_prob in random_prob.items():
        prob += rand_prob
        if prob_data < prob:
            return rand_type
    else:
        return rand_type