import os
import random
import sys
from BuildManager import *
from SectionUtils import *
from TransBlockUtils import *

from payload.Instruction import *
from payload.MagicDevice import *
from payload.Block import *

class ReturnBlock(TransBlock):
    def __init__(self, extension, fuzz_param, output_path):
        super().__init__('return_block', extension, fuzz_param, output_path)

    def gen_default(self, graph):
        self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/return_block.text.S"))

class AccessSecretBlock(TransBlock):
    def __init__(self, extension, fuzz_param, output_path):
        super().__init__('access_secret_block', extension, fuzz_param, output_path)

    def _gen_block_begin(self, graph):
        inst_list_begin = [
            'INFO_TEXE_START',
        ]
        self._load_inst_str(inst_list_begin)
    
    def gen_default(self, graph):
        self._gen_block_begin(graph)
        
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
            '.space 0x8',
        ]
        self._load_data_str(data_list)

class RandomDataBlock(TransBlock):
    def __init__(self, depth, max_depth, extension, fuzz_param, output_path):
        super().__init__('random_data_block', depth, max_depth, extension, fuzz_param, output_path)
        assert (
            self.strategy == "default"
        ), f"strategy of {self.name} must be default rather than {self.strategy}"
        self.page_num = fuzz_param['page_num']

    def gen_default(self, graph):
        def random_data_line(byte_num = 0x800):
            assert byte_num%64==0, "byte_num must be aligned to 64"
            for i in range(0, byte_num, 64):
                data = [hex(random.randint(0,0xffffffffffffffff)) for i in range(8)]
                dataline = " ,".join(data)
                self.data_list.append(RawInstruction(f'.dword {dataline}'))
        
        self.base_label = []

        for page_index in range(self.page_num):
            random_data_line(0x800)
            base_label = f'{self.name}_page_{page_index}'
            self.base_label.append(base_label)
            self.data_list.append(RawInstruction(f'{base_label}:'))
            random_data_line(0x800)

class EncodeBlock(TransBlock):
    def __init__(self, depth, max_depth, extension, fuzz_param, output_path):
        super().__init__('encode_block', depth, max_depth, extension, fuzz_param, output_path)
        self.leak_kind = fuzz_param["leak_kind"]
        assert self.leak_kind in [
            "cache",
            "FPUport",
            "LSUport",
        ], f"leak_kind must be 'cache', 'FPUport' or 'LSUport', rather than {self.leak_kind}"

    def gen_random(self, graph):
        raise "Error: gen_random not implemented!"

    def _gen_block_end(self, graph):
        return_block = graph[f"return_block_{self.depth}"]

        inst_exit = [
            "encode_exit:",
            "INFO_TEXE_END",
            f"j {return_block.entry}",
        ]
        self._load_inst_str(inst_exit)

    def gen_default(self, graph):
        match (self.leak_kind):
            case "cache" | "FPUport" | "LSUport":
                self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], f"template/trans/encode_block.{self.leak_kind}.text.S"), mutate=True)
            case _:
                raise f"leak_kind cannot be {self.leak_kind}"
            
        self._gen_block_end(graph)

