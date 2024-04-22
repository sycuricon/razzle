import os
import random
import sys
from BuildManager import *
from SectionUtils import *
from TransBlockUtils import *

from payload.Instruction import *
from payload.MagicDevice import *
from payload.Block import *


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
