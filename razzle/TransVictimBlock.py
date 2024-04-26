import os
import random
import sys
from enum import Enum
from BuildManager import *
from SectionUtils import *
from SectionManager import *
from TransBlockUtils import *
from TransBodyBlock import *

from payload.Instruction import *
from payload.MagicDevice import *
from payload.Block import *
    
class TriggerBlock(TransBlock):
    def __init__(self, extension, output_path, dep_reg, ret_label, train_label):
        super().__init__('trigger_block', extension, output_path)
        self.dep_reg = dep_reg
        self.ret_label  = ret_label
        self.train_label = train_label
        self.trigger_type = TriggerType.random_choice()
    
    def gen_instr(self):
        block = BaseBlock(self.entry, self.extension, True)
        inst = Instruction()
        inst.set_extension_constraint(self.extension)

        match(self.trigger_type):
            case TriggerType.LOAD_STORE:
                block.inst_list.append(Instruction(f'add a0, {self.dep_reg}, a0'))
                inst.set_category_constraint(['LOAD', 'STORE', 'FLOAT_LOAD', 'FLOAT_STORE'])
                inst.solve()
                inst['RS1'] = 'A0'
                inst['IMM'] = down_align(inst['IMM'], 8)
            case TriggerType.LOAD_STORE_SP:
                block.inst_list.append(Instruction(f'add sp, {self.dep_reg}, a0'))
                inst.set_category_constraint(['LOAD_SP', 'STORE_SP'])
                inst.solve()
                inst['IMM'] = down_align(inst['IMM'], 8)
            case TriggerType.AMO:
                block.inst_list.append(Instruction(f'add a0, {self.dep_reg}, a0'))
                inst.set_category_constraint(['AMO'])
                inst.solve()
                inst['RS1'] = 'A0'
            case TriggerType.V4:
                block.inst_list.append(Instruction(f'add a0, {self.dep_reg}, a0'))
                inst.set_name_constraint(['SD'])
                inst.solve()
                inst['RS1'] = 'A0'
                inst['RS2'] = 'ZERO'
            case TriggerType.BIM:
                block.inst_list.append(Instruction(f'add a0, {self.dep_reg}, a0'))
                inst.set_category_constraint(['BRANCH'])
                inst.set_label_constraint([self.ret_label, self.train_label])
                inst.solve()
                inst['RS1'] = 'A0'
                inst['RS2'] = self.dep_reg
            case TriggerType.BTB:
                block.inst_list.append(Instruction(f'add a0, {self.dep_reg}, a0'))
                inst.set_name_constraint(['JALR', 'C.JALR', 'C.JR'])
                inst.set_category_constraint(['JUMP'])
                inst.solve()
                inst['RS1'] = 'A0'
            case TriggerType.RSB:
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
            case TriggerType.ARITHMETIC:
                block.inst_list.append(Instruction(f'add a0, {self.dep_reg}, a0'))
                inst.set_category_constraint(['ARITHMETIC'])
                inst.solve()
                inst['RS1'] = 'A0'
            case TriggerType.FLOAT:
                block.inst_list.append(Instruction(f'add a0, {self.dep_reg}, a0'))
                inst.set_category_constraint(['FLOAT'])
                inst.solve()
                inst['RS1'] = 'A0'
            case _:
                raise "the trigger type is invalid"
    
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

class EncodeBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('encode_block', extension, output_path)
        # self.leak_kind = random.choice(["cache", "FPUport", "LSUport"])
        self.leak_kind = random.choice(["cache"])

    def _gen_block_end(self):

        inst_exit = [
            "encode_exit:",
            "INFO_TEXE_END",
            f"j run_time_loop",
        ]
        self._load_inst_str(inst_exit)

    def gen_instr(self):
        match (self.leak_kind):
            case "cache" | "FPUport" | "LSUport":
                self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], f"template/trans/encode_block.{self.leak_kind}.text.S"), mutate=True)
            case _:
                raise f"leak_kind cannot be {self.leak_kind}"
            
        self._gen_block_end()

