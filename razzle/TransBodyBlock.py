import os
import random
import sys
from enum import Enum
from BuildManager import *
from SectionUtils import *
from SectionManager import *
from TransBlockUtils import *

from payload.Instruction import *
from payload.MagicDevice import *
from payload.Block import *

class DelayBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('delay_block', extension, output_path)
        self.float_rate = random.random() * 0.2 + 0.4 # 0.4 ~ 0.6
        self.delay_len = random.randint(4, 8)

    def _gen_dep_list(self):
        self.GPR_list = [
            reg for reg in reg_range if reg not in ["A0", "ZERO"]
        ]
        self.FLOAT_list = float_range
        dep_list = []
        for _ in range(self.delay_len):
            if random.random() < self.float_rate:
                dep_list.append(random.choice(self.FLOAT_list))
            else:
                dep_list.append(random.choice(self.GPR_list))
        dep_list.append(random.choice(self.GPR_list))
        return dep_list

    def _gen_inst_list(self, dep_list):
        block = BaseBlock(f'{self.name}_body', self.extension, None, True)

        for i, src in enumerate(dep_list[0:-1]):
            dest = dep_list[i + 1]
            if src in self.GPR_list and dest in self.FLOAT_list:
                block.inst_list.append(
                    Instruction(f"fcvt.s.lu   {dest.lower()}, {src.lower()}")
                )
            elif src in self.FLOAT_list and dest in self.GPR_list:
                block.inst_list.append(
                    Instruction(f"fcvt.lu.s   {dest.lower()}, {src.lower()}")
                )
            elif src in self.FLOAT_list and dest in self.FLOAT_list:
                while True:
                    instr = Instruction()
                    instr.set_extension_constraint(
                        [
                            extension
                            for extension in [
                                "RV_D",
                                "RV64_D",
                                "RV_F",
                                "RV64_F",
                                "RV32_C_F",
                                "RV_C_D",
                            ]
                            if extension in self.extension
                        ]
                    )
                    instr.set_category_constraint(["FLOAT"])

                    def c_dest(name, frd):
                        return use_frd(name) and use_frs1(name) and frd == dest

                    instr.add_constraint(c_dest, ["NAME", "FRD"])
                    instr.solve()

                    freg_list = [
                        freg for freg in ["FRS1", "FRS2", "FRS3"] if instr.has(freg)
                    ]
                    for freg in freg_list:
                        if freg == src:
                            break
                    else:
                        instr[random.choice(freg_list)] = src

                    if instr.has("FRD"):
                        block.inst_list.append(instr)
                        break

            elif src in self.GPR_list and dest in self.GPR_list:
                while True:
                    instr = Instruction()
                    instr.set_extension_constraint(
                        [
                            extension
                            for extension in ["RV_M", "RV64_M"]
                            if extension in self.extension
                        ]
                    )
                    instr.set_category_constraint(["ARITHMETIC"])

                    def c_dest(name, rd):
                        return use_rs1(name) and rd == dest

                    instr.add_constraint(c_dest, ["NAME", "RD"])
                    instr.solve()

                    if instr.has("RS1") and instr["RS1"] != src:
                        if instr.has("RS2"):
                            if random.random() < 0.5:
                                instr["RS1"] = src
                            else:
                                instr["RS2"] = src
                        else:
                            instr["RS1"] = src

                    if instr.has("RS1") and instr["RS1"] not in self.GPR_list:
                        instr["RS1"] = random.choice(self.GPR_list)
                    if instr.has("RS2") and instr["RS2"] not in self.GPR_list:
                        instr["RS2"] = random.choice(self.GPR_list)

                    if instr.has("RD"):
                        block.inst_list.append(instr)
                        break
        
        self._add_inst_block(block)
    
    def _gen_block_begin(self):
        inst_begin = [
            'INFO_DELAY_START',
        ]
        self._load_inst_str(inst_begin)
    
    def _gen_block_end(self):
        reg = self.result_reg.lower()
        imm = random.randint(-0x800, 0x7ff)

        inst_end = [
            f'{self.name}_delay_end:',
            f'addi {reg}, {reg}, {imm}',
            'INFO_DELAY_END',
        ]
        self._load_inst_str(inst_end)

    def gen_instr(self):
        self._gen_block_begin()
        do_random = random.choice([True, False, False, False])
        if do_random:
            dep_list = self._gen_dep_list()
            self._gen_inst_list(dep_list)
            self.result_reg = dep_list[-1]
        else:
            inst_list = [
                f'{self.name}_body:',
                'fcvt.s.lu fa4, t0',
                'fcvt.s.lu fa5, t1',
                'fdiv.s	fa5, fa5, fa4',
                'fdiv.s	fa5, fa5, fa4',
                'fdiv.s	fa5, fa5, fa4',
                'fdiv.s	fa5, fa5, fa4',
                'fdiv.s	fa5, fa5, fa4',
                'fcvt.lu.s t0, fa5',
            ]
            self._load_inst_str(inst_list, mutate=True)
            self.result_reg = 'T0'
        self._gen_block_end()

