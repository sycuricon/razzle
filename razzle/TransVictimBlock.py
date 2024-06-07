import os
import random
import sys
import copy
from enum import *
from BuildManager import *
from SectionUtils import *
from SectionManager import *
from TransBlockUtils import *
from TransBodyBlock import *

from payload.Instruction import *
from payload.MagicDevice import *
from payload.Block import *
    
class TriggerBlock(TransBlock):
    def __init__(self, extension, output_path, dep_reg, ret_label, train_label, trigger_type):
        super().__init__('trigger_block', extension, output_path)
        self.dep_reg = dep_reg
        self.ret_label  = ret_label
        self.train_label = train_label
        self.trigger_type = trigger_type
    
    def gen_default(self):
        block = BaseBlock(self.entry, self.extension, True)
        inst = Instruction()
        inst.set_extension_constraint(self.extension)

        match(self.trigger_type):
            case TriggerType.V4:
                block.inst_list.append(Instruction(f'add a0, {self.dep_reg}, a0'))
                inst.set_name_constraint(['SD'])
                inst.solve()
                inst['RS1'] = 'A0'
                inst['RS2'] = 'ZERO'
            case TriggerType.BRANCH:
                block.inst_list.append(Instruction(f'add a0, {self.dep_reg}, a0'))
                inst.set_category_constraint(['BRANCH'])
                inst.set_label_constraint([self.ret_label, self.train_label])
                inst.solve()
                inst['RS1'] = 'A0'
                inst['RS2'] = self.dep_reg
            case TriggerType.JALR:
                block.inst_list.append(Instruction(f'add a0, {self.dep_reg}, a0'))
                inst.set_name_constraint(['JALR', 'C.JALR', 'C.JR'])
                inst.set_category_constraint(['JUMP'])
                inst.solve()
                inst['RS1'] = 'A0'
                if random.random() < 0.3:
                    inst['RD'] = 'RA'
            case TriggerType.RETURN:
                block.inst_list.append(Instruction(f'add ra, {self.dep_reg}, a0'))
                inst.set_name_constraint(['JALR', 'C.JR'])
                inst.set_category_constraint(['JUMP'])
                inst.solve()
                inst['RS1'] = 'RA'
                inst['RD'] = 'ZERO'
            case TriggerType.JMP:
                inst.set_name_constraint(['JAL', 'C.J', 'C.JAL'])
                inst.set_category_constraint(['JUMP'])
                inst.set_label_constraint([self.ret_label])
                inst.solve()
                if random.random() < 0.7:
                    inst['RD'] = 'RA'
            case TriggerType.EBREAK:
                inst = Instruction('ebreak')
            case TriggerType.ILLEGAL:
                inst = Instruction('illegal')
            case TriggerType.ECALL:
                inst = Instruction('ecall')
            case TriggerType.LOAD_ACCESS_FAULT|TriggerType.LOAD_MISALIGN|TriggerType.LOAD_PAGE_FAULT|TriggerType.LOAD:
                inst.set_category_constraint(['LOAD', 'FLOAT_LOAD', 'LOAD_SP'])
                inst.solve()
                if inst['CATEGORY'] == 'LOAD_SP':
                    block.inst_list.append(Instruction(f'add sp, {self.dep_reg}, a0'))
                else:
                    block.inst_list.append(Instruction(f'add a0, {self.dep_reg}, a0'))
                    inst['RS1'] = 'A0'

                if inst['NAME'] in ['LB', 'LBU'] and self.trigger_type == TriggerType.LOAD_MISALIGN:
                    self.trigger_type = random.choice([TriggerType.LOAD_ACCESS_FAULT, TriggerType.LOAD_PAGE_FAULT, TriggerType.LOAD])
                
                inst['IMM'] = down_align(inst['IMM'], 8)
            case TriggerType.STORE_ACCESS_FAULT|TriggerType.STORE_MISALIGN|TriggerType.STORE_PAGE_FAULT|TriggerType.STORE:
                inst.set_category_constraint(['STORE', 'FLOAT_STORE', 'STORE_SP'])
                inst.solve()
                if inst['CATEGORY'] == 'STORE_SP':
                    block.inst_list.append(Instruction(f'add sp, {self.dep_reg}, a0'))
                else:
                    block.inst_list.append(Instruction(f'add a0, {self.dep_reg}, a0'))
                    inst['RS1'] = 'A0'
                
                if inst['NAME'] in ['SB', 'SBU'] and self.trigger_type == TriggerType.STORE_MISALIGN:
                    self.trigger_type = random.choice([TriggerType.STORE_ACCESS_FAULT, TriggerType.STORE_PAGE_FAULT, TriggerType.STORE])
                
                inst['IMM'] = down_align(inst['IMM'], 8)
            case TriggerType.AMO_ACCESS_FAULT|TriggerType.AMO_MISALIGN|TriggerType.AMO_PAGE_FAULT|TriggerType.AMO:
                block.inst_list.append(Instruction(f'add a0, {self.dep_reg}, a0'))
                inst.set_category_constraint(['AMO', 'AMO_LOAD', 'AMO_STORE'])
                inst.solve()
                inst['RS1'] = 'A0' 
            case TriggerType.INT:
                inst.set_category_constraint(['ARITHMETIC'])
                def name_c(name):
                    return name not in ['LA', 'Li']
                inst.add_constraint(name_c, ['NAME'])
                inst.solve()
            case TriggerType.FLOAT:
                inst.set_category_constraint(['FLOAT'])
                inst.solve()
                if inst.has('RS1'):
                    inst['RS1'] = self.dep_reg
    
        self.trigger_inst = inst
        block.inst_list.append(inst)
        self._add_inst_block(block)
    
    def store_template(self, folder):
        super().store_template(folder)
        type_name = os.path.join(folder, f'{self.name}.type')
        with open(type_name, "wt") as file:
            file.write(f'{self.trigger_type}')
    
    def load_template(self, template):
        super().load_template(template)
        with open(f'{template}.type', "rt") as file:
            self.trigger_type = eval(file.readline().strip())
            self.trigger_inst = self.inst_block_list[0].inst_list[-1]