class LoadInitBlock(TransBlock):
    def __init__(self, depth, max_depth, extension, fuzz_param, output_path):
        super().__init__('load_init_block', depth, max_depth, extension, fuzz_param, output_path)
        assert (
            self.strategy == "default"
        ), f"strategy of {self.name} must be default rather than {self.strategy}"
        self.load_init_entry = f'{self.name}_train_init_entry'

    def gen_default(self, graph):
        block_list = [graph[f'delay_block_{self.depth}'], graph[f'predict_block_{self.depth}']]
        if self.depth == self.max_depth:
            block_list.extend([graph[f'access_secret_block_{self.depth}'],graph[f'encode_block_{self.depth}']])
        else:
            block_list.extend([graph[f'transient_block_{self.depth}']])
        
        for block in block_list:
            block._compute_need_inited()
        for i in range(1, len(block_list)):
            block_list[i]._inited_posted_process(block_list[i-1].succeed_inited)
        
        need_inited = set()
        for block in block_list:
            need_inited.update(block.need_inited)
        need_inited.difference_update({'A0'})

        float_init_list = []
        GPR_init_list = []
        has_t0 = False
        for reg in need_inited:
            if reg == 'T0':
                has_t0 = True
                continue
            if reg.startswith('F'):
                float_init_list.append(reg)
            else:
                GPR_init_list.append(reg)
        if has_t0:
            GPR_init_list.append('T0')
        
        inst_list = [
            "auipc t0, 0",
            "add ra, t0, zero",
            "jalr x0, 12(ra)",
            f"{self.load_init_entry}:",
            f"la t0, {self.name}_delay_data_table",
        ]
        table_index = 0
        for freg in float_init_list:
            inst_list.append(f"fld {freg.lower()}, {table_index*8}(t0)")
            table_index += 1
        for reg in GPR_init_list:
            inst_list.append(f"ld {reg.lower()}, {table_index*8}(t0)")
            table_index += 1

        data_list = [
            f"{self.name}_delay_data_table:"
        ]
        for _ in range(len(need_inited)):
            data_list.append(f".dword {hex(random.randint(0, 2**64))}")

        nop_line = 8 + 8 - (len(inst_list)) % 8
        for i in range(nop_line):
            inst_list.append("nop")

        self._load_inst_str(inst_list)
        self._load_data_str(data_list)

        delay_block = graph[f'delay_block_{self.depth}']
        predict_block = graph[f'predict_block_{self.depth}']
        dump_result = inst_simlutor(self.baker, [self.inst_block_list, delay_block.inst_block_list],\
                                     [self.data_list, delay_block.data_list])
        delay_block.result_imm = dump_result[delay_block.result_reg]
        predict_block.dep_val = delay_block.result_imm

class DelayBlock(TransBlock):
    def __init__(self, depth, max_depth, extension, fuzz_param, output_path):
        super().__init__('delay_block', depth, max_depth, extension, fuzz_param, output_path)
        self.float_rate = fuzz_param["float_rate"]
        self.delay_len = fuzz_param["delay_len"]

    def _gen_dep_list(self):
        self.GPR_list = [
            reg for reg in reg_range if reg not in ["A0", "ZERO", "T0", "T1"]
        ]
        self.FLOAT_list = float_range
        dep_list = []
        for i in range(random.randint(self.delay_len - 1, self.delay_len + 1)):
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

    def gen_strategy(self, graph):
        dep_list = self._gen_dep_list()
        self._gen_block_begin(graph)
        self._gen_inst_list(dep_list)
        self._gen_block_end(graph)
        self.result_reg = dep_list[-1]
    
    def _gen_block_begin(self, graph):
        inst_begin = [
            'INFO_DELAY_START',
        ]
        self._load_inst_str(inst_begin)
    
    def _gen_block_end(self, graph):
        inst_end = [
            f'{self.name}_delay_end:',
            'INFO_DELAY_END',
        ]
        self._load_inst_str(inst_end)

    def gen_default(self, graph):
        self._gen_block_begin(graph)
        inst_list = [
            f'{self.name}_body:',
            f'la t0, {self.name}_delay_dummy1',
            'ld t0, 0(t0)',
            f'la t1, {self.name}_delay_dummy2',
            'ld t1, 0(t1)',
            'fcvt.s.lu fa4, t0',
            'fcvt.s.lu fa5, t1',
            'fdiv.s	fa5, fa5, fa4',
            'fdiv.s	fa5, fa5, fa4',
            'fdiv.s	fa5, fa5, fa4',
            'fdiv.s	fa5, fa5, fa4',
            'fdiv.s	fa5, fa5, fa4',
            'fcvt.lu.s t2, fa5',
        ]
        self._load_inst_str(inst_list, mutate=True)
        self._gen_block_end(graph)

        data_list = [
            f'{self.name}_delay_dummy1:',
            '.dword 0xa234b057963aef89',
            f'{self.name}_delay_dummy2:',
            '.dword 0x46fea3467def0136',
        ]
        self._load_data_str(data_list)

        self.result_reg = "t2".upper()
        # self.result_imm = 0


