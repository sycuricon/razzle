import os
import random
import sys
from enum import *
from BuildManager import *
from SectionUtils import *
from SectionManager import *
from TransBlockUtils import *
from TransVictimBlock import *

from payload.Instruction import *
from payload.MagicDevice import *
from payload.Block import *

class AdjustType(Enum):
    BRANCH = auto()
    RETURN = auto()
    CALL = auto()
    CALL_LOOP = auto()
    JALR = auto()
    JMP = auto()
    OTHER = auto()

class AdjustBlock(TransBlock):
    def __init__(self, extension, output_path, trigger_type):
        super().__init__('adjust_block', extension, output_path)
        self.trigger_type = trigger_type
    
    def _gen_block_begin(self):
        inst_list_begin = [
            'INFO_TRAIN_START',
            'auipc t0, 0',
            'add ra, t0, zero'
        ]
        self._load_inst_str(inst_list_begin)
    
    def _gen_block_end(self):
        inst_exit = [
            "adjust_exit:",
            "INFO_TRAIN_END",
            f"ebreak",
        ]
        self._load_inst_str(inst_exit)
    
    def _gen_adjust_type(self):
        class AdjustMainType(Enum):
            BRANCH = auto()
            CALL_RETURN = auto()
            JMP = auto()
            OTHER = auto()

        adjust_main_prob = {
            AdjustMainType.BRANCH: 0.2,
            AdjustMainType.CALL_RETURN: 0.2,
            AdjustMainType.JMP: 0.2,
            AdjustMainType.OTHER: 0.1
        }
        match self.trigger_type:
            case TriggerType.BRANCH:
                adjust_main_prob[AdjustMainType.BRANCH] += 0.3
            case TriggerType.RETURN:
                adjust_main_prob[AdjustMainType.CALL_RETURN] += 0.3
            case TriggerType.JMP | TriggerType.JALR:
                adjust_main_prob[AdjustMainType.JMP] += 0.3
            case _:
                adjust_main_prob[AdjustMainType.BRANCH] += 0.1
                adjust_main_prob[AdjustMainType.CALL_RETURN] += 0.1
                adjust_main_prob[AdjustMainType.JMP] += 0.1
        
        match random_choice(adjust_main_prob):
            case AdjustMainType.BRANCH:
                return AdjustType.BRANCH
            case AdjustMainType.CALL_RETURN:
                adjust_sub_prob = {
                    AdjustType.RETURN: 0.5,
                    AdjustType.CALL: 0.3,
                    AdjustType.CALL_LOOP: 0.2,
                }
                return random_choice(adjust_sub_prob)
            case AdjustMainType.JMP:
                return random.choice([AdjustType.JALR, AdjustType.JMP])
            case AdjustMainType.OTHER:
                return AdjustType.OTHER
            case _:
                raise Exception("invalid adjust type")

    def gen_default(self):
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
            match(self._gen_adjust_type()):
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
            
            if self._get_inst_len() > 96:
                break
        
        inst_list = ['adjust_fill_nop:']
        inst_list.extend(['c.nop'] * (120 - self._get_inst_len())//2)

        self._gen_block_end()

class TransTTEManager(TransBaseManager):
    def __init__(self, config, extension, victim_privilege, virtual, output_path, data_section):
        super().__init__(config, extension, victim_privilege, virtual, output_path)
        self.data_section = data_section

    def gen_block(self, template_path, trans_victim):
        assert type(trans_victim) == TransVictimManager
        self.trans_victim = trans_victim

        if template_path is not None:
            template_list = os.listdir(template_path)
            with open(os.path.join(template_path, 'return_front'), 'rt') as file:
                return_front = eval(file.readline().strip())
            delay_template = None if 'delay_block.text' not in template_list else os.path.join(template_path, 'delay_block')
            adjust_template = None if 'adjust_block.text' not in template_list else os.path.join(template_path, 'adjust_block')
            trigger_template = None if 'trigger_block.text' not in template_list else os.path.join(template_path, 'trigger_block')
            load_init_template = None if 'load_init_block.text' not in template_list else os.path.join(template_path, 'load_init_block')
        else:
            return_front = False
            delay_template = None
            adjust_template = None
            trigger_template = None
            load_init_template = None

        self.delay_block = DelayBlock(self.extension, self.output_path)
        self.return_block = ReturnBlock(self.extension, self.output_path)
        self.adjust_block = AdjustBlock(self.extension, self.output_path, self.trans_victim.trigger_type)

        self.delay_block.gen_instr(delay_template)
        self.return_block.gen_instr(None)
        self.adjust_block.gen_instr(adjust_template)

        self.trigger_block = TriggerBlock(self.extension, self.output_path, self.delay_block.result_reg, self.return_block.entry, self.return_block.entry, True)
        self.trigger_block.gen_instr(trigger_template)
        assert self.trigger_block.trigger_type != TriggerType.V4

        block_list = [self.delay_block, self.trigger_block, self.adjust_block, self.return_block]
        self.load_init_block = LoadInitTriggerBlock(self.swap_idx, self.extension, self.output_path, block_list, self.delay_block, self.trigger_block)
        self.load_init_block.gen_instr(load_init_template)

        front_block_begin = self.trans_victim.symbol_table['_text_swap_start']
        nop_ret_begin = self.trans_victim.symbol_table['access_secret_block_entry']
        return_entry = self.trans_victim.symbol_table['return_block_entry']
        if return_entry > nop_ret_begin:
            front_block_end = nop_ret_begin
        else:
            front_block_end = return_entry

        victim_front_len = front_block_end - front_block_begin
        if self.trans_victim.trigger_block.trigger_inst.is_rvc():
            victim_front_len -= 2
        else:
            victim_front_len -= 4
        
        tte_front_len = self.load_init_block._get_inst_len() + \
            self.delay_block._get_inst_len() + \
            self.trigger_block._get_inst_len() + (3 + random.randint(2, 4)) * 4
        if return_front == True:
            tte_front_len += self.return_block._get_inst_len()
        
        nop_inst_len = victim_front_len - tte_front_len

        if nop_inst_len < 0:
            for inst in self.load_init_block.gen_asm()[0]:
                print(inst)
            for inst in self.delay_block.gen_asm()[0]:
                print(inst)
            for inst in self.trigger_block.gen_asm()[0]:
                print(inst)

        self.nop_block = NopBlock(self.extension, self.output_path, nop_inst_len)
        self.nop_block.gen_instr(None)

        self.trigger_type = self.trigger_block.trigger_type
    
    def mutate(self):
        self.adjust_block = AdjustBlock(self.extension, self.output_path, self.trans_victim.trigger_type)
        self.adjust_block.gen_instr(None)

        old_load_init_len = self.load_init_block._get_inst_len()

        block_list = [self.delay_block, self.trigger_block, self.adjust_block, self.return_block]
        self.load_init_block = LoadInitTriggerBlock(self.swap_idx, self.extension, self.output_path, block_list, self.delay_block, self.trigger_block)
        self.load_init_block.gen_instr(None)

        new_load_init_len = self.load_init_block._get_inst_len()

        self.nop_block = NopBlock(self.extension, self.output_path, self.nop_block.c_nop_len + old_load_init_len - new_load_init_len)
        self.nop_block.gen_instr(None)

    def dump_trigger_block(self, folder):
        self._dump_trans_block(folder, [self.load_init_block, self.delay_block,\
            self.trigger_block, self.adjust_block], self.return_front)
    
    def _generate_sections(self):

        text_swap_section = self.section[".text_swap"] = FuzzSection(
            ".text_swap", Flag.U | Flag.X | Flag.R
        )

        self.section[".data_tte"] = self.data_section

        empty_section = FuzzSection(
            "", 0
        )

        self.data_section.clear()
        self._set_section(text_swap_section, self.data_section,[self.load_init_block])
        self._set_section(text_swap_section, empty_section, [self.nop_block, self.delay_block,\
                            self.trigger_block])
        if self.return_front:
            self._set_section(text_swap_section, empty_section, [self.return_block, self.adjust_block])
        else:
            self._set_section(text_swap_section, empty_section, [self.adjust_block, self.return_block])
    
    def need_train(self):
        return TriggerType.need_train(self.trigger_block.trigger_type)




    