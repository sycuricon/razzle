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
    def __init__(self, extension, output_path, dep_reg, ret_label, train_label, li_offset):
        super().__init__('trigger_block', extension, output_path)
        self.dep_reg = dep_reg
        self.ret_label  = ret_label
        self.train_label = train_label
        self.li_offset = li_offset
    
    def gen_instr(self):
        block = BaseBlock(self.entry, self.extension, True)
        inst = Instruction()
        inst.set_extension_constraint(self.extension)

        if not self.li_offset and random.random() < 0.5:
            self.trigger_type = TriggerType.V4
            block.inst_list.append(Instruction(f'add a0, {self.dep_reg}, a0'))
            inst.set_name_constraint(['SD'])
            inst.solve()
            inst['RS1'] = 'A0'
            inst['RS2'] = 'ZERO'
        elif random.random() < 0.7:
            type_prob = {
                TriggerType.JALR: 0.35,
                TriggerType.BRANCH: 0.25,
                TriggerType.RETURN: 0.25,
                TriggerType.JMP: 0.15
            }
            self.trigger_type = random_choice(type_prob)
            match(self.trigger_type):
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
                case _:
                    raise Exception("excepted trigger type")
        else:
            rand_data = random.random()
            if rand_data < 0.1:
                self.trigger_type = random.choice([TriggerType.EBREAK, TriggerType.ILLEGAL, TriggerType.ECALL])
                match(self.trigger_type):
                    case TriggerType.EBREAK:
                        inst = Instruction('ebreak')
                    case TriggerType.ILLEGAL:
                        inst = Instruction('illegal')
                    case TriggerType.ECALL:
                        inst = Instruction('ecall')
                    case _:
                        raise Exception("excepted trigger type")
            else:
                if rand_data < 0.4:
                    inst.set_category_constraint(['LOAD', 'FLOAT_LOAD', 'LOAD_SP'])
                    inst.solve()
                    if inst['CATEGORY'] == 'LOAD_SP':
                        block.inst_list.append(Instruction(f'add sp, {self.dep_reg}, a0'))
                    else:
                        block.inst_list.append(Instruction(f'add a0, {self.dep_reg}, a0'))
                        inst['RS1'] = 'A0'

                    
                    if inst['NAME'] in ['LB', 'LBU']:
                        self.trigger_type = random.choice([TriggerType.LOAD_ACCESS_FAULT, TriggerType.LOAD_PAGE_FAULT])
                    else:
                        type_prob = {
                            TriggerType.LOAD_MISALIGN: 0.2,
                            TriggerType.LOAD_ACCESS_FAULT: 0.4,
                            TriggerType.LOAD_PAGE_FAULT: 0.4
                        }
                        self.trigger_type = random_choice(type_prob)
                   
                    inst['IMM'] = down_align(inst['IMM'], 8)
                        
                elif rand_data < 0.7:
                    
                    inst.set_category_constraint(['STORE', 'FLOAT_STORE', 'STORE_SP'])
                    inst.solve()
                    if inst['CATEGORY'] == 'STORE_SP':
                        block.inst_list.append(Instruction(f'add sp, {self.dep_reg}, a0'))
                    else:
                        block.inst_list.append(Instruction(f'add a0, {self.dep_reg}, a0'))
                        inst['RS1'] = 'A0'

                    
                    if inst['NAME'] in ['SB', 'SBU']:
                        self.trigger_type = random.choice([TriggerType.STORE_ACCESS_FAULT, TriggerType.STORE_PAGE_FAULT])
                    else:
                        type_prob = {
                            TriggerType.STORE_MISALIGN: 0.2,
                            TriggerType.STORE_ACCESS_FAULT: 0.4,
                            TriggerType.STORE_PAGE_FAULT: 0.4
                        }
                        self.trigger_type = random_choice(type_prob)
                   
                    inst['IMM'] = down_align(inst['IMM'], 8)
                    
                else:

                    block.inst_list.append(Instruction(f'add a0, {self.dep_reg}, a0'))
                    inst.set_category_constraint(['AMO', 'AMO_LOAD', 'AMO_STORE'])
                    inst.solve()
                    inst['RS1'] = 'A0' 

                    type_prob = {
                        TriggerType.AMO_MISALIGN: 0.2,
                        TriggerType.AMO_ACCESS_FAULT: 0.4,
                        TriggerType.AMO_PAGE_FAULT: 0.4
                    }
                    self.trigger_type = random_choice(type_prob)
    
        self.trigger_inst = inst
        block.inst_list.append(inst)
        self._add_inst_block(block)

class AccessSecretBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('access_secret_block', extension, output_path)
        self.li_offset = True if random.random() < 0.8 else False

    def _gen_block_begin(self):
        inst_list_begin = [
            'INFO_TEXE_START',
        ]
        self._load_inst_str(inst_list_begin)
    
    def gen_instr(self):
        self._gen_block_begin()
        
        if self.li_offset:
            
            inst_list = [
                f'begin_access_secret:',
                'li t1, 0xfffffffffffff001',
                'la t0, trapoline',
                'add t0, t0, t1',
                'lb t0, 0(t0)',
            ]

        else:

            inst_list = [
                f'begin_access_secret:',
                f'ld t1, {self.name}_target_offset',
                'la t0, trapoline',
                'add t0, t0, t1',
                'lb t0, 0(t0)',
            ]
            
        data_list = [
            f'{self.name}_target_offset:',
            '.dword secret + LEAK_TARGET - trapoline',
        ]

        self._load_inst_str(inst_list)
        self._load_data_str(data_list)

        self.secret_reg = 'T0'
    
    def _get_inst_len(self):
        return 7 * 4

class EncodeBlock(TransBlock):
    def __init__(self, extension, output_path, secret_reg):
        super().__init__('encode_block', extension, output_path)
        self.leak_kind = random.choice(["cache"])
        self.secret_reg = secret_reg

    def _gen_block_end(self):

        inst_exit = [
            "encode_exit:",
            "INFO_TEXE_END",
            f"ebreak",
        ]
        self._load_inst_str(inst_exit)

    def gen_instr(self):
        match (self.leak_kind):
            case "cache" | "FPUport" | "LSUport":
                self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], f"template/trans/encode_block.{self.leak_kind}.text.S"), mutate=True)
            case _:
                self._gen_random(3)
            
        self._gen_block_end()

class LoadInitTriggerBlock(LoadInitBlock):
    def __init__(self, depth, extension, output_path, init_block_list, delay_block, trigger_block):
        super().__init__(depth, extension, output_path, init_block_list)
        self.delay_block = delay_block
        self.trigger_block = trigger_block
        self.ret_label = trigger_block.ret_label
        self.train_label = trigger_block.train_label

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
                trigger_param = f'access_secret_block_target_offset - {hex(self.dep_reg_result)}'
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
            case TriggerType.EBREAK | TriggerType.ILLEGAL | TriggerType.ECALL:
                trigger_param = None
            case _:
                raise Exception("the trigger type is invalid")

        return {'A0':trigger_param} if trigger_param != None else {}

    def _simulate_dep_reg_result(self):
        dump_result = inst_simlutor(self.baker, [self, self.delay_block])
        return dump_result[self.delay_block.result_reg]

    def gen_instr(self):
        self._gen_init_code()
        self.dep_reg_result = self._simulate_dep_reg_result()
        self.trigger_param = self._compute_trigger_param()

        if len(self.trigger_param) != 0:
            a0_data_asm = RawInstruction(f'.dword {self.trigger_param["A0"]}')
            if self.GPR_init_list[-1] == 'T0':
                self.data_list[-2] = a0_data_asm
            else:
                self.data_list[-1] = a0_data_asm

class SecretMigrateType(Enum):
    MEMORY = auto()
    CACHE = auto()
    LOAD_BUFFER = auto()