class PredictBlock(TransBlock):
    def __init__(self, depth, max_depth, extension, fuzz_param, output_path):
        super().__init__('predict_block', depth, max_depth, extension, fuzz_param, output_path)
        self.transient_entry = f'{self.name}_transient_entry'

        self.boot_victim = ['load', 'except', 'branch_not_taken', 'branch_taken', 'call', 'return']
        # self.boot_train  = ['return', 'except']
        self.boot_train  = ['return']
        # self.boot_train  = ['except', 'branch_not_taken', 'branch_taken', 'call', 'return']
        self.chain_victim = ['branch_not_taken', 'branch_taken', 'call', 'return']
        # self.chain_train  = ['branch_not_taken', 'branch_taken', 'call', 'return']
        self.chain_train  = ['call', 'return']
        
        if self.victim and self.boot:
            predict_pool = self.boot_victim
        elif not self.victim and self.boot:
            predict_pool = self.boot_train
        elif self.victim and not self.boot:
            predict_pool = self.chain_victim
        else:
            predict_pool = self.chain_train   
        
        self.predict_kind = random.choice(predict_pool)

    def gen_random(self, graph):
        raise "Error: gen_random not implemented!"

    def gen_default(self, graph):
        delay_block = graph[f"delay_block_{self.depth}"]
        load_init_block = graph[f'load_init_block_{self.depth}'] 
        self.dep_reg = delay_block.result_reg
        transient_block = graph[f"transient_block_{self.depth}"]\
            if self.depth != self.max_depth else graph[f"access_secret_block_{self.depth}"]
        return_block = graph[f"return_block_{self.depth}"]

        match (self.predict_kind):
            case "call":
                block = BaseBlock(self.entry, self.extension, graph, mutate=True)
                delay_link_inst = Instruction(f"add t0, {self.dep_reg.lower()}, a0")
                block.inst_list.append(delay_link_inst)
                self._add_inst_block(block)

                block = BaseBlock(self.transient_entry, self.extension, graph, mutate=True)
                call_inst = Instruction()
                call_inst.set_name_constraint(["JALR"])
                call_inst.set_category_constraint(["JUMP"])
                call_inst.set_extension_constraint(["RV_I"])

                def c_call(rd, rs1):
                    return rd == "RA" and rs1 == "T0"

                call_inst.add_constraint(c_call, ["RD", "RS1"], True)
                call_inst.solve()
                self.off_imm = call_inst["IMM"]
                block.inst_list.append(call_inst)

                self._add_inst_block(block)
            case "return":
                if self.boot:
                    block = BaseBlock(f'{self.name}_dummy', self.extension, graph, mutate=True)
                    block.inst_list.append(Instruction(f"add ra, {self.dep_reg.lower()}, a0"))
                    block.inst_list.append(Instruction("jalr zero, 0(ra)"))
                    self._add_inst_block(block)

                    block = BaseBlock(self.entry, self.extension, graph, mutate=True)
                    block.inst_list.append(Instruction(f"jal ra, {load_init_block.load_init_entry}"))
                    self._add_inst_block(block)
                    self.off_imm = 0
                else:
                    block = BaseBlock(self.entry, self.extension, graph, mutate=True)
                    block.inst_list.append(Instruction(f"add ra, {self.dep_reg.lower()}, a0"))
                    block.inst_list.append(Instruction("jalr zero, 0(ra)"))
                    self._add_inst_block(block)

                    inst_list = [
                        f'{self.transient_entry}:',
                        'auipc t0, 0',
                        'add ra, t0, x0',
                        'jalr x0, 12(ra)',
                        'jalr x0, 16(ra)',
                        'jalr ra, 16(t0)',
                    ]

                    self._load_inst_str(inst_list, mutate=True)
                    self.off_imm = 0
            case "branch_taken" | "branch_not_taken":
                block = BaseBlock(self.entry, self.extension, graph, mutate=True)

                off_inst = Instruction()
                off_inst.set_name_constraint(['ADDI'])
                off_inst.set_extension_constraint(["RV_I"])
                def delay_c_param(RD, RS1):
                    return (
                        RD == self.dep_reg
                        and RS1 == self.dep_reg
                    )
                off_inst.add_constraint(delay_c_param, ["RD", "RS1"])
                off_inst.solve()
                block.inst_list.append(off_inst)
                self.off_imm = off_inst['IMM']
                self._add_inst_block(block)

                block = BaseBlock(self.transient_entry, self.extension, graph, mutate=True)
                ret_inst = Instruction()
                ret_inst.set_category_constraint(["BRANCH"])
                ret_inst.set_extension_constraint(["RV_I"])
                if self.predict_kind == "branch_taken":
                    ret_inst.set_label_constraint([return_block.entry])
                else:
                    ret_inst.set_label_constraint([transient_block.entry])

                def c_param(RS1, RS2):
                    return (
                        RS1 == "A0"
                        and RS2 == self.dep_reg
                    )

                ret_inst.add_constraint(c_param, ["RS1", "RS2"])
                ret_inst.solve()

                self.branch_kind = ret_inst["NAME"]
                block.inst_list.append(ret_inst)
                self._add_inst_block(block)
            case "except":
                inst_list = [
                    f'{self.entry}:',
                ]
                if not self.victim:
                    inst_list.extend(
                        [
                            'la t0, secret',
                            'ld t0, 1000(t0)'
                        ]
                    )
                self._load_inst_str(inst_list, mutate=True)  
            case "load":
                block = BaseBlock(self.entry, self.extension, graph, mutate=True)
                block.inst_list.append(Instruction(f"add t1, a0, {self.dep_reg.lower()}"))
                block.inst_list.append(Instruction(f"sd zero, 0(t1)"))
                self._add_inst_block(block)
            case _:
                raise "Error: predict_kind not implemented!"

