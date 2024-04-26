import os
import random
import sys
from enum import Enum
from BuildManager import *
from SectionUtils import *
from SectionManager import *
from TransBlockUtils import *
from TransVictimBlock import *

from payload.Instruction import *
from payload.MagicDevice import *
from payload.Block import *

class TriggerTTEBlock(TransBlock):
    def __init__(self, extension, output_path, dep_reg, ret_label):
        super().__init__('trigger_block', extension, output_path)
        self.dep_reg = dep_reg
        self.ret_label  = ret_label
        self.trigger_type = TriggerType.tte_random_choice()
    
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
            case TriggerType.LOAD_STORE_SP:
                block.inst_list.append(Instruction(f'add sp, {self.dep_reg}, a0'))
                inst.set_category_constraint(['LOAD_SP', 'STORE_SP'])
                inst.solve()
            case TriggerType.AMO:
                block.inst_list.append(Instruction(f'add a0, {self.dep_reg}, a0'))
                inst.set_category_constraint(['AMO'])
                inst.solve()
                inst['RS1'] = 'A0'
            case TriggerType.BIM:
                block.inst_list.append(Instruction(f'add a0, {self.dep_reg}, a0'))
                inst.set_category_constraint(['BRANCH'])
                inst.set_label_constraint([self.ret_label])
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
            case _:
                raise "the trigger type is invalid"
    
        self.trigger_inst = inst
        block.inst_list.append(inst)
        self._add_inst_block(block)

class LoadInitTTEBlock(LoadInitDelayBlock):
    def __init__(self, depth, extension, output_path, init_block_list, delay_block, trigger_block):
        super().__init__(depth, extension, output_path, init_block_list)
        self.delay_block = delay_block
        self.trigger_block = trigger_block
        self.ret_label = trigger_block.ret_label

    def _compute_trigger_param(self):
        trigger_inst = self.trigger_block.trigger_inst
        trigger_type = self.trigger_block.trigger_type

        match(trigger_type):
            case TriggerType.LOAD_STORE | TriggerType.LOAD_STORE_SP:
                address_base = 'secret_page_base'
                trigger_param = f'{address_base} - {hex(self.dep_reg_result)}'
            case TriggerType.AMO:
                address_base = 'secret_page_base'
                trigger_param = f'{address_base} - {hex(self.dep_reg_result)} + {hex(random.randint(-0x800, 0x7ff))}'
            case TriggerType.BIM:
                match(trigger_inst['NAME']):
                    case 'BEQ' | 'BGE' | 'BGEU':
                        trigger_param = '0'
                    case 'BNE':
                        trigger_param = '1'
                    case 'BLT':
                        assert Unsigned2Signed(self.dep_reg_result) != -0x8000000000000000
                        trigger_param = '-1'
                    case 'BLTU':
                        assert self.dep_reg_result != 0
                        trigger_param = '-1'
                    case 'C.BEQZ':
                        trigger_param = f'-{hex(self.dep_reg_result)}'
                    case 'C.BNEZ':
                        if self.dep_reg_result == 0:
                            trigger_param = '1'
                        else:
                            trigger_param = '0'
                    case _:
                        raise Exception(f"the branch name {trigger_inst['NAME']} is invalid")
            case TriggerType.BTB | TriggerType.RSB:
                trigger_inst_imm = trigger_inst['IMM'] if trigger_inst.has('IMM') else 0
                trigger_param = f'{self.ret_label} - {hex(self.dep_reg_result)} - {hex(trigger_inst_imm)}'
            case _:
                raise Exception("the trigger type is invalid")

        return {'A0': trigger_param}

class AdjustType(Enum):
    BRANCH = 0
    RETURN = 1
    CALL = 2
    CALL_LOOP = 3
    JALR = 4
    JMP = 5
    OTHER = 6

    def random_choice():
        return AdjustType(random.randint(0, 6))

class AdjustBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('adjust_block', extension, output_path)
    
    def _gen_block_begin(self):
        inst_list_begin = [
            'INFO_TEXE_START',
            'auipc t0, 0',
            'add ra, t0, zero'
        ]
        self._load_inst_str(inst_list_begin)
    
    def _gen_block_end(self):
        inst_exit = [
            "adjust_exit:",
            "INFO_TEXE_END",
            f"j run_time_loop",
        ]
        self._load_inst_str(inst_exit)

    def gen_instr(self):
        def update_jalr_offset(jalr_offset, inst):
            return jalr_offset + (2 if inst['NAME'].startswith('C.') else 4)

        def recover_t0_ra(inst, block, jalr_offset):
            if inst.has('RD'):
                if inst['RD'] == 'RA':
                    inst = Instruction('add ra, t0, zero')
                    block.inst_list.append(inst)
                    jalr_offset = update_jalr_offset(jalr_offset, inst)
                elif inst['RD'] == 'T0':
                    inst = Instruction('add t0, ra, zero')
                    block.inst_list.append(inst)
                    jalr_offset = update_jalr_offset(jalr_offset, inst)
            return jalr_offset

        self._gen_block_begin()

        block = BaseBlock(f'{self.name}_{len(self.inst_block_list)}', self.extension, True)
        self._add_inst_block(block)

        jalr_offset = 8
        for _ in range(24):
            match(AdjustType.random_choice()):
                case AdjustType.BRANCH:
                    inst = Instruction()
                    inst.set_category_constraint(['BRANCH'])
                    next_block = BaseBlock(f'{self.name}_{len(self.inst_block_list)}', self.extension, True)
                    self._add_inst_block(next_block)
                    inst.set_label_constraint([next_block.name])
                    inst.solve()
                    block.inst_list.append(inst)
                    jalr_offset = update_jalr_offset(jalr_offset, inst)
                    block = next_block
                case AdjustType.RETURN:
                    inst = Instruction(f'jalr zero, {jalr_offset}(ra)')
                    block.inst_list.append(inst)
                    jalr_offset = update_jalr_offset(jalr_offset, inst)
                    inst['IMM'] = jalr_offset
                case AdjustType.CALL:
                    inst = Instruction(f'jalr ra, {jalr_offset}(t0)')
                    block.inst_list.append(inst)
                    jalr_offset = update_jalr_offset(jalr_offset, inst)
                    inst = Instruction('add ra, t0, zero')
                    block.inst_list.append(inst)
                    jalr_offset = update_jalr_offset(jalr_offset, inst)
                case AdjustType.CALL_LOOP:
                    inst = Instruction(f'jalr ra, {jalr_offset}(t0)')
                    block.inst_list.append(inst)
                    jalr_offset = update_jalr_offset(jalr_offset, inst)
                    inst['IMM'] = jalr_offset
                    inst = Instruction('add ra, t0, zero')
                    block.inst_list.append(inst)
                    jalr_offset = update_jalr_offset(jalr_offset, inst)
                case AdjustType.JALR:
                    inst = Instruction()
                    inst.set_name_constraint(['JALR'])
                    inst.set_category_constraint(['JUMP'])
                    inst.solve()
                    block.inst_list.append(inst)
                    jalr_offset = update_jalr_offset(jalr_offset, inst)
                    inst['RS1'] = 'T0'
                    inst['IMM'] = jalr_offset
                    jalr_offset = recover_t0_ra(inst, block, jalr_offset)
                case AdjustType.JMP:
                    inst = Instruction()
                    inst.set_name_constraint(['JAL', 'C.J'])
                    inst.set_category_constraint(['JUMP'])
                    next_block = BaseBlock(f'{self.name}_{len(self.inst_block_list)}', self.extension, True)
                    self._add_inst_block(next_block)
                    inst.set_label_constraint([next_block.name])
                    inst.solve()
                    block.inst_list.append(inst)
                    jalr_offset = update_jalr_offset(jalr_offset, inst)
                    block = next_block
                    jalr_offset = recover_t0_ra(inst, block, jalr_offset)
                case AdjustType.OTHER:
                    func = random.choice([BaseBlock._gen_float_arithmetic,BaseBlock._gen_int_arithmetic])
                    inst = func(block)[0]
                    block.inst_list.append(inst)
                    jalr_offset = update_jalr_offset(jalr_offset, inst)
                    jalr_offset = recover_t0_ra(inst, block, jalr_offset)
            
            if self._get_inst_len() > 24:
                break

        self._gen_block_end()

class TransTTEManager(TransBaseManager):
    def __init__(self, config, extension, victim_privilege, virtual, output_path, trans_frame, depth, trans_victim):
        super().__init__(config, extension, victim_privilege, virtual, output_path)
        self.trans_frame = trans_frame
        assert type(trans_victim) == TransVictimManager
        self.trans_victim = trans_victim
        self.depth = depth

    def gen_block(self):
        self.delay_block = DelayBlock(self.extension, self.output_path)
        self.return_block = ReturnBlock(self.extension, self.output_path)
        self.adjust_block = AdjustBlock(self.extension, self.output_path)

        self.delay_block.gen_instr()
        self.return_block.gen_instr()
        self.adjust_block.gen_instr()

        self.trigger_block = TriggerTTEBlock(self.extension, self.output_path, self.delay_block.result_reg, self.return_block.entry)
        self.trigger_block.gen_instr()

        block_list = [self.delay_block, self.trigger_block, self.adjust_block, self.return_block]
        self.load_init_block = LoadInitTTEBlock(self.depth, self.extension, self.output_path, block_list, self.delay_block, self.trigger_block)
        self.load_init_block.gen_instr()

        front_block_begin = self.trans_victim.symbol_table['_text_swap_start']
        nop_ret_begin = self.trans_victim.symbol_table['access_secret_block_entry']
        return_entry = self.trans_victim.symbol_table['return_block_entry']
        if return_entry > nop_ret_begin:
            front_block_end = nop_ret_begin
        else:
            front_block_end = return_entry

        victim_front_len = front_block_end - front_block_begin
        if self.trans_victim.trigger_block.trigger_inst['NAME'].startswith('C.'):
            victim_front_len -= 2
        else:
            victim_front_len -= 4
        
        tte_front_len = self.load_init_block._get_inst_len() *2 + 4 + \
            self.delay_block._get_inst_len() * 4 + \
            self.trigger_block._get_inst_len() * 4 + 3 * 4 + random.randint(2, 4) * 4
        if self.trigger_block.trigger_inst['NAME'].startswith('C.'):
            tte_front_len -= 2
        
        nop_inst_len = (victim_front_len - tte_front_len) // 2

        if nop_inst_len < 0:
            for inst in self.load_init_block.gen_asm()[0]:
                print(inst)
            for inst in self.delay_block.gen_asm()[0]:
                print(inst)
            for inst in self.trigger_block.gen_asm()[0]:
                print(inst)

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
        self._set_section(text_swap_section, empty_section, [self.nop_block, self.delay_block,\
                            self.trigger_block, self.adjust_block, self.return_block])




    