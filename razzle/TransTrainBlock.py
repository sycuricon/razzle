import os
import random
import sys
from enum import *
from BuildManager import *
from SectionUtils import *
from SectionManager import *
from TransBlockUtils import *
from TransVictimBlock import *
from TransTTEBlock import *

from payload.Instruction import *
from payload.MagicDevice import *
from payload.Block import *

class TrainType(Enum):
    BRANCH_NOT_TAKEN = auto()
    BRANCH_TAKEN = auto()
    JALR = auto()
    JMP = auto()
    CALL = auto()
    RETURN = auto()

class trainTrainBlock(TransBlock):
    def __init__(self, extension, output_path, ret_label, train_label, train_type):
        super().__init__('train_block', extension, output_path)
        self.ret_label  = ret_label
        self.train_label = train_label
        self.train_type = train_type
    
    def gen_instr(self):
        block = BaseBlock(self.entry, self.extension, True)
        inst = Instruction()
        inst.set_extension_constraint(self.extension)

        match(self.train_type):
            case TrainType.BRANCH_NOT_TAKEN | TrainType.BRANCH_TAKEN:
                inst.set_category_constraint(['BRANCH'])
                inst.set_label_constraint([self.ret_label, self.train_label])
                inst.solve()
                inst['RS1'] = 'A0'
                inst['RS1'] = 'A1'
            case TrainType.JALR:
                inst.set_name_constraint(['JALR', 'C.JALR', 'C.JR'])
                inst.set_category_constraint(['JUMP'])
                inst.solve()
                inst['RS1'] = 'A0'
            case TrainType.RETURN:
                inst.set_name_constraint(['JALR', 'C.JR'])
                inst.set_category_constraint(['JUMP'])
                inst.solve()
                inst['RS1'] = 'RA'
                inst['RD'] = 'ZERO'
            case TrainType.JMP:
                inst.set_name_constraint(['JAL', 'C.J', 'C.JAL'])
                inst.set_category_constraint(['JUMP'])
                inst.set_label_constraint([self.ret_label, self.train_label])
                inst.solve()
            case TrainType.CALL:
                inst.set_name_constraint(['JALR', 'JAL', 'C.JALR', 'C.JAL'])
                inst.set_category_constraint(['JUMP'])
                inst.set_label_constraint([self.ret_label, self.train_label])
                inst.solve()
                inst['RD'] = 'RA'
                inst['RS1'] = 'A0'
            case _:
                raise Exception(f"the train type {self.train_type} is invalid")
    
        self.train_inst = inst
        block.inst_list.append(inst)
        self._add_inst_block(block)
    
