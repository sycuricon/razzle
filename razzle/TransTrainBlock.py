import os
import random
import sys
from enum import Enum
from BuildManager import *
from SectionUtils import *
from SectionManager import *
from TransBlockUtils import *
from TransVictimBlock import *
from TransTTEBlock import *

from payload.Instruction import *
from payload.MagicDevice import *
from payload.Block import *

class TriggerTrainBlock(TransBlock):
    def __init__(self, extension, output_path, ret_label, train_label):
        super().__init__('trigger_block', extension, output_path)
        self.ret_label  = ret_label
        self.train_label = train_label
        self.trigger_type = TriggerType.train_random_choice()
    
    def gen_instr(self):
        block = BaseBlock(self.entry, self.extension, True)
        inst = Instruction()
        inst.set_extension_constraint(self.extension)

        match(self.trigger_type):
            case TriggerType.BIM:
                inst.set_category_constraint(['BRANCH'])
                inst.set_label_constraint([self.ret_label, self.train_label])
                inst.solve()
            case TriggerType.BTB:
                inst.set_name_constraint(['JALR', 'C.JALR', 'C.JR'])
                inst.set_category_constraint(['JUMP'])
                def btb_c(rs1):
                    return rs1 != 'ZERO'
                inst.add_constraint(btb_c, ['RS1'])
                inst.solve()
            case TriggerType.RSB:
                inst.set_name_constraint(['JALR', 'C.JR'])
                inst.set_category_constraint(['JUMP'])
                inst.solve()
                inst['RS1'] = 'RA'
                inst['RD'] = 'ZERO'
            case TriggerType.JMP:
                inst.set_name_constraint(['JAL', 'C.J'])
                inst.set_category_constraint(['JUMP'])
                inst.set_label_constraint([self.ret_label, self.train_label])
                inst.solve()
            case _:
                raise "the trigger type is invalid"
    
        self.trigger_inst = inst
        block.inst_list.append(inst)
        self._add_inst_block(block)
    
class LoadInitTrainBlock(LoadInitBlock):
    def __init__(self, depth, extension, output_path, trigger_block):
        super().__init__(depth, extension, output_path, None)
        self.trigger_block = trigger_block
        self.ret_label = trigger_block.ret_label
        self.train_label = trigger_block.train_label
    
    def _compute_trigger_param(self):
        trigger_inst = self.trigger_block.trigger_inst
        trigger_type = self.trigger_block.trigger_type

        do_train = random.choice([False, True])
        trigger_param = {}

        match(trigger_type):
            case TriggerType.BIM:
                trigger_param[trigger_inst['RS1']] = random.randint(0, 2**64-1)
                if trigger_inst.has('RS2'):
                    trigger_param[trigger_inst['RS2']] = random.randint(0, 2**64-1)
            case TriggerType.BTB | TriggerType.RSB:
                trigger_inst_imm = trigger_inst['IMM'] if trigger_inst.has('IMM') else 0
                if do_train:
                    trigger_param[trigger_inst['RS1']] = f'{self.train_label} - {hex(trigger_inst_imm)}'
                else:
                    trigger_param[trigger_inst['RS1']] = f'{self.ret_label} - {hex(trigger_inst_imm)}'
            case TriggerType.JMP:
                pass
            case _:
                raise Exception("the trigger type is invalid")

        return trigger_param
    
    def gen_instr(self):
        trigger_param = self._compute_trigger_param()
        need_inited = list(trigger_param.keys())
        if 'ZERO' in need_inited:
            need_inited.remove('ZERO')
        if 'SP' in need_inited:
            need_inited.remove('SP')
            need_inited.append('SP')
        self.GPR_init_list = need_inited

        inst_list = [
            f"la sp, {self.name}_delay_data_table",
        ]
        data_list = [
            f"{self.name}_delay_data_table:"
        ]

        table_index = 0
        for reg in self.GPR_init_list:
            inst_list.append(f"c.ldsp {reg.lower()}, {table_index*8}(sp)")
            data_list.append(f".dword {hex(random.randint(0, 2**64))}")
            table_index += 1

        self._load_inst_str(inst_list)
        self._load_data_str(data_list)

class NopRetBlock(TransBlock):
    def __init__(self, extension, output_path, c_nop_len):
        super().__init__('nop_ret_block', extension, output_path)
        self.c_nop_len = c_nop_len

    def gen_instr(self):
        inst_list = [
            'c.nop'
        ] * (self.c_nop_len - 2)

        inst_list.append('j run_time_loop')

        self._load_inst_str(inst_list)

class TransTrainManager(TransBaseManager):
    def __init__(self, config, extension, victim_privilege, virtual, output_path, trans_frame, depth, trans_victim):
        super().__init__(config, extension, victim_privilege, virtual, output_path)
        self.trans_frame = trans_frame
        assert type(trans_victim) in [TransVictimManager, TransTTEManager]
        self.trans_victim = trans_victim
        self.depth = depth

    def gen_block(self):
        self.return_block = ReturnBlock(self.extension, self.output_path)
        self.return_block.gen_instr()

        self.return_block_first = False

        front_block_begin = self.trans_victim.symbol_table['_text_swap_start']
        if type(self.trans_victim) == TransTTEManager:
            nop_ret_begin = self.trans_victim.symbol_table['adjust_block_entry']
            nop_ret_end = self.trans_victim.symbol_table['return_block_entry']
            front_block_end = nop_ret_begin
        else:
            nop_ret_begin = self.trans_victim.symbol_table['access_secret_block_entry']
            return_entry = self.trans_victim.symbol_table['return_block_entry']
            if return_entry > nop_ret_begin:
                nop_ret_end = return_entry
                front_block_end = nop_ret_begin
            else:
                nop_ret_end = self.trans_victim.symbol_table['_text_swap_end']
                front_block_end = return_entry
                self.return_block_first = True

        self.nop_ret_block = NopRetBlock(self.extension, self.output_path, (nop_ret_end - nop_ret_begin)//2)
        self.nop_ret_block.gen_instr()

        self.trigger_block = TriggerTrainBlock(self.extension, self.output_path, self.return_block.entry, self.nop_ret_block.entry)
        self.trigger_block.gen_instr()
        trigger_block_len = 2 if self.trigger_block.trigger_inst['NAME'].startswith == 'C.' else 4

        self.load_init_block = LoadInitTrainBlock(self.depth, self.extension, self.output_path, self.trigger_block)
        self.load_init_block.gen_instr()
        load_init_block_len = self.load_init_block._get_inst_len() * 2 + 4

        c_nop_len = (front_block_end - front_block_begin - trigger_block_len - load_init_block_len) // 2
        self.nop_block = NopBlock(self.extension, self.output_path, c_nop_len)
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
        self._set_section(text_swap_section, empty_section, [self.nop_block, self.trigger_block])
        if self.return_block_first:
            self._set_section(text_swap_section, empty_section, [self.return_block, self.nop_ret_block])
        else:
            self._set_section(text_swap_section, empty_section, [self.nop_ret_block, self.return_block])