class AccessSecretBlock(TransBlock):
    def __init__(self, extension, output_path, virtual, li, mask):
        super().__init__('access_secret_block', extension, output_path)
        self.virtual = virtual
        self.li_offset = li
        self.mask = mask
    
    def store_template(self, folder):
        type_name = os.path.join(folder, f'{self.name}.type')
        with open(type_name, "wt") as file:
            file.write(f'{self.li_offset}\n')
            file.write(f'{hex(self.address)}\n')
    
    def load_template(self, template):
        with open(f'{template}.type', "rt") as file:
            self.li_offset = eval(file.readline().strip())
            self.address = eval(file.readline().strip())
        self.gen_code()
    
    def gen_code(self):
        trapoline_address = 0x5000 if self.virtual else 0x80005000

        if self.li_offset:
            
            inst_list = [
                f'li s0, {hex(self.address - trapoline_address)}',
                f'la t1, trapoline',
                f'add t1, t1, s0',
                'lb s0, 0(t1)',            ]

        else:

            inst_list = [
                f'la s0, {self.name}_target_offset',
                f'ld s0, 0(s0)',
                f'la t1, trapoline',
                f'add t1, t1, s0',
                'lb s0, 0(t1)',
            ]
            
        data_list = [
            f'{self.name}_target_offset:',
            f'.dword {self.address - trapoline_address}',
        ]

        self._load_inst_str(inst_list, mutate=True)
        self._load_data_str(data_list)

        self.secret_reg = 'S0'
    
    def gen_default(self):
        self.mask = (1 << self.mask) - 1
        self.rand_mask = (1 << 64) - 1 - self.mask
        self.address = 0x4001 if self.virtual else 0x80004001
        self.address = (self.address & self.mask) | (random.randint(0, (2<<64)-1) & self.rand_mask)
        self.gen_code()

class EncodeType(Enum):
    FUZZ_FRONTEND = auto()
    FUZZ_BACKEND = auto()
    FUZZ_PIPELINE = auto()
    FUZZ_DEFAULT = auto()