class RunTimeBlock(TransBlock):
    def __init__(self, depth, max_depth, extension, fuzz_param, output_path):
        super().__init__('run_time_block', depth, max_depth, extension, fuzz_param, output_path)

    def _gen_predict_param(self, graph):
        predict_block = graph[f"predict_block_{self.depth}"]
        transient_block = graph[f"transient_block_{self.depth}"]\
            if self.depth != self.max_depth else graph[f"access_secret_block_{self.depth}"]
        return_block = graph[f"return_block_{self.depth}"]
        delay_block = graph[f"delay_block_{self.depth}"]

        match (predict_block.predict_kind):
            case "call" | "return":
                train_param = f"{transient_block.entry} - {delay_block.result_imm} - {predict_block.off_imm}"
                victim_param = f"{return_block.entry} - {delay_block.result_imm} - {predict_block.off_imm}"
            case "branch_taken" | "branch_not_taken":
                delay_imm = (delay_block.result_imm + predict_block.off_imm) % 2**64
                match (predict_block.branch_kind):
                    case "BEQ":
                        train_param = delay_imm + 1 if delay_imm == 0 else delay_imm - 1
                        victim_param = delay_imm
                    case "BNE":
                        train_param = delay_imm
                        victim_param = (
                            delay_imm + 1 if delay_imm == 0 else delay_imm - 1
                        )
                    case "BLT":
                        delay_imm = Unsigned2Signed(delay_imm)
                        assert (
                            delay_imm != -(2 ** (64 - 1))
                            and delay_imm != 2 ** (64 - 1) - 1
                        )
                        train_param = random.randint(delay_imm, 2 ** (64 - 1))
                        victim_param = random.randint(-(2 ** (64 - 1)), delay_imm)
                    case "BGE":
                        delay_imm = Unsigned2Signed(delay_imm)
                        assert (
                            delay_imm != -(2 ** (64 - 1))
                            and delay_imm != 2 ** (64 - 1) - 1
                        )
                        train_param = random.randint(-(2 ** (64 - 1)), delay_imm)
                        victim_param = random.randint(delay_imm, 2 ** (64 - 1))
                    case "BLTU":
                        delay_imm = Signed2Unsigned(delay_imm)
                        assert delay_imm != 0 and delay_imm != 2**64 - 1
                        train_param = random.randint(delay_imm, 2**64)
                        victim_param = random.randint(0, delay_imm)
                    case "BGEU":
                        delay_imm = Signed2Unsigned(delay_imm)
                        assert delay_imm != 0 and delay_imm != 2**64 - 1
                        train_param = random.randint(0, delay_imm)
                        victim_param = random.randint(delay_imm, 2**64)
                    case _:
                        raise f"Error: branch_kind {predict_block.branch_kind} not implemented!"

                if predict_block.predict_kind == "branch_not_taken":
                    train_param, victim_param = victim_param, train_param
                # print(predict_block.branch_kind, delay_imm, train_param, victim_param)
            case "except":
                train_param = 0
                victim_param = 0
            case "load":
                train_param = f"{transient_block.name}_target_offset - {delay_block.result_imm}"
                victim_param = f"{transient_block.name}_target_offset - {delay_block.result_imm}"
            case _:
                raise "Error: predict_kind not implemented!"
        return victim_param, train_param

    def _gen_data_list(
        self,
        victim_predict_param,
        victim_offset_param,
        train_predict_param,
        train_offset_param,
        graph,
    ):
        delay_block = graph[f"delay_block_{self.depth}"]

        data_str_list = []

        data_str_list.append(f"{self.name}_train_param_table:")
        for i in range(self.train_loop):
            data_str_list.append(f"{self.name}_train_predict_param_{i}:")
            data_str_list.append(f".dword {train_predict_param}")
            data_str_list.append(f"{self.name}_train_delay_value_{i}:")
            data_str_list.append(f".dword {delay_block.result_imm}")

        data_str_list.append(f"{self.name}_train_offset_table:")
        for i in range(self.train_loop):
            data_str_list.append(f"{self.name}_train_offset_param_{i}:")
            data_str_list.append(f".dword {train_offset_param}")

        data_str_list.append(f"{self.name}_victim_param_table:")
        for i in range(self.victim_loop):
            data_str_list.append(f"{self.name}_victim_predict_param_{i}:")
            data_str_list.append(f".dword {victim_predict_param}")

        data_str_list.append(f"{self.name}_victim_offset_table:")
        for i in range(self.victim_loop):
            data_str_list.append(f"{self.name}_victim_offset_param_{i}:")
            data_str_list.append(f".dword {victim_offset_param}")
        
        self._load_data_str(data_str_list)

    def _gen_inst_list(self, graph):
        delay_block = graph[f"delay_block_{self.depth}"]
        predict_block = graph[f"predict_block_{self.depth}"]
        return_block = graph[f"return_block_{self.depth}"]
        load_init_block = graph[f'load_init_block_{self.depth}']
        if predict_block.predict_kind == "return" and predict_block.boot:
            train_entry = load_init_block.entry
            victim_entry = predict_block.entry
        else:
            train_entry = predict_block.entry
            victim_entry = load_init_block.entry
        
        if self.depth == self.max_depth:
            access_secret_block = graph[f"access_secret_block_{self.depth}"]

        inst_str_list = []
        # trap -> return, address stored in trap_return_rtap
        inst_str_list.append(f"la t0, {return_block.entry}")
        inst_str_list.append("la t1, trap_return_entry")
        inst_str_list.append("sd t0, 0(t1)")
        for i in range(self.train_loop):
            table_width = 2
            # return -> runtime, address stored in store_ra
            inst_str_list.append(f"la t0, {self.name}_train_{i}_end")
            inst_str_list.append(f"la t1, {return_block.name}_store_ra")
            inst_str_list.append("sd t0, 0(t1)")

            # predict param
            inst_str_list.append(f"la t0, {self.name}_train_param_table")
            inst_str_list.append(f"ld a0, {i*8*table_width}(t0)")
            inst_str_list.append(f"ld {delay_block.result_reg.lower()}, {i*8*table_width+8}(t0)")

            # offset param, stored in train_offset_table
            if self.depth == self.max_depth:
                inst_str_list.append(f"la t0, {self.name}_train_offset_table")
                inst_str_list.append(f"ld t1, {i*8}(t0)")
                inst_str_list.append(f"la t0, {access_secret_block.name}_target_offset")
                inst_str_list.append("sd t1, 0(t0)")

            # call function
            inst_str_list.append("INFO_TRAIN_START")
            inst_str_list.append(f"call {train_entry}")
            inst_str_list.append(f"{self.name}_train_{i}_end:")
            inst_str_list.append("INFO_TRAIN_END")

        for i in range(self.victim_loop):
            table_width = 1
            inst_str_list.append(f"la t0, {self.name}_victim_{i}_end")
            inst_str_list.append(f"la t1, {return_block.name}_store_ra")
            inst_str_list.append("sd t0, 0(t1)")

            inst_str_list.append(f"la t0, {self.name}_victim_param_table")
            inst_str_list.append(f"ld a0, {i*8*table_width}(t0)")

            if self.depth == self.max_depth:
                inst_str_list.append(f"la t0, {self.name}_victim_offset_table")
                inst_str_list.append(f"ld t1, {i*8}(t0)")
                inst_str_list.append(f"la t0, {access_secret_block.name}_target_offset")
                inst_str_list.append("sd t1, 0(t0)")

            inst_str_list.append("INFO_VCTM_START")
            inst_str_list.append(f"call {victim_entry}")
            inst_str_list.append(f"{self.name}_victim_{i}_end:")
            inst_str_list.append("INFO_VCTM_END")
        
        self._load_inst_str(inst_str_list)

    def gen_default(self, graph):
        predict_block = graph[f"predict_block_{self.depth}"]
        self.victim_loop = 1
        match(predict_block.predict_kind):
            case 'load' | 'except' | 'return':
                self.train_loop = 0
            case 'branch_not_taken' | 'branch_taken':
                self.train_loop = 2 if predict_block.boot else 1
            case 'call':
                self.train_loop = 1 if predict_block.boot else 0
            case _:
                raise "Error: predict_kind not implemented!"

        victim_predict_param, train_predict_param = self._gen_predict_param(graph)
        train_offset_param = 0
        victim_offset_param = "secret + LEAK_TARGET - trapoline"

        self._gen_data_list(
            victim_predict_param,
            victim_offset_param,
            train_predict_param,
            train_offset_param,
            graph,
        )
        self._gen_inst_list(graph)