class SecretMigrateBlock(TransBlock):
    def __init__(self, extension, output_path, protect_gpr_list):
        super().__init__('secret_migrate_block', extension, output_path)
        self.protected_gpr_list = protect_gpr_list

    def gen_instr(self):
        secret_migrate_prob = {
            SecretMigrateType.MEMORY: 0.7,
            SecretMigrateType.CACHE: 0.2,
            SecretMigrateType.LOAD_BUFFER: 0.1
        }
        self.secret_migrate_type = random_choice(secret_migrate_prob)

        if len(self.protected_gpr_list) >= 30:
            self.secret_migrate_type = SecretMigrateType.MEMORY

        inst_list = []
        used_reg = random.choices(list(set(reg_range) - {'ZERO'} - set(self.protected_gpr_list)), k=2)
        used_reg = [reg.lower() for reg in used_reg]
        
        if self.secret_migrate_type == SecretMigrateType.MEMORY:
            inst_list.extend(['c.nop'] * 6)
        else:
            inst_list.extend(
                [
                    f'la {used_reg[0]}, secret',
                    f'ld {used_reg[1]}, 0({used_reg[0]})'
                ]
            )
        
        if self.secret_migrate_type == SecretMigrateType.LOAD_BUFFER:
            inst_list.extend(
                [
                    f'la {used_reg[0]}, dummy_data_block_data',
                    f'li {used_reg[1]}, 0x1000',
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
            inst_list.extend(['c.nop'] * 22)

        self._load_inst_str(inst_list)
    
    def _get_inst_len(self):
        return (22 + 6) * 2
        
class TransVictimManager(TransBaseManager):
    def __init__(self, config, extension, victim_privilege, virtual, output_path, data_section):
        super().__init__(config, extension, victim_privilege, virtual, output_path)
        self.data_section = data_section
    
    def gen_block(self):
        self.delay_block = DelayBlock(self.extension, self.output_path)
        self.delay_block.gen_instr()

        self.return_block = ReturnBlock(self.extension, self.output_path)
        self.return_block.gen_instr()

        self.access_secret_block = AccessSecretBlock(self.extension, self.output_path)
        self.access_secret_block.gen_instr()

        self.encode_block = EncodeBlock(self.extension, self.output_path, self.access_secret_block.secret_reg)
        self.encode_block.gen_instr()

        self.trigger_block = TriggerBlock(self.extension, self.output_path, self.delay_block.result_reg,\
            self.return_block.entry, self.access_secret_block.entry, self.access_secret_block.li_offset)
        self.trigger_block.gen_instr()

        block_list = [self.delay_block, self.trigger_block, self.access_secret_block, self.encode_block, self.return_block]
        self.load_init_block = LoadInitTriggerBlock(self.swap_idx, self.extension, self.output_path, block_list, self.delay_block, self.trigger_block)
        self.load_init_block.gen_instr()

        self.secret_migrate_block = SecretMigrateBlock(self.extension, self.output_path, self.load_init_block.GPR_init_list)
        self.secret_migrate_block.gen_instr()

        inst_len = self.load_init_block._get_inst_len() + self.delay_block._get_inst_len()\
              + self.secret_migrate_block._get_inst_len() + self.trigger_block._get_inst_len()
        if self.trigger_block.trigger_inst.is_rvc():
            inst_len -= 2
        else:
            inst_len -= 4
        nop_inst_len = (inst_len + 16*4 + 8 - 1) // 8 * 8 - inst_len
        
        self.nop_block = NopBlock(self.extension, self.output_path, nop_inst_len)
        self.nop_block.gen_instr()

        self.trigger_type = self.trigger_block.trigger_type

        do_follow = True
        if self.trigger_block.trigger_type == TriggerType.BRANCH and self.trigger_block.trigger_inst['LABEL'] == self.access_secret_block.entry:
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
    
    def dump_trigger_block(self, folder):
        need_inited = set()
        need_inited.update(self.delay_block.need_inited)
        need_inited.update(self.trigger_block.need_inited)
        load_init_block = copy.deepcopy(self.load_init_block)

        new_inst_list = []
        new_data_list = []
        old_inst_list = self.load_init_block.inst_block_list[0].inst_list
        old_data_list = self.load_init_block.data_list
        
        new_inst_list.append(old_inst_list[0])
        new_data_list.append(old_data_list[0])
        for inst, data in zip(old_inst_list[1:], old_data_list[1:]):
            if inst['NAME'] == 'C.LDSP':
                if inst['RD'] in need_inited:
                    new_inst_list.append(inst)
                    new_data_list.append(data)
            else:
                if inst['FRD'] in need_inited:
                    new_inst_list.append(inst)
                    new_data_list.append(data)
        
        load_init_block.inst_block_list[0].inst_list = new_inst_list
        load_init_block.data_list = new_data_list

        self._dump_trans_block(folder, [load_init_block, self.delay_block,\
            self.trigger_block], self.return_front)
        
        trigger_type_file = os.path.join(folder, 'trigger_type')
        with open(trigger_type_file, "wt") as file:
            file.write(f'{self.trigger_block.trigger_type}')
    
    def dump_leak_block(self, folder):
        self._dump_trans_block(folder, [self.load_init_block, self.secret_migrate_block, self.delay_block,\
            self.trigger_block, self.access_secret_block, self.encode_block], self.return_front)
        
        trigger_type_file = os.path.join(folder, 'trigger_type')
        with open(trigger_type_file, "wt") as file:
            file.write(f'{self.trigger_block.trigger_type}')
    
    def record_fuzz(self,file):
        file.write(f'trigger_type:\t{self.trigger_block.trigger_type}\t')
        file.write(f'trigger_inst:\t{self.trigger_block.trigger_inst.to_asm()}\t')
        file.write(f'return_front:\t{self.return_front}\n')

    def mutate(self):
        pass

    def _generate_sections(self):

        text_swap_section = self.section[".text_swap"] = FuzzSection(
            ".text_swap", Flag.U | Flag.X | Flag.R
        )

        self.section[".data_victim"] = self.data_section

        empty_section = FuzzSection(
            "", 0
        )

        self.data_section.clear()

        self._set_section(text_swap_section, self.data_section, [self.load_init_block])
        self._set_section(text_swap_section, empty_section, [self.secret_migrate_block ,self.nop_block, self.delay_block, self.trigger_block])
        
        if not self.return_front:
            self._set_section(text_swap_section, self.data_section, [self.access_secret_block])
            self._set_section(text_swap_section, empty_section, [self.encode_block, self.return_block])
        else:
            self._set_section(text_swap_section, empty_section, [self.return_block])
            self._set_section(text_swap_section, self.data_section, [self.access_secret_block])
            self._set_section(text_swap_section, empty_section, [self.encode_block])
    
    def need_train(self):
        return TriggerType.need_train(self.trigger_block.trigger_type)

            




        