class LoadInitVictimBlock(LoadInitDelayBlock):
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
            case TriggerType.LOAD_STORE | TriggerType.LOAD_STORE_SP:
                address_base = random.choice(['secret_page_base', 'random_data_block_page_base'])
                trigger_param = f'{address_base} - {hex(up_align(self.dep_reg_result, 8))}'
            case TriggerType.AMO:
                address_base = random.choice(['secret_page_base', 'random_data_block_page_base'])
                trigger_param = f'{address_base} - {hex(self.dep_reg_result)} + {hex(down_align(random.randint(-0x800, 0x7ff), 8))}'
            case TriggerType.V4:
                trigger_param = f'access_secret_block_target_offset - {hex(self.dep_reg_result)}'
            case TriggerType.BIM:
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
            case TriggerType.BTB | TriggerType.RSB:
                trigger_inst_imm = trigger_inst['IMM'] if trigger_inst.has('IMM') else 0
                trigger_param = f'{self.ret_label} - {hex(self.dep_reg_result)} - {hex(trigger_inst_imm)}'
            case TriggerType.ARITHMETIC | TriggerType.FLOAT | TriggerType.JMP:
                trigger_param = random.randint(0, 2**64-1)
            case _:
                raise Exception("the trigger type is invalid")

        return {'A0':trigger_param}

class TransVictimManager(TransBaseManager):
    def __init__(self, config, extension, victim_privilege, virtual, output_path, trans_frame, depth):
        super().__init__(config, extension, victim_privilege, virtual, output_path)
        self.trans_frame = trans_frame
        self.depth = depth
    
    def gen_block(self):
        self.delay_block = DelayBlock(self.extension, self.output_path)
        self.return_block = ReturnBlock(self.extension, self.output_path)
        self.access_secret_block = AccessSecretBlock(self.extension, self.output_path)
        self.encode_block = EncodeBlock(self.extension, self.output_path)

        self.delay_block.gen_instr()
        self.return_block.gen_instr()
        self.access_secret_block.gen_instr()
        self.encode_block.gen_instr()

        self.trigger_block = TriggerBlock(self.extension, self.output_path, self.delay_block.result_reg, self.return_block.entry, self.access_secret_block.entry)
        self.trigger_block.gen_instr()

        block_list = [self.delay_block, self.trigger_block, self.access_secret_block, self.encode_block, self.return_block]
        self.load_init_block = LoadInitVictimBlock(self.depth, self.extension, self.output_path, block_list, self.delay_block, self.trigger_block)

        self.load_init_block.gen_instr()

        inst_len = self.load_init_block._get_inst_len() + self.delay_block._get_inst_len()\
              + self.trigger_block._get_inst_len() - 1
        nop_inst_len = ((inst_len + 16 + 8 - 1) // 8 * 8 - inst_len) * 2
        
        self.nop_block = NopBlock(self.extension, self.output_path, nop_inst_len)
        self.nop_block.gen_instr()

    def _generate_sections(self):
        if len(self.section) != 0:
            return

        text_swap_section = self.section[".text_swap"] = FuzzSection(
            ".text_swap", Flag.U | Flag.X | Flag.R
        )

        empty_section = FuzzSection(
            "", 0
        )

        self._set_section(text_swap_section, self.trans_frame.data_frame_section,[self.load_init_block])
        self._set_section(text_swap_section, empty_section, [self.nop_block, self.delay_block, self.trigger_block])

        do_follow = True
        if self.trigger_block.trigger_type == TriggerType.BIM and self.trigger_block.trigger_inst['LABEL'] == self.access_secret_block.entry:
            do_follow = False
        else:
            if self.trigger_block.trigger_type == TriggerType.BTB:
                tend_follow = False
            else:
                tend_follow = True

            if tend_follow:
                do_follow = random.choice([True, True, True, True, False])
            else:
                do_follow = random.choice([True, False, False, False, False])
        
        if do_follow:
            self._set_section(text_swap_section, self.trans_frame.data_frame_section, [self.access_secret_block])
            self._set_section(text_swap_section, empty_section, [self.encode_block, self.return_block])
        else:
            self._set_section(text_swap_section, empty_section, [self.return_block])
            self._set_section(text_swap_section, self.trans_frame.data_frame_section, [self.access_secret_block])
            self._set_section(text_swap_section, empty_section, [self.encode_block])

            




        