class TransientBlock(TransBlock):
    def __init__(self, depth, max_depth, extension, fuzz_param, output_path):
        super().__init__('transient_block', depth, max_depth, extension, fuzz_param, output_path)
        if self.depth > 1:
            self.transient = True
    
    def _gen_block_begin(self, graph):
        inst_begin = [
            "INFO_TEXE_START"
        ]
        self._load_inst_str(inst_begin)
    
    def _gen_block_end(self, graph):
        return_block = graph[f'return_block_{self.depth}']
        inst_end = [
            f"{self.name}_exit:",
            "INFO_TEXE_END",
            f'j {return_block.entry}',
        ]
        self._load_inst_str(inst_end)
    
    def gen_random(self, graph):
        self._gen_block_begin(graph)
        self._add_inst_block_list(self._gen_random(graph, random.randint(3,5)))
        self._gen_block_end(graph)

    def gen_default(self, graph):
        predict_block = graph[f'predict_block_{self.depth + 1}']
        delay_block   = graph[f'delay_block_{self.depth + 1}']
        transient_block = graph[f'transient_block_{self.depth + 1}']\
            if self.depth + 1 < self.max_depth else\
            graph[f'access_secret_block_{self.depth + 1}']
        
        self._gen_block_begin(graph)
        block = BaseBlock(f'{self.name}_transient_train', self.extension, graph, mutate=True)
        match(predict_block.predict_kind):
            case 'branch_not_taken' | 'branch_taken':
                value1 = 0
                match(predict_block.branch_kind):
                    case 'BEQ' | 'BGE' | 'BGEU':
                        value2 = 0 if predict_block.predict_kind == 'branch_not_taken' else 1
                    case 'BNE' | 'BLT' | 'BLTU':
                        value2 = 1 if predict_block.predict_kind == 'branch_not_taken' else 0
                    case _:
                        raise f"Error: branch_kind {predict_block.branch_kind} not implemented!"
                block.inst_list.append(Instruction(f'li a0, {value1}'))
                block.inst_list.append(Instruction(f'li {predict_block.dep_reg}, {value2}'))
            case 'call':
                offset = - delay_block.result_imm - predict_block.off_imm
                block.inst_list.append(Instruction(f'la t0, {transient_block.entry}'))
                block.inst_list.append(Instruction(f'addi t0, t0, {offset}'))
            case 'return':
                pass
            case _:
                raise 'Error: predict_kind not implemented!'
        self._add_inst_block(block)
        block.inst_list.append(Instruction(f'jal zero, {predict_block.transient_entry}'))
        self._gen_block_end(graph)