class LoadInitTrainBlock(LoadInitBlock):
    def __init__(self, depth, extension, output_path, train_block):
        super().__init__(depth, extension, output_path, None)
        self.train_block = train_block
        self.ret_label = train_block.ret_label
        self.train_label = train_block.train_label
    
    def _compute_train_param(self):
        train_inst = self.train_block.train_inst
        train_type = self.train_block.train_type

        do_train = random.choice([False, True])
        train_param = {}

        match(train_type):
            case TrainType.BRANCH_NOT_TAKEN:
                match(train_inst['NAME']):
                    case 'BEQ'|'BGE'|'BGEU':
                        train_param[train_inst['RS1']] = 0
                        train_param[train_inst['RS2']] = 1
                    case 'BNE'|'BLT'|'BLTU':
                        train_param[train_inst['RS1']] = 0
                        train_param[train_inst['RS2']] = 0
                    case 'C.BEQZ':
                        train_param[train_inst['RS1']] = 1
                    case 'C.BNEZ':
                        train_param[train_inst['RS1']] = 0
                    case _:
                        raise Exception('invalid branch type')
            case TrainType.BRANCH_TAKEN:
                match(train_inst['NAME']):
                    case 'BEQ'|'BGE'|'BGEU':
                        train_param[train_inst['RS1']] = 0
                        train_param[train_inst['RS2']] = 0
                    case 'BNE'|'BLT'|'BLTU':
                        train_param[train_inst['RS1']] = 1
                        train_param[train_inst['RS2']] = 0
                    case 'C.BEQZ':
                        train_param[train_inst['RS1']] = 0
                    case 'C.BNEZ':
                        train_param[train_inst['RS1']] = 1
                    case _:
                        raise Exception('invalid branch type')
            case TrainType.JALR | TrainType.RETURN:
                train_inst_imm = train_inst['IMM'] if train_inst.has('IMM') else 0
                if do_train:
                    train_param[train_inst['RS1']] = f'{self.train_label} - {hex(train_inst_imm)}'
                else:
                    train_param[train_inst['RS1']] = f'{self.ret_label} - {hex(train_inst_imm)}'
            case TrainType.CALL:
                if train_inst['NAME'] in ['C.JALR', 'JALR']:
                    train_inst_imm = train_inst['IMM'] if train_inst.has('IMM') else 0
                    if do_train:
                        train_param[train_inst['RS1']] = f'{self.train_label} - {hex(train_inst_imm)}'
                    else:
                        train_param[train_inst['RS1']] = f'{self.ret_label} - {hex(train_inst_imm)}'
                elif train_inst['NAME'] in ['C.JAL', 'JAL']:
                    pass
            case TrainType.JMP:
                pass
            case _:
                raise Exception(f"the train type {train_type} and inst {train_inst['NAME']} is invalid")

        return train_param
    
    def gen_instr(self):
        train_param = self._compute_train_param()
        need_inited = list(train_param.keys())
        if 'ZERO' in need_inited:
            need_inited.remove('ZERO')
        if 'SP' in need_inited:
            need_inited.remove('SP')
            need_inited.append('SP')
        self.GPR_init_list = need_inited

        inst_list = [
            f"la sp, {self.name}_data_table",
        ]
        data_list = [
            f"{self.name}_data_table:"
        ]

        table_index = 0
        for reg in self.GPR_init_list:
            inst_list.append(f"c.ldsp {reg.lower()}, {table_index*8}(sp)")
            data_list.append(f".dword {train_param[reg]}")
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
        ] * ((self.c_nop_len - 4)//2)

        inst_list.append('ebreak')

        self._load_inst_str(inst_list)

class TransTrainManager(TransBaseManager):
    def __init__(self, config, extension, victim_privilege, virtual, output_path, data_section, trans_victim, train_type):
        super().__init__(config, extension, victim_privilege, virtual, output_path)
        assert type(trans_victim) in [TransVictimManager, TransTTEManager]
        self.trans_victim = trans_victim
        self.train_type = train_type
        self.data_section = data_section

    def gen_block(self):
        self.return_block = ReturnBlock(self.extension, self.output_path)
        self.return_block.gen_instr()

        self.return_front = False

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
                self.return_front = True

        self.nop_ret_block = NopRetBlock(self.extension, self.output_path, (nop_ret_end - nop_ret_begin))
        self.nop_ret_block.gen_instr()

        self.train_block = trainTrainBlock(self.extension, self.output_path, self.return_block.entry, self.nop_ret_block.entry, self.train_type)
        self.train_block.gen_instr()
        train_block_len = self.train_block._get_inst_len()

        self.load_init_block = LoadInitTrainBlock(self.swap_idx, self.extension, self.output_path, self.train_block)
        self.load_init_block.gen_instr()
        load_init_block_len = self.load_init_block._get_inst_len()

        c_nop_len = front_block_end - front_block_begin - train_block_len - load_init_block_len
        self.nop_block = NopBlock(self.extension, self.output_path, c_nop_len)
        self.nop_block.gen_instr()
    
    def dump_trigger_block(self, folder):
        self._dump_trans_block(folder, [self.load_init_block, self.train_block], self.return_front)

        train_type_file = os.path.join(folder, 'train_type')
        with open(train_type_file, "wt") as file:
            file.write(f'{self.train_block.train_type}')
    
    def record_fuzz(self,file):
        file.write(f'train_type:\t{self.train_block.train_type}\t')
        file.write(f'train_inst:\t{self.train_block.train_inst.to_asm()}\t')
        file.write(f'return_front:\t{self.return_front}\n')

    def _generate_sections(self):

        text_swap_section = self.section[".text_swap"] = FuzzSection(
            ".text_swap", Flag.U | Flag.X | Flag.R
        )

        if type(self.trans_victim) == TransVictimManager:
            self.section[".data_train"] = self.data_section
        else:
            self.section[".data_tte_train"] = self.data_section

        empty_section = FuzzSection(
            "", 0
        )

        self._set_section(text_swap_section, self.data_section, [self.load_init_block])
        self._set_section(text_swap_section, empty_section, [self.nop_block, self.train_block])
        if self.return_front:
            self._set_section(text_swap_section, empty_section, [self.return_block, self.nop_ret_block])
        else:
            self._set_section(text_swap_section, empty_section, [self.nop_ret_block, self.return_block])

