import os
import random
import sys
from BuildManager import *
from SectionUtils import *

from payload.Instruction import *
from payload.MagicDevice import *
from payload.Block import *


class TransBlock:
    def __init__(self, name, depth, extension, fuzz_param, output_path):
        self.name = f'{name}_{depth}'
        self.depth = depth
        self.entry = self.name + "_entry"
        self.inst_list = []
        self.data_list = []
        self.extension = extension
        self.strategy = fuzz_param["strategy"]
        assert (
            self.strategy == "default" or self.strategy == "random"
        ), "strategy must be default or random"
        self.baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]},
            os.path.join(output_path, self.name),
        )

    def _load_file_asm(self, file_name, is_raw = True):
        # file_name=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..',file_name)
        with open(file_name, "rt") as file:
            file_list = file.readlines()
        if is_raw:
            inst_list = self._load_raw_asm(file_list)
        else:
            inst_list = self._load_str_asm(file_list)
        return inst_list

    def _load_str_asm(self, str_list):
        inst_list = []
        for str_element in str_list:
            str_element = str_element.strip()
            try:
                inst = Instruction(str_element)
            except:
                inst = RawInstruction(str_element)
            inst_list.append(inst)
        return inst_list
    
    def _load_raw_asm(self, str_list):
        inst_list = []
        for str_element in str_list:
            inst = RawInstruction(str_element.strip())
            inst_list.append(inst)
        return inst_list

    def gen_instr(self, graph):
        match self.strategy:
            case "default":
                self.gen_default(graph)
            case "random":
                self.gen_random(graph)
            case _:
                self.gen_strategy(graph)
    
    def _gen_random(self, block_cnt=3):
        return []

    def gen_random(self, graph):
        raise "Error: gen_random not implemented!"

    def gen_default(self, graph):
        raise "Error: gen_default not implemented!"

    def gen_strategy(self, graph):
        raise "Error: gen_dstrategy not implemented!"

    def gen_asm(self):
        inst_asm_list = []
        inst_asm_list.append(f"{self.name}:\n")
        for item in self.inst_list:
            inst_asm_list.append(item.to_asm() + "\n")
        data_asm_list = []
        data_asm_list.append(f"{self.name}_data:\n")
        for item in self.data_list:
            data_asm_list.append(item.to_asm() + "\n")
        return inst_asm_list, data_asm_list

    def work(self):
        return len(self.extension) > 0