def inst_simlutor(baker, inst_block_list_list, data_list_list):
    if not os.path.exists(baker.output_path):
        os.makedirs(baker.output_path)

    file_name = os.path.join(baker.output_path, "tmp.S")
    with open(file_name, "wt") as file:
        file.write('#include "boom_conf.h"\n')
        file.write('#include "encoding.h"\n')
        file.write('#include "parafuzz.h"\n')
        file.write(".section .text\n")
        file.write(f"li t0, 0x8000000a00007800\n")
        file.write("csrw mstatus, t0\n")
        for inst_block_list in inst_block_list_list:
            for block in inst_block_list:
                file.writelines(block.gen_asm())
                file.write("\n")
        file.write(".section .data\n")
        for data_list in data_list_list:
            for data in data_list:
                file.write(data.to_asm())
                file.write("\n")

    gen_elf = ShellCommand(
        "riscv64-unknown-elf-gcc",
        [
            "-march=rv64gc_zicsr",
            "-mabi=lp64f",
            "-mcmodel=medany",
            "-nostdlib",
            "-nostartfiles",
            "-I$RAZZLE_ROOT/template",
            "-I$RAZZLE_ROOT/template/trans",
            "-T$RAZZLE_ROOT/template/tmp/link.ld",
        ],
    )
    baker.add_cmd(gen_elf.save_cmd([file_name, "-o", "$OUTPUT_PATH/tmp"]))

    inst_cnt = ShellCommand(
        "riscv64-unknown-elf-objdump",
        ["-d", "$OUTPUT_PATH/tmp", "| grep -cE '^[[:space:]]+'"],
    )
    baker.add_cmd(inst_cnt.save_output("INST_CNT"))

    gen_dump = ShellCommand(
        "spike-solve", ["$OUTPUT_PATH/tmp", "$INST_CNT", "$OUTPUT_PATH/dump"]
    )
    baker.add_cmd(gen_dump.save_cmd())
    baker.run()

    with open(os.path.join(baker.output_path, "dump"), "rt") as file:
        reg_lines = file.readlines()
        dump_reg = {}
        for reg_line in reg_lines:
            key, value = reg_line.strip().split()
            dump_reg[key] = int(value, base=16)
        # print(dump_reg)
    return dump_reg
