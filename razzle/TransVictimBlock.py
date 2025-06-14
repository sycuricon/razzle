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
    
    def gen_instr(self):
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
                    self.trigger_type = random.choice([TriggerType.LOAD_ACCESS_FAULT, TriggerType.LOAD])
                
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
                    self.trigger_type = random.choice([TriggerType.STORE_ACCESS_FAULT, TriggerType.STORE])
                
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
    
    def record_fuzz(self):
        record = {}
        record['type'] = f"{self.trigger_type}"
        record['inst'] = self.trigger_inst.to_asm()
        return self.name, record

class AccessSecretBlock(TransBlock):
    def __init__(self, extension, output_path, li, mask, train_priv, train_addr, attack_priv, attack_addr):
        super().__init__('access_secret_block', extension, output_path)
        self.li_offset = li
        self.mask = mask
        self.train_priv = train_priv
        self.train_addr = train_addr
        self.attack_priv = attack_priv
        self.attack_addr = attack_addr
    
    def _gen_block_end(self):
        inst_list = [
            f"{self.name}_end:",
            "INFO_TEXE_START"
        ]

        self._load_inst_str(inst_list)
    
    def gen_instr(self):
        self.mask = (1 << self.mask) - 1
        self.rand_mask = (1 << 64) - 1 - self.mask
        self.address = 0x4001
        self.address = (self.address & self.mask) | (random.randint(0, (2<<64)-1) & self.rand_mask)

        trapoline_address = 0x5000
        offset = hex(self.address - trapoline_address)
        if self.attack_addr == 'p':
            base_trapoline_address = 0x80005000
        elif self.train_addr == 'p':
            base_trapoline_address =  0x5000 if self.attack_priv == 'U' else 0xfffffffffff05000 
        else:
            base_trapoline_address =  0x5000 if self.train_priv == 'U' else 0xfffffffffff05000 

        if self.li_offset:
            
            inst_list = [
                f'li s0, {offset}',
                f'li t1, {base_trapoline_address}',
                f'add t1, t1, s0',
                'lb s0, 0(t1)',            
            ]

        else:

            inst_list = [
                f'la s0, {self.name}_target_offset',
                f'ld s0, 0(s0)',
                f'li t1, {base_trapoline_address}',
                f'add t1, t1, s0',
                'lb s0, 0(t1)',
            ]
            
        data_list = [
            f'{self.name}_target_offset:',
            f'.dword {offset}',
        ]

        self._load_inst_str(inst_list, mutate=True)
        self._load_data_str(data_list)

        self.secret_reg = 'S0'

        self._gen_block_end()
    
    def record_fuzz(self):
        record = {}
        record['li_offset'] = self.li_offset
        record['mask'] = self.mask
        record['address'] = self.address
        return self.name, record

class ReturnVictimBlock(ReturnBlock):
    def __init__(self, extension, output_path):
        super().__init__(extension, output_path)

    def gen_instr(self):
        inst_list = ['INFO_VCTM_END']
        inst_list.extend(
            ['nop' for _ in range(16)]
        )
        inst_list.extend(
            [
                'ebreak',
                'warm_up_top:',
                'j warm_up_bottom'
            ]
        )
        self._load_inst_str(inst_list)

class EncodeType(Enum):
    FUZZ_FRONTEND = auto()
    FUZZ_BACKEND = auto()
    FUZZ_PIPELINE = auto()
    FUZZ_DEFAULT = auto()

