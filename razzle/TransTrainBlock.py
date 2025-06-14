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

class TrainType(Enum):
    BRANCH_NOT_TAKEN = auto()
    BRANCH_TAKEN = auto()
    JALR = auto()
    JMP = auto()
    CALL = auto()
    RETURN = auto()

    INT = auto()
    FLOAT = auto()
    LOAD = auto()
    STORE = auto()
    AMO = auto()
    SYSTEM = auto()

    NONE = auto()

class TrainBlock(TransBlock):
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
            case TrainType.INT:
                inst.set_category_constraint(['ARITHMETIC'])
                def name_c(name):
                    return name not in ['LA', 'Li']
                inst.add_constraint(name_c, ['NAME'])
                inst.solve()
            case TrainType.FLOAT:
                inst.set_category_constraint(['FLOAT'])
                inst.solve()
            case TrainType.LOAD:
                inst.set_category_constraint(['LOAD', 'FLOAT_LOAD', 'LOAD_SP'])
                inst.solve()
            case TrainType.STORE:
                inst.set_category_constraint(['STORE', 'FLOAT_STORE', 'STORE_SP'])
                inst.solve()
            case TrainType.AMO:
                inst.set_category_constraint(['AMO', 'AMO_LOAD', 'AMO_STORE'])
                inst.solve()
            case TrainType.SYSTEM:
                inst.set_category_constraint(['SYSTEM'])
                inst.solve()
            case _:
                raise Exception(f"the train type {self.train_type} is invalid")
    
        self.train_inst = inst
        block.inst_list.append(inst)
        self._add_inst_block(block)
    
    def append_train_nop_len(self, c_nop_len):
        inst_list = ['nop_append:']
        inst_list.extend(['c.nop'] * (c_nop_len // 2))
        self._load_inst_str(inst_list)
    
    def record_fuzz(self):
        record = {}
        record['type'] = f'{self.train_type}'
        record['inst'] = self.train_inst.to_asm()
        return self.name, record
    
class LoadInitTrainBlock(LoadInitBlock):
    def __init__(self, depth, extension, output_path, train_block, mode):
        super().__init__(depth, extension, output_path, None, mode)
        self.train_block = train_block
        self.ret_label = train_block.ret_label
        self.train_label = train_block.train_label
        
    
    def _compute_param(self):
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
                        train_param[train_inst['RS1']] = 0
                        train_param[train_inst['RS2']] = 1
                    case 'C.BEQZ':
                        train_param[train_inst['RS1']] = 0
                    case 'C.BNEZ':
                        train_param[train_inst['RS1']] = 1
                    case _:
                        raise Exception('invalid branch type')
            case TrainType.JALR | TrainType.RETURN:
                train_inst_imm = train_inst['IMM'] if train_inst.has('IMM') else 0
                if do_train:
                    train_param[train_inst['RS1']] = f'{self.train_label} + {self.prefix} - {hex(train_inst_imm)}'
                else:
                    train_param[train_inst['RS1']] = f'{self.ret_label} + {self.prefix} - {hex(train_inst_imm)}'
            case TrainType.CALL:
                if train_inst['NAME'] in ['C.JALR', 'JALR']:
                    train_inst_imm = train_inst['IMM'] if train_inst.has('IMM') else 0
                    if do_train:
                        train_param[train_inst['RS1']] = f'{self.train_label} + {self.prefix} - {hex(train_inst_imm)}'
                    else:
                        train_param[train_inst['RS1']] = f'{self.ret_label} + {self.prefix} - {hex(train_inst_imm)}'
                elif train_inst['NAME'] in ['C.JAL', 'JAL']:
                    pass
            case TrainType.JMP|TrainType.SYSTEM:
                pass
            case TrainType.INT|TrainType.FLOAT:
                for field in ['RS1', 'RS2', 'RD', 'FRS1', 'FRS2', 'FRS3']:
                    if train_inst.has(field):
                        train_param[train_inst[field]] = random.randint(0, 2**64-1)
            case TrainType.STORE|TrainType.LOAD|TrainType.AMO:
                addr_reg = 'SP'
                if train_inst.has('RS1'):
                    addr_reg = train_inst['RS1']
                addr = random.choice(['random_data_block_page_base', 'page_fault_data_block_page_base', 'access_fault_data_block_page_base'])
                addr = f'{addr} + {self.prefix}'
                if train_type == train_type.AMO:
                    addr = f'{addr} + {random.randint(-0x800, 0x7ff)}'
                train_param[addr_reg] = addr
                for field in ['RS2', 'FRS1']:
                    if train_inst.has(field):
                        train_param[train_inst[field]] = random.randint(0, 2**64-1)
            case _:
                raise Exception(f"the train type {train_type} and inst {train_inst['NAME']} is invalid")

        return train_param

class NopRetBlock(TransBlock):
    def __init__(self, extension, output_path, c_nop_len):
        super().__init__('nop_ret_block', extension, output_path)
        self.c_nop_len = c_nop_len

    def gen_instr(self):
        inst_list = ['ebreak']
        inst_list.extend([
            'c.nop'
        ] * ((self.c_nop_len - 8)//2))
        inst_list.append('ebreak')

        self._load_inst_str(inst_list)

class TransTrainManager(TransBaseManager):
    def __init__(self, config, extension, output_path, data_section, trans_frame):
        super().__init__(config, extension, output_path)
        self.data_section = data_section
        self.trans_frame = trans_frame

    def gen_block(self, config, train_type, align, single, trans_victim):
        self.mode = ''.join([config['train_priv'], config['train_addr']])

        self.single = single
        self.align = align
        self.trans_victim = trans_victim

        if self.single:

            self.train_type = train_type

            self.return_block = ReturnBlock(self.extension, self.output_path)
            self.return_block.gen_instr()

            self.return_front = self.trans_victim.return_front

            front_block_begin = self.trans_victim.symbol_table['_text_swap_start']
            if self.return_front:
                nop_ret_begin = self.trans_victim.symbol_table['access_secret_block_entry']
                nop_ret_end = self.trans_victim.symbol_table['_text_swap_end']
                front_block_end = self.trans_victim.symbol_table['return_block_entry']
            else:
                nop_ret_begin = self.trans_victim.symbol_table['access_secret_block_entry']
                nop_ret_end = self.trans_victim.symbol_table['return_block_entry']
                front_block_end = nop_ret_begin

            nop_ret_len = (nop_ret_end - nop_ret_begin)
            self.nop_ret_block = NopRetBlock(self.extension, self.output_path, nop_ret_len)
            self.nop_ret_block.gen_instr()

            self.train_block = TrainBlock(self.extension, self.output_path, self.return_block.entry, self.nop_ret_block.entry, self.train_type)
            self.train_block.gen_instr()
            self.train_type = self.train_block.train_type

            self.load_init_block = LoadInitTrainBlock(self.swap_idx, self.extension, self.output_path, self.train_block, self.mode)
            self.load_init_block.gen_instr()

            train_block_len = self.train_block._get_inst_len()
            load_init_block_len = self.load_init_block._get_inst_len()
            c_nop_len = front_block_end - front_block_begin - train_block_len - load_init_block_len
            if not self.align:
                train_nop_len = random.randint(0, c_nop_len - 6)
                if train_nop_len % 2 != 0:
                    train_nop_len -= 1
                c_nop_len = c_nop_len - train_nop_len
                self.train_block.append_train_nop_len(train_nop_len)
            self.nop_block = NopBlock(self.extension, self.output_path, c_nop_len)
            self.nop_block.gen_instr()
        
        else:

            block_begin = self.trans_victim.symbol_table['_text_swap_start']
            block_end = self.trans_victim.symbol_table['_text_swap_end']
            full_nop_len = (block_end - block_begin) // 2
            nop_len = random.randint(10, full_nop_len - 10)
            ret_nop_len = full_nop_len - nop_len

            self.nop_block = NopBlock(self.extension, self.output_path, nop_len)
            self.nop_block.gen_instr()
            self.nop_ret_block = NopRetBlock(self.extension, self.output_path, ret_nop_len)
            self.nop_ret_block.gen_instr()

            self.arbitrary_block = ArbitraryBlock(self.extension, self.output_path)
            self.arbitrary_block.gen_instr()

            self.load_init_block = LoadInitBlock(self.swap_idx, self.extension, self.output_path, [self.arbitrary_block], self.mode)
            self.load_init_block.gen_instr()

            self.return_front = False

    
    def record_fuzz(self):
        if self.single:
            block_list = [self.train_block]
        else:
            block_list = []
        record = self._base_record_fuzz(block_list)
        record['align'] = self.align
        record['single'] = self.single
        record['return_front'] = self.return_front
        return 'train', record

    def _generate_sections(self):

        text_swap_section = self.section[".text_swap"] = FuzzSection(
            ".text_swap", Flag.U | Flag.X | Flag.R
        )

        self.section[".data_train"] = self.data_section

        empty_section = FuzzSection(
            "", 0
        )

        if self.single:
            self._set_section(text_swap_section, self.data_section, [self.load_init_block])
            self._set_section(text_swap_section, empty_section, [self.nop_block, self.train_block])
            if self.return_front:
                self._set_section(text_swap_section, empty_section, [self.return_block, self.nop_ret_block])
            else:
                self._set_section(text_swap_section, empty_section, [self.nop_ret_block, self.return_block])
        else:
            self._set_section(text_swap_section, self.data_section, [self.load_init_block])
            self._set_section(text_swap_section, empty_section, [self.nop_block, self.arbitrary_block, self.nop_ret_block])