class NopBlock(TransBlock):
    def __init__(self, extension, output_path, block_name, c_nop_len):
        super().__init__(block_name, extension, output_path)
        self.c_nop_len = c_nop_len

    def gen_instr(self):
        inst_list = [
            'c.nop'
        ] * self.c_nop_len

        self._load_inst_str(inst_list)

class TriggerType(Enum):
    LOAD_STORE = 0
    LOAD_STORE_SP = 1
    AMO = 2
    V4 = 3
    BIM = 4
    BTB = 5
    RSB = 6
    JMP = 7
    ARITHMETIC = 8
    FLOAT = 9
    LEN = 10

    def random_choice():
        data = random.choice([TriggerType(i) for i in range(10)])
        return data
    
class TriggerBlock(TransBlock):
    def __init__(self, extension, output_path, dep_reg, ret_label, train_label):
        super().__init__('trigger_block', extension, output_path)
        self.dep_reg = dep_reg
        self.ret_label  = ret_label
        self.train_label = train_label
        self.trigger_type = TriggerType.random_choice()
    
    def gen_instr(self):
        block = BaseBlock(self.entry, self.extension, None, True)
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

    def _gen_block_begin(self):
        inst_list_begin = [
            'INFO_TEXE_START',
        ]
        self._load_inst_str(inst_list_begin)
    
    def gen_instr(self):
        self._gen_block_begin()
        
        inst_list = [
            f'begin_access_secret:',
            f'la t0, {self.name}_target_offset',
            'ld t1, 0(t0)',
            'la t0, trapoline',
            'add t0, t0, t1',
            'lb t0, 0(t0)',
        ]
        self._load_inst_str(inst_list, mutate=True)

        data_list = [
            f'{self.name}_target_offset:',
            '.dword secret + LEAK_TARGET - trapoline',
        ]
        self._load_data_str(data_list)

class EncodeBlock(TransBlock):
    def __init__(self, extension, output_path, ret_label):
        super().__init__('encode_block', extension, output_path)
        # self.leak_kind = random.choice(["cache", "FPUport", "LSUport"])
        self.leak_kind = random.choice(["cache"])
        self.ret_label = ret_label

    def _gen_block_end(self):

        inst_exit = [
            "encode_exit:",
            "INFO_TEXE_END",
            f"j {self.ret_label}",
        ]
        self._load_inst_str(inst_exit)

    def gen_instr(self):
        match (self.leak_kind):
            case "cache" | "FPUport" | "LSUport":
                self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], f"template/trans/encode_block.{self.leak_kind}.text.S"), mutate=True)
            case _:
                raise f"leak_kind cannot be {self.leak_kind}"
            
        self._gen_block_end()

class ReturnBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('return_block', extension, output_path)

    def gen_instr(self):
        self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/return_block.text.S"))