class EncodeBlock(TransBlock):
    def __init__(self, extension, output_path, secret_reg, strategy, block_len=0, block_num=0):
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
        inst_list = []
        self._load_inst_str(inst_list)
    
    def _gen_block_end(self):

        inst_exit = [
            "encode_exit:",
            "INFO_TEXE_END",
            "ebreak",
            "warm_up_bottom:",
            "j warm_up_done"
        ]
        self._load_inst_str(inst_exit)

        inst_len = self._get_inst_len()
        inst_dummy = [
            "encode_nop_fill:",
        ]
        inst_dummy.extend(['c.nop' for _ in range((192 - inst_len)//2)])
        self._load_inst_str(inst_dummy)

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
                block.inst_list.append(Instruction(f'c.beqz {self.secret_reg}, return_block_entry'))
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

    def gen_instr(self):
        self._gen_block_begin()

        match (self.strategy):
            case EncodeType.FUZZ_DEFAULT:
                self.loop = False
                self.encode_block_list = []
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
            if self.encode_block_list[i].block_type in [BaseBlockType.CSR, BaseBlockType.SYSTEM]:
                block_list = self.encode_block_list[i].get_block_list()
                inst_len = 0
                for block in block_list:
                    inst_len += block.get_inst_len()
                block = NullBlock(self.encode_block_list[i].name, self.extension, False, inst_len)
                self.inst_block_list.append(block)
            else:
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
    
    def record_fuzz(self):
        record = {}
        record['strategy'] = f'{self.strategy}'
        record['block_len'] = self.block_len
        record['block_num'] = self.block_num
        record['loop'] = self.loop
        record['encode_type'] = []
        for block in self.encode_block_list[self.encode_block_begin:self.encode_block_end]:
            record['encode_type'].append(f'{block.block_type}')
        return self.name, record

class WarmUpVictimBlock(WarmUpBlock):
    def __init__(self, extension, output_path, warm_up):
        super().__init__(extension, output_path)
        self.warm_up = warm_up

    def gen_instr(self):
        inst_list = [
            'INFO_VCTM_START',
            'warm_up_list:',
            'j warm_up_top' if self.warm_up else 'nop',
            'nop',
            'nop',
            'warm_up_done:'
        ]
        self._load_inst_str(inst_list)
    
    def record_fuzz(self):
        record = {}
        record['warm_up'] = self.warm_up
        return self.name, record

class LoadInitTriggerBlock(LoadInitBlock):
    def __init__(self, depth, extension, output_path, init_block_list, delay_block, trigger_block, random_block, mode):
        super().__init__(depth, extension, output_path, init_block_list, mode)
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
                address_base = f'random_data_block_page_base + {self.prefix}'
                trigger_param = f'{address_base} - {self.dep_reg_result} + 1'
            case TriggerType.LOAD_ACCESS_FAULT | TriggerType.STORE_ACCESS_FAULT:
                address_base = f'access_fault_data_block_page_base + {self.prefix}'
                trigger_param = f'{address_base} - {self.dep_reg_result}'
            case TriggerType.LOAD_PAGE_FAULT | TriggerType.STORE_PAGE_FAULT:
                address_base = f'page_fault_data_block_page_base + {self.prefix}'
                trigger_param = f'{address_base} - {self.dep_reg_result}'
            case TriggerType.LOAD | TriggerType.STORE:
                address_base = f'random_data_block_page_base + {self.prefix}'
                trigger_param = f'{address_base} - {self.dep_reg_result}'
            case TriggerType.AMO:
                address_base = f'random_data_block_page_base + {self.prefix}'
                trigger_param = f'{address_base} - {hex(self.dep_reg_result)} + {hex(down_align(random.randint(-0x800, 0x7ff), 8))}'
            case TriggerType.AMO_MISALIGN:
                address_base = f'random_data_block_page_base + {self.prefix}'
                trigger_param = f'{address_base} - {hex(self.dep_reg_result)} + {hex(down_align(random.randint(-0x800, 0x7ff), 8))} + 1'
            case TriggerType.AMO_ACCESS_FAULT:
                address_base = f'access_fault_data_block_page_base + {self.prefix}'
                trigger_param = f'{address_base} - {hex(self.dep_reg_result)} + {hex(down_align(random.randint(-0x800, 0x7ff), 8))}'
            case TriggerType.AMO_PAGE_FAULT:
                address_base = f'page_fault_data_block_page_base + {self.prefix}'
                trigger_param = f'{address_base} - {hex(self.dep_reg_result)} + {hex(down_align(random.randint(-0x800, 0x7ff), 8))}'
            case TriggerType.V4:
                trigger_param = f'access_secret_block_target_offset  + {self.prefix} - {hex(self.dep_reg_result)} - {trigger_inst["IMM"]}'
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
                trigger_param = f'{self.ret_label}  + {self.prefix} - {hex(self.dep_reg_result)} - {hex(trigger_inst_imm)}'
            case TriggerType.JMP | TriggerType.EBREAK | TriggerType.ILLEGAL | TriggerType.ECALL | TriggerType.INT | TriggerType.FLOAT:
                trigger_param = None
            case _:
                raise Exception("the trigger type is invalid")

        return {'A0':trigger_param} if trigger_param != None else {}

    def _simulate_dep_reg_result(self):
        dump_result = inst_simlutor(self.baker, [self, self.delay_block, self.random_block])
        return dump_result[self.delay_block.result_reg]

    def gen_instr(self):
        self._gen_init_code()
        self.dep_reg_result = self._simulate_dep_reg_result()
        self.trigger_param = self._compute_trigger_param()

        if len(self.trigger_param) != 0:
            a0_data_asm = RawInstruction(f'.dword {self.trigger_param["A0"]}')
            if 'SP' in self.GPR_init_list:
                self.data_list[-2] = a0_data_asm
            else:
                self.data_list[-1] = a0_data_asm

    def update_init_seq(self, init_block_list):
        self.init_block_list = init_block_list
        need_inited = self._need_init_compute()
        has_inited = set(self.GPR_init_list) | set(self.float_init_list)
        need_inited.difference_update(has_inited)
        need_inited.difference_update({'ZERO'})

        len_need_inited = len(need_inited)

        has_sp = False
        if 'SP' in need_inited:
            need_inited.difference_update({'SP'})
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
            list_len = len(self.reg_init_block.inst_list)
            while i < list_len:
                if self.reg_init_block.inst_list[i].has('RD'):
                    break
                else:
                    i += 1
            self.reg_init_block.inst_list[i:i] = inst_list
            self.data_list[i:i] = data_list

            if has_sp:
                self.reg_init_block.inst_list.append(Instruction(f"c.ldsp sp, 0(sp)"))
                self.data_list.append(RawInstruction(f".dword {hex(random.randint(0, 2**64))}"))
            self.GPR_init_list.append('SP')

            for i, inst in enumerate(self.reg_init_block.inst_list[1:]):
                inst['IMM'] = i*8

            self.GPR_init_list.extend(GPR_init_list)
            self.float_init_list.extend(float_init_list)
        
class TransVictimManager(TransBaseManager):
    def __init__(self, config, extension, output_path, data_section, trans_frame):
        super().__init__(config, extension, output_path)
        self.data_section = data_section
        self.trans_frame = trans_frame
    
    def gen_block(self, config, strategy):
        self.mode = ''.join([config['attack_priv'], config['attack_addr']])

        assert strategy in [EncodeType.FUZZ_FRONTEND, EncodeType.FUZZ_BACKEND,\
            EncodeType.FUZZ_PIPELINE, EncodeType.FUZZ_DEFAULT]
        self.strategy = strategy

        self.delay_block = DelayBlock(self.extension, self.output_path, config['delay_len'], config['delay_float_rate'], config['delay_mem'])
        self.delay_block.gen_instr()

        self.return_block = ReturnVictimBlock(self.extension, self.output_path)
        self.return_block.gen_instr()

        tmp_random_state = random.getstate()
        random.seed(config['access_seed'])
        self.access_secret_block = AccessSecretBlock(self.extension, self.output_path, \
            config['access_secret_li'], config['access_secret_mask'],\
            config['train_priv'], config['train_addr'],\
            config['attack_priv'], config['attack_addr'])
        self.access_secret_block.gen_instr()
        random.setstate(tmp_random_state)

        self.encode_block = EncodeBlock(self.extension, self.output_path, self.access_secret_block.secret_reg, self.strategy)

        self.trigger_block = TriggerBlock(self.extension, self.output_path, self.delay_block.result_reg,\
            self.return_block.entry, self.access_secret_block.entry, config['trigger_type'])
        self.trigger_block.gen_instr()

        self.encode_block.trigger_type = self.trigger_block.trigger_type
        self.encode_block.gen_instr()

        self.warm_up_block = WarmUpVictimBlock(self.extension, self.output_path, config['warm_up'])
        self.warm_up_block.gen_instr()

        block_list = [self.delay_block, self.trigger_block, self.access_secret_block, self.encode_block, self.return_block]
        self.load_init_block = LoadInitTriggerBlock(self.swap_idx, self.extension, self.output_path, block_list, self.delay_block, self.trigger_block, self.trans_frame.random_data_block, self.mode)
        self.load_init_block.gen_instr()
        self.temp_load_init_block = self.load_init_block

        align_size = 64
        inst_len = self.load_init_block._get_inst_len() + self.warm_up_block._get_inst_len()
        nop_inst_len = (inst_len + align_size + align_size - 1) // align_size * align_size - inst_len
        
        self.nop_block = NopBlock(self.extension, self.output_path, nop_inst_len)
        self.nop_block.gen_instr()

        self.trigger_type = self.trigger_block.trigger_type

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
    
    def leak_reduce(self, encode_list):
        self.encode_block.leak_reduce(encode_list)

    def mutate_access(self, config):
        self.mode = ''.join([config['attack_priv'], config['attack_addr']])
        random.seed(config['access_seed'])
        self.access_secret_block = AccessSecretBlock(self.extension, self.output_path,\
            config['access_secret_li'], config['access_secret_mask'],\
            config['train_priv'], config['train_addr'], config['attack_priv'], config['attack_addr'])
        self.access_secret_block.gen_instr()

        self.encode_block = EncodeBlock(self.extension, self.output_path, self.access_secret_block.secret_reg, EncodeType.FUZZ_DEFAULT)
        self.encode_block.trigger_type = self.trigger_block.trigger_type
        self.encode_block.gen_instr()

        self.load_init_block = copy.deepcopy(self.temp_load_init_block)

    def mutate_encode(self, config):
        self.mode = ''.join([config['attack_priv'], config['attack_addr']])
        random.seed(config['leak_seed'])
        self.encode_block = EncodeBlock(self.extension, self.output_path, self.access_secret_block.secret_reg, config['encode_fuzz_type'], config['encode_block_len'], config['encode_block_num'])
        self.encode_block.trigger_type = self.trigger_block.trigger_type
        self.encode_block.gen_instr()

        old_inst_len = self.load_init_block._get_inst_len()
        self.load_init_block = copy.deepcopy(self.temp_load_init_block)
        init_block_list = [self.delay_block, self.trigger_block, self.access_secret_block, self.encode_block, self.return_block]
        self.load_init_block.update_init_seq(init_block_list)
        new_inst_len = self.load_init_block._get_inst_len()

        self.nop_block = NopBlock(self.extension, self.output_path, self.nop_block.c_nop_len + old_inst_len - new_inst_len)
        self.nop_block.gen_instr()
    
    def clear_encode(self):
        self.encode_block = EncodeBlock(self.extension, self.output_path, self.access_secret_block.secret_reg, EncodeType.FUZZ_DEFAULT)
        self.encode_block.gen_instr()

    def record_fuzz(self):
        block_list = [self.warm_up_block, self.delay_block, self.trigger_block, self.access_secret_block, self.encode_block]
        record = self._base_record_fuzz(block_list)
        record['return_front'] = self.return_front
        return 'victim', record

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
        self._set_section(text_swap_section, empty_section, [self.warm_up_block])
        self._set_section(text_swap_section, self.data_section, [self.load_init_block])
        self._set_section(text_swap_section, empty_section, [self.nop_block, self.delay_block, self.trigger_block])
        
        if not self.return_front:
            self._set_section(text_swap_section, empty_section, [self.access_secret_block])
            self._set_section(text_swap_section, empty_section, [self.encode_block, self.return_block])
        else:
            self._set_section(text_swap_section, empty_section, [self.return_block])
            self._set_section(text_swap_section, empty_section, [self.access_secret_block])
            self._set_section(text_swap_section, empty_section, [self.encode_block])
    
    def need_train(self):
        return TriggerType.need_train(self.trigger_block.trigger_type)

            




        