class EncodeBlock(TransBlock):
    def __init__(self, extension, output_path, secret_reg, strategy, block_len=None, block_num=None):
        super().__init__('encode_block', extension, output_path)
        self.secret_reg = secret_reg
        assert strategy in [EncodeType.FUZZ_FRONTEND, EncodeType.FUZZ_BACKEND,\
            EncodeType.FUZZ_PIPELINE, EncodeType.FUZZ_DEFAULT]
        self.strategy = strategy
        self.block_len = block_len
        self.block_num = block_num
        self.encode_block_list = []
        self.encode_list = []
        self.encode_block_begin = 0
        self.encode_block_end = 0
    
    def _gen_block_begin(self):

        inst_list = [
            "INFO_VCTM_END",
            "INFO_TEXE_START"
        ]

        self._load_inst_str(inst_list)
    
    def _gen_block_end(self):

        inst_len = self._get_inst_len()
        inst_dummy = [
            "encode_nop_fill:",
        ]
        inst_dummy.extend(['c.nop' for _ in range((192 - inst_len)//2)])
        self._load_inst_str(inst_dummy)

        inst_exit = [
            "encode_exit:",
            "INFO_TEXE_END",
            f"ebreak",
        ]
        self._load_inst_str(inst_exit)

    def _gen_random(self):
        kind_class = {
            BaseBlockType.INT:IntBlock,
            BaseBlockType.FLOAT:FloatBlock,
            BaseBlockType.LOAD_STORE:LSUBlock,
            BaseBlockType.JMP:JMPBlock,
            BaseBlockType.CALLRET:RetCallBlock,
            BaseBlockType.BRANCH:BranchBlock,
            BaseBlockType.AMO:AMOBlock,
            BaseBlockType.CSR:CSRBlock,
            BaseBlockType.SYSTEM:SystemBlock
        }

        self.encode_block_list = []
        self.encode_list = []
        self.encode_block_begin = 0
        self.encode_block_end = 0

        normal_reg = copy.copy(reg_range[1:])
        normal_reg = set(normal_reg)
        normal_reg.remove(self.secret_reg)
        taint_reg = set()
        normal_freg = set(float_range)
        taint_freg = set()

        if self.strategy == EncodeType.FUZZ_BACKEND:
            taint_reg.add(self.secret_reg)

        block = BaseBlock(f'{self.name}_0', self.extension, True)
        self.encode_block_list.append(block)
        self.inst_block_list.append(block)
        match self.strategy:
            case EncodeType.FUZZ_FRONTEND:
                block.inst_list.append(Instruction(f'xor {self.secret_reg}, {self.secret_reg}, {self.secret_reg}'))
                block.inst_list.append(Instruction(f'auipc t0, 0x0'))
                block.inst_list.append(Instruction(f'add t0, t0, {self.secret_reg}'))
                block.inst_list.append(Instruction(f'jalr zero, 12(t0)'))
            case EncodeType.FUZZ_PIPELINE:
                block.inst_list.append(Instruction(f'c.beqz {self.secret_reg}, encode_nop_fill'))
            case EncodeType.FUZZ_BACKEND:
                pass
            case _:
                raise Exception("the strategy type is invalid!!!!")

        self.encode_block_begin = 1
        self.encode_block_end = self.encode_block_begin + self.block_num
        self.encode_list = list(range(self.encode_block_begin, self.encode_block_end))

        match self.strategy:
            case EncodeType.FUZZ_FRONTEND:
                block_type_pool = [BaseBlockType.BRANCH, BaseBlockType.JMP, BaseBlockType.CALLRET, BaseBlockType.SYSTEM]
            case EncodeType.FUZZ_BACKEND:
                block_type_pool = [BaseBlockType.INT, BaseBlockType.FLOAT, BaseBlockType.LOAD_STORE, BaseBlockType.AMO]
                if self.trigger_type != TriggerType.V4:
                    block_type_pool.append(BaseBlockType.CSR)
            case EncodeType.FUZZ_PIPELINE:
                block_type_pool = [BaseBlockType.BRANCH, BaseBlockType.JMP, BaseBlockType.CALLRET, BaseBlockType.SYSTEM,\
                    BaseBlockType.INT, BaseBlockType.FLOAT, BaseBlockType.LOAD_STORE, BaseBlockType.AMO]
                if self.trigger_type != TriggerType.V4:
                    block_type_pool.append(BaseBlockType.CSR)
            case _:
                raise Exception("the strategy type is invalid!!!!")
        
        kind = BaseBlockType.NULL
        for i in range(self.encode_block_begin, self.encode_block_end):
            if kind == BaseBlockType.NULL:
                base_prob = 1.0 / len(block_type_pool)
                kind_prob = {key:base_prob for key in block_type_pool}
            else:
                base_prob = 0.5 / len(block_type_pool)
                kind_prob = {key:base_prob for key in block_type_pool}
                kind_prob[kind] += 0.5
            kind = random_choice(kind_prob)
            block = kind_class[kind](f'{self.name}_{i}', self.extension, True, self.block_len)
            self.encode_block_list.append(block)
            block_list = block.gen_random_block(normal_reg, taint_reg, normal_freg, taint_freg)
            self.inst_block_list.extend(block_list)

        self.loop = False
        if self.trigger_type != TriggerType.V4:
            block = BaseBlock(f'{self.name}_{self.block_num + 1}', self.extension, True)
            self.inst_block_list.append(block)
            block.inst_list.append(Instruction(f'jal zero, {self.encode_block_list[0].name}'))
            self.encode_block_list.append(block)
            self.loop = True

    def gen_default(self):
        self._gen_block_begin()

        match (self.strategy):
            case EncodeType.FUZZ_DEFAULT:
                pass
            case EncodeType.FUZZ_BACKEND|EncodeType.FUZZ_FRONTEND|EncodeType.FUZZ_PIPELINE:
                self._gen_random()
            
        self._gen_block_end()

    def leak_reduce(self, encode_list):
        self.inst_block_list = []
        self._gen_block_begin()

        self.inst_block_list.append(self.encode_block_list[0])
        for i in encode_list:
            self.inst_block_list.extend(self.encode_block_list[i].get_block_list())
        if self.encode_block_end == len(self.encode_block_list):
            self.inst_block_list.append(self.encode_block_list[-1])

        self._gen_block_end()

        self.encode_list = encode_list
    
    def break_loop(self):
        self.inst_block_list = []
        self._gen_block_begin()

        self.inst_block_list.append(self.encode_block_list[0])
        for i in self.encode_list:
            self.inst_block_list.extend(self.encode_block_list[i].get_block_list())

        self._gen_block_end()

    def mutate(self):
        if self.strategy == EncodeType.FUZZ_DEFAULT:
            pass
        else:
            self.inst_block_list = []
            self._gen_block_begin()
            self._gen_random(4)
            self._gen_block_end()
    
    def load_template(self, template):
        super().load_template(template)
        try:
            with open(f'{template}.type', "rt") as file:
                strategy = file.read().strip()
                if self.strategy == None:
                    self.strategy = strategy
                self.encode_block_list_type = []
                for line in file.readlines():
                    self.encode_block_list_type.append(eval(line.strip()))
        except:
            pass
    
    def store_template(self, folder):
        super().store_template(folder)
        with open(os.path.join(folder, f'{self.name}.type'), "wt") as file:
            file.write(f'{self.strategy}\n')
            for i in self.encode_list:
                file.write(f'{self.encode_block_list[i].block_type}\n')

class LoadInitTriggerBlock(LoadInitBlock):
    def __init__(self, depth, extension, output_path, init_block_list, delay_block, trigger_block, random_block):
        super().__init__(depth, extension, output_path, init_block_list)
        self.delay_block = delay_block
        self.trigger_block = trigger_block
        self.ret_label = trigger_block.ret_label
        self.train_label = trigger_block.train_label
        self.random_block = random_block

    def _compute_trigger_param(self):
        trigger_inst = self.trigger_block.trigger_inst
        trigger_type = self.trigger_block.trigger_type

        match(trigger_type):
            case TriggerType.LOAD_MISALIGN | TriggerType.STORE_MISALIGN:
                address_base = 'random_data_block_page_base'
                trigger_param = f'{address_base} - {self.dep_reg_result} + 1'
            case TriggerType.LOAD_ACCESS_FAULT | TriggerType.STORE_ACCESS_FAULT:
                address_base = 'access_fault_data_block_page_base'
                trigger_param = f'{address_base} - {self.dep_reg_result}'
            case TriggerType.LOAD_PAGE_FAULT | TriggerType.STORE_PAGE_FAULT:
                address_base = 'page_fault_data_block_page_base'
                trigger_param = f'{address_base} - {self.dep_reg_result}'
            case TriggerType.LOAD | TriggerType.STORE:
                address_base = 'random_data_block_page_base'
                trigger_param = f'{address_base} - {self.dep_reg_result}'
            case TriggerType.AMO:
                address_base = 'random_data_block_page_base'
                trigger_param = f'{address_base} - {hex(self.dep_reg_result)} + {hex(down_align(random.randint(-0x800, 0x7ff), 8))}'
            case TriggerType.AMO_MISALIGN:
                address_base = 'random_data_block_page_base'
                trigger_param = f'{address_base} - {hex(self.dep_reg_result)} + {hex(down_align(random.randint(-0x800, 0x7ff), 8))} + 1'
            case TriggerType.AMO_ACCESS_FAULT:
                address_base = 'access_fault_data_block_page_base'
                trigger_param = f'{address_base} - {hex(self.dep_reg_result)} + {hex(down_align(random.randint(-0x800, 0x7ff), 8))}'
            case TriggerType.AMO_PAGE_FAULT:
                address_base = 'page_fault_data_block_page_base'
                trigger_param = f'{address_base} - {hex(self.dep_reg_result)} + {hex(down_align(random.randint(-0x800, 0x7ff), 8))}'
            case TriggerType.V4:
                trigger_param = f'access_secret_block_target_offset - {hex(self.dep_reg_result)} - {trigger_inst["IMM"]}'
            case TriggerType.BRANCH:
                branch_success = trigger_inst['LABEL'] == self.ret_label
                match((branch_success, trigger_inst['NAME'])):
                    case (True, 'BEQ') | (False, 'BNE') | (False, 'BLT') | (True, 'BGE') | (False, 'BLTU') | (True, 'BGEU'):
                        trigger_param = '0'
                    case (False, 'BEQ') | (True, 'BNE'):
                        trigger_param = '1'
                    case (True, 'BLT') | (False, 'BGE'):
                        assert Unsigned2Signed(self.dep_reg_result) != -0x8000000000000000
                        trigger_param = '-1'
                    case (True, 'BLTU') | (False, 'BGEU'):
                        assert self.dep_reg_result != 0
                        trigger_param = '-1'
                    case (True, 'C.BEQZ') | (False, 'C.BNEZ'):
                        trigger_param = f'-{hex(self.dep_reg_result)}'
                    case (False, 'C.BEQZ') | (True, 'C.BNEZ'):
                        if self.dep_reg_result == 0:
                            trigger_param = '1'
                        else:
                            trigger_param = '0'
                    case _:
                        raise Exception(f"the branch name {trigger_inst['NAME']} is invalid")
            case TriggerType.JALR | TriggerType.RETURN:
                trigger_inst_imm = trigger_inst['IMM'] if trigger_inst.has('IMM') else 0
                trigger_param = f'{self.ret_label} - {hex(self.dep_reg_result)} - {hex(trigger_inst_imm)}'
            case TriggerType.JMP:
                trigger_param = f'{random.randint(0, 2**64-1)}'
            case TriggerType.EBREAK | TriggerType.ILLEGAL | TriggerType.ECALL | TriggerType.INT | TriggerType.FLOAT:
                trigger_param = None
            case _:
                raise Exception("the trigger type is invalid")

        return {'A0':trigger_param} if trigger_param != None else {}

    def _simulate_dep_reg_result(self):
        dump_result = inst_simlutor(self.baker, [self, self.delay_block, self.random_block])
        return dump_result[self.delay_block.result_reg]

    def gen_default(self):
        self._gen_init_code()
        self.dep_reg_result = self._simulate_dep_reg_result()
        self.trigger_param = self._compute_trigger_param()

        if len(self.trigger_param) != 0:
            a0_data_asm = RawInstruction(f'.dword {self.trigger_param["A0"]}')
            if 'SP' in self.GPR_init_list:
                self.data_list[-2] = a0_data_asm
            else:
                self.data_list[-1] = a0_data_asm

    def update_init_seq(self):
        need_inited = self._need_init_compute()
        has_inited = set(self.GPR_init_list) | set(self.float_init_list)
        need_inited.difference_update(has_inited)
        need_inited.difference_update({'ZERO'})

        len_need_inited = len(need_inited)

        has_sp = False
        if 'SP' in need_inited:
            need_inited.difference_update('SP')
            has_sp = True

        if len_need_inited != 0:
            float_init_list = []
            GPR_init_list = []
            for reg in need_inited:
                if reg.startswith('F'):
                    float_init_list.append(reg)
                else:
                    GPR_init_list.append(reg)
            
            inst_list = []
            data_list = []
            for freg in float_init_list:
                inst_list.append(Instruction(f"c.fldsp {freg.lower()}, 0(sp)"))
                data_list.append(RawInstruction(f".dword {hex(random.randint(0, 2**64))}"))
            for reg in GPR_init_list:
                inst_list.append(Instruction(f"c.ldsp {reg.lower()}, 0(sp)"))
                data_list.append(RawInstruction(f".dword {hex(random.randint(0, 2**64))}"))

            i = 1
            list_len = len(self.inst_block_list[0].inst_list)
            while i < list_len:
                if self.inst_block_list[0].inst_list[i].has('RD'):
                    break
                else:
                    i += 1
            self.inst_block_list[0].inst_list[i:i] = inst_list
            self.data_list[i:i] = data_list

            if has_sp:
                self.inst_block_list[0].inst_list.append(Instruction(f"c.ldsp sp, 0(sp)"))
                self.data_list.append(RawInstruction(f".dword {hex(random.randint(0, 2**64))}"))
            self.GPR_init_list.append('SP')

            for i, inst in enumerate(self.inst_block_list[0].inst_list[1:]):
                inst['IMM'] = i*8

            self.GPR_init_list.extend(GPR_init_list)
            self.float_init_list.extend(float_init_list)

    def load_template(self, template):
        super().load_template(template)
        self.update_init_seq()
        

class SecretMigrateType(Enum):
    MEMORY = auto()
    CACHE = auto()
    LOAD_BUFFER = auto()

class SecretMigrateBlock(TransBlock):
    def __init__(self, extension, output_path, protect_gpr_list, secret_migrate_type):
        super().__init__('secret_migrate_block', extension, output_path)
        self.protected_gpr_list = protect_gpr_list
        self.secret_migrate_type = secret_migrate_type

    def store_template(self, folder):
        type_name = os.path.join(folder, f'{self.name}.type')
        with open(type_name, "wt") as file:
            file.write(f'{self.secret_migrate_type}')
    
    def load_template(self, template):
        with open(f'{template}.type', "rt") as file:
            self.secret_migrate_type = eval(file.readline().strip())
        self.gen_code()
    
    def gen_code(self):
        if len(self.protected_gpr_list) >= 30:
            self.secret_migrate_type = SecretMigrateType.MEMORY

        inst_list = []
        used_reg = list(set(reg_range) - {'ZERO'} - set(self.protected_gpr_list))
        used_reg.sort()
        used_reg = list(map(str.lower, used_reg[0:2]))
        
        if self.secret_migrate_type == SecretMigrateType.MEMORY:
            inst_list.extend(['c.nop'] * 8)
        else:
            inst_list.extend(
                [
                    f'la {used_reg[0]}, secret',
                    f'ld {used_reg[1]}, 0({used_reg[0]})',
                    f'mv {used_reg[1]}, zero'
                ]
            )
        
        if self.secret_migrate_type == SecretMigrateType.LOAD_BUFFER:
            inst_list.extend(
                [
                    f'la {used_reg[0]}, dummy_data_block_data_top',
                    f'lui {used_reg[1]}, 0x1',
                    f'sd zero, 0({used_reg[0]})',
                    f'add {used_reg[0]}, {used_reg[0]}, {used_reg[1]}',
                    f'sd zero, 0({used_reg[0]})',
                    f'add {used_reg[0]}, {used_reg[0]}, {used_reg[1]}',
                    f'sd zero, 0({used_reg[0]})',
                    f'add {used_reg[0]}, {used_reg[0]}, {used_reg[1]}',
                    f'sd zero, 0({used_reg[0]})',
                ]
            )
        else:
            inst_list.extend(['c.nop'] * 20)

        self._load_inst_str(inst_list)

    def gen_default(self):
        self.gen_code()
    
    def _get_inst_len(self):
        return (20 + 8) * 2
        
class TransVictimManager(TransBaseManager):
    def __init__(self, config, extension, victim_privilege, virtual, output_path, data_section, trans_frame):
        super().__init__(config, extension, victim_privilege, virtual, output_path)
        self.data_section = data_section
        self.trans_frame = trans_frame
    
    def gen_block(self, config, strategy, template_path):
        assert strategy in [EncodeType.FUZZ_FRONTEND, EncodeType.FUZZ_BACKEND,\
            EncodeType.FUZZ_PIPELINE, EncodeType.FUZZ_DEFAULT]
        self.strategy = strategy

        if template_path is not None:
            template_list = os.listdir(template_path)
            with open(os.path.join(template_path, 'return_front'), 'rt') as file:
                return_front = eval(file.readline().strip())
            delay_template = None if 'delay_block.text' not in template_list else os.path.join(template_path, 'delay_block')
            secret_migrate_template = None if 'secret_migrate_block.type' not in template_list else os.path.join(template_path, 'secret_migrate_block')
            access_secret_template = None if 'access_secret_block.type' not in template_list else os.path.join(template_path, 'access_secret_block')
            encode_template = None if 'encode_block.text' not in template_list else os.path.join(template_path, 'encode_block')
            trigger_template = None if 'trigger_block.text' not in template_list else os.path.join(template_path, 'trigger_block')
            load_init_template = None if 'load_init_block.text' not in template_list else os.path.join(template_path, 'load_init_block')
        else:
            delay_template = None
            secret_migrate_template = None
            access_secret_template = None
            encode_template = None
            trigger_template = None
            load_init_template = None

        self.delay_block = DelayBlock(self.extension, self.output_path, config['delay_len'], config['delay_float_rate'], config['delay_mem'])
        self.delay_block.gen_instr(delay_template)

        self.return_block = ReturnBlock(self.extension, self.output_path)
        self.return_block.gen_instr(None)

        tmp_random_state = random.getstate()
        random.seed(config['access_seed'])
        self.access_secret_block = AccessSecretBlock(self.extension, self.output_path, self.virtual, config['access_secret_li'], config['access_secret_mask'])
        self.access_secret_block.gen_instr(access_secret_template)
        random.setstate(tmp_random_state)

        self.encode_block = EncodeBlock(self.extension, self.output_path, self.access_secret_block.secret_reg, self.strategy)

        self.trigger_block = TriggerBlock(self.extension, self.output_path, self.delay_block.result_reg,\
            self.return_block.entry, self.access_secret_block.entry, config['trigger_type'])
        self.trigger_block.gen_instr(trigger_template)

        self.encode_block.trigger_type = self.trigger_block.trigger_type
        self.encode_block.gen_instr(encode_template)

        block_list = [self.delay_block, self.trigger_block, self.access_secret_block, self.encode_block, self.return_block]
        self.load_init_block = LoadInitTriggerBlock(self.swap_idx, self.extension, self.output_path, block_list, self.delay_block, self.trigger_block, self.trans_frame.random_data_block)
        self.load_init_block.gen_instr(load_init_template)
        self.temp_load_init_block = self.load_init_block

        self.secret_migrate_block = SecretMigrateBlock(self.extension, self.output_path, self.load_init_block.GPR_init_list, config['secret_migrate_type'])
        self.secret_migrate_block.gen_instr(secret_migrate_template)

        inst_len = self.load_init_block._get_inst_len() + self.secret_migrate_block._get_inst_len()
        nop_inst_len = (inst_len + 16*4 + 64 - 1) // 64 * 64 - inst_len
        
        self.nop_block = NopBlock(self.extension, self.output_path, nop_inst_len)
        self.nop_block.gen_instr(None)

        self.trigger_type = self.trigger_block.trigger_type

        if template_path is None:
            do_follow = True
            if self.trigger_block.trigger_type == TriggerType.BRANCH and\
                self.trigger_block.trigger_inst['LABEL'] == self.access_secret_block.entry:
                do_follow = False
            elif self.trigger_block.trigger_type in [TriggerType.INT, TriggerType.FLOAT,\
                TriggerType.AMO, TriggerType.LOAD, TriggerType.STORE]:
                do_follow = False
            else:
                if self.trigger_block.trigger_type == TriggerType.JALR:
                    tend_follow = False
                else:
                    tend_follow = True

                if tend_follow:
                    do_follow = random.choice([True, True, True, True, False])
                else:
                    do_follow = random.choice([True, False, False, False, False])

            self.return_front = not do_follow
        else:
            self.return_front = return_front
    
    def store_template(self, folder):
        self._dump_trans_block(folder, [self.load_init_block, self.secret_migrate_block, self.delay_block,\
            self.trigger_block, self.access_secret_block, self.encode_block], self.return_front)
        
        trigger_type_file = os.path.join(folder, 'trigger_block.type')
        with open(trigger_type_file, "wt") as file:
            file.write(f'{self.trigger_block.trigger_type}')
    
    def leak_reduce(self, encode_list):
        self.encode_block.leak_reduce(encode_list)

    def mutate_access(self, config):
        random.seed(config['access_seed'])
        self.access_secret_block = AccessSecretBlock(self.extension, self.output_path, self.virtual, config['access_secret_li'], config['access_secret_mask'])
        self.access_secret_block.gen_instr(None)

        self.secret_migrate_block = SecretMigrateBlock(self.extension, self.output_path, self.load_init_block.GPR_init_list, config['secret_migrate_type'])
        self.secret_migrate_block.gen_instr(None)

        self.encode_block = EncodeBlock(self.extension, self.output_path, self.access_secret_block.secret_reg, EncodeType.FUZZ_DEFAULT)
        self.encode_block.trigger_type = self.trigger_block.trigger_type
        self.encode_block.gen_instr(None)

        self.load_init_block = copy.deepcopy(self.temp_load_init_block)

    def mutate_encode(self, config):
        random.seed(config['leak_seed'])
        self.encode_block = EncodeBlock(self.extension, self.output_path, self.access_secret_block.secret_reg, config['encode_fuzz_type'], config['encode_block_len'], config['encode_block_num'])
        self.encode_block.trigger_type = self.trigger_block.trigger_type
        self.encode_block.gen_instr(None)

        old_inst_len = self.load_init_block._get_inst_len()
        self.load_init_block = copy.deepcopy(self.temp_load_init_block)
        self.load_init_block.init_block_list = [self.delay_block, self.trigger_block, self.access_secret_block, self.encode_block, self.return_block]
        self.load_init_block.update_init_seq()
        new_inst_len = self.load_init_block._get_inst_len()

        self.nop_block = NopBlock(self.extension, self.output_path, self.nop_block.c_nop_len + old_inst_len - new_inst_len)
        self.nop_block.gen_instr(None)

    def record_fuzz(self, file):
        file.write(f'victim: {self.swap_idx}\n')
        file.write(f'\treturn_front: {self.return_front}\n')
        file.write(f'\ttrigger_type: {self.trigger_block.trigger_type}\t')
        file.write(f'\ttrigger_inst: {self.trigger_block.trigger_inst.to_asm()}\n')
        file.write(f'\tsecret_migrate_type: {self.secret_migrate_block.secret_migrate_type}\t')
        file.write(f'\taccess_secret_address: {hex(self.access_secret_block.address)}\n')
        file.write(f'\tencode_type: ')
        for i in self.encode_block.encode_list:
            file.write(f'{self.encode_block.encode_block_list[i].block_type} ')
        file.write('\n')

    def _generate_sections(self):

        text_swap_section = self.section[".text_swap"] = FuzzSection(
            ".text_swap", Flag.U | Flag.X | Flag.R
        )

        self.section[".data_victim"] = self.data_section

        empty_section = FuzzSection(
            "", 0
        )

        self.data_section.clear()

        self._set_section(empty_section, self.data_section, [self.access_secret_block])
        self._set_section(text_swap_section, self.data_section, [self.load_init_block])
        self._set_section(text_swap_section, empty_section, [self.secret_migrate_block ,self.nop_block, self.delay_block, self.trigger_block])
        
        if not self.return_front:
            self._set_section(text_swap_section, empty_section, [self.access_secret_block])
            self._set_section(text_swap_section, empty_section, [self.encode_block, self.return_block])
        else:
            self._set_section(text_swap_section, empty_section, [self.return_block])
            self._set_section(text_swap_section, empty_section, [self.access_secret_block])
            self._set_section(text_swap_section, empty_section, [self.encode_block])
    
    def need_train(self):
        return TriggerType.need_train(self.trigger_block.trigger_type)

            




        