class LoadInitBlock(TransBlock):
    def __init__(self, depth, extension, output_path, init_block_list, delay_block, trigger_block, ret_label, train_label, do_train):
        super().__init__(f'load_init_block_{depth}', extension, output_path)
        self.delay_block = delay_block
        self.trigger_block = trigger_block
        self.ret_label = ret_label
        self.train_label = train_label
        self.init_block_list = init_block_list
        self.do_train = do_train

    def _gen_init_code(self):
        for block in self.init_block_list:
            block._compute_need_inited()
        for i in range(1, len(self.init_block_list)):
            self.init_block_list[i]._inited_posted_process(self.init_block_list[i-1].succeed_inited)
        
        need_inited = set()
        for block in self.init_block_list:
            need_inited.update(block.need_inited)
        need_inited.difference_update({'A0', 'ZERO'})

        self.float_init_list = []
        self.GPR_init_list = []

        has_t0 = False
        if 'T0' in need_inited:
            has_t0 = True
            need_inited.difference_update({'T0'})

        for reg in need_inited:
            if reg.startswith('F'):
                self.float_init_list.append(reg)
            else:
                self.GPR_init_list.append(reg)
        self.GPR_init_list.append('A0')
        if has_t0:
            self.GPR_init_list.append('T0')
        
        inst_list = [
            f"la t0, {self.name}_delay_data_table",
        ]
        data_list = [
            f"{self.name}_delay_data_table:"
        ]

        table_index = 0
        for freg in self.float_init_list:
            inst_list.append(f"fld {freg.lower()}, {table_index*8}(t0)")
            data_list.append(f".dword {hex(random.randint(0, 2**64))}")
            table_index += 1
        for reg in self.GPR_init_list:
            inst_list.append(f"ld {reg.lower()}, {table_index*8}(t0)")
            data_list.append(f".dword {hex(random.randint(0, 2**64))}")
            table_index += 1

        self._load_inst_str(inst_list)
        self._load_data_str(data_list)
    
    def _simulate_dep_reg_result(self):
        inst_block_list = [self.inst_block_list, self.delay_block.inst_block_list]
        data_list = [self.data_list, self.delay_block.data_list]
        dump_result = inst_simlutor(self.baker, inst_block_list, data_list)
        return dump_result[self.delay_block.result_reg]

    def _compute_trigger_param(self):
        trigger_inst = self.trigger_block.trigger_inst
        trigger_type = self.trigger_block.trigger_type

        match(trigger_type):
            case TriggerType.LOAD_STORE | TriggerType.LOAD_STORE_SP:
                address_base = random.choice(['secret_page_base', 'random_data_block_page_base'])
                trigger_param = f'{address_base} - {hex(self.dep_reg_result)}'
            case TriggerType.AMO:
                address_base = random.choice(['secret_page_base', 'random_data_block_page_base'])
                trigger_param = f'{address_base} - {hex(self.dep_reg_result)} + {hex(random.randint(-0x800, 0x7ff))}'
            case TriggerType.V4:
                trigger_param = f'access_secret_block_target_offset - {hex(self.dep_reg_result)}'
            case TriggerType.BIM:
                branch_success = self.do_train and trigger_inst['LABEL'] == self.ret_label\
                    or not self.do_train and trigger_inst['LABEL'] == self.train_label
                match((branch_success, trigger_inst['NAME'])):
                    case (True, 'BEQ') | (False, 'BNE') | (False, 'BLT') | (True, 'BGE') | (False, 'BLT') | (True, 'BGE'):
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
                if self.do_train:
                    trigger_param = f'{self.train_label} - {hex(self.dep_reg_result)} - {hex(trigger_inst_imm)}'
                else:
                    trigger_param = f'{self.ret_label} - {hex(self.dep_reg_result)} - {hex(trigger_inst_imm)}'
            case TriggerType.ARITHMETIC | TriggerType.FLOAT | TriggerType.JMP:
                trigger_param = random.randint(0, 2**64-1)
            case _:
                raise "the trigger type is invalid"

        return trigger_param

    def gen_instr(self):
        self._gen_init_code()
        self.dep_reg_result = self._simulate_dep_reg_result()
        self.trigger_param = self._compute_trigger_param()

        a0_data_asm = RawInstruction(f'.dword {self.trigger_param}')
        if self.GPR_init_list[-1] == 'T0':
            self.data_list[-2] = a0_data_asm
        else:
            self.data_list[-1] = a0_data_asm

class TransVictimManager(TransBaseManager):
    def __init__(self, config, extension, victim_privilege, virtual, output_path, trans_frame, depth):
        super().__init__(config, extension, victim_privilege, virtual, output_path)
        self.trans_frame = trans_frame
        self.depth = depth
    
    def gen_block(self):
        self.delay_block = DelayBlock(self.extension, self.output_path)
        self.return_block = ReturnBlock(self.extension, self.output_path)
        self.access_secret_block = AccessSecretBlock(self.extension, self.output_path)
        self.encode_block = EncodeBlock(self.extension, self.output_path, self.return_block.entry)

        self.delay_block.gen_instr()
        self.return_block.gen_instr()
        self.access_secret_block.gen_instr()
        self.encode_block.gen_instr()

        self.trigger_block = TriggerBlock(self.extension, self.output_path, self.delay_block.result_reg, self.return_block.entry, self.access_secret_block.entry)
        self.trigger_block.gen_instr()

        block_list = [self.delay_block, self.trigger_block, self.access_secret_block, self.encode_block, self.return_block]
        self.load_init_block = LoadInitBlock(self.depth, self.extension, self.output_path, block_list, self.delay_block, self.trigger_block, self.return_block.entry, self.access_secret_block.entry, False)

        self.load_init_block.gen_instr()

        inst_len = self.load_init_block._get_inst_len() + self.delay_block._get_inst_len()\
              + self.trigger_block._get_inst_len() - 1
        nop_inst_len = ((inst_len + 8 + 8 - 1) // 8 * 8 - inst_len) * 2
        
        self.nop1_block = NopBlock(self.extension, self.output_path, 'nop_name', nop_inst_len)
        self.nop1_block.gen_instr()

    def _generate_sections(self):

        text_swap_section = self.section[".text_swap"] = FuzzSection(
            ".text_swap", Flag.U | Flag.X | Flag.R
        )

        empty_section = FuzzSection(
            "", 0
        )

        self._set_section(text_swap_section, self.trans_frame.data_frame_section,[self.load_init_block])
        self._set_section(text_swap_section, empty_section, [self.nop1_block, self.delay_block, self.trigger_block])

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

    def _distribute_address(self):
        offset = 0
        length = Page.size
        self.section[".text_swap"].get_bound(
            self.virtual_memory_bound[0][0] + offset, self.memory_bound[0][0] + offset, length
        )




        

