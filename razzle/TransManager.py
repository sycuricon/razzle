import os
from SectionManager import *
from SectionUtils import *
from TransBlock import *


class FuzzSection(Section):
    def __init__(self, name, flag):
        super().__init__(name, flag)
        self.inst_list = []

    def add_inst_list(self, list):
        self.inst_list.extend(list)
        self.inst_list.append("\n")

    def _generate_body(self, is_variant):
        return self.inst_list


class TransManager(SectionManager):
    def __init__(self, config, victim_privilege, virtual, output_path):
        super().__init__(config)
        self.transblock = {}
        self.extension = [
            "RV_I",
            "RV64_I",
            "RV_ZICSR",
            "RV_F",
            "RV64_F",
            "RV_D",
            "RV64_D",
            "RV_A",
            "RV64_A",
            "RV_M",
            "RV64_M",
        ]
        self.block_param = config["block_param"]
        self.transient_depth = config["transient_depth"]
        self.victim_privilege = victim_privilege
        self.virtual = virtual
        self.block_param["secret_protect_block_param"][
            "victim_privilege"
        ] = self.victim_privilege
        self.block_param["secret_protect_block_param"]["virtual"] = self.virtual
        self.output_path = output_path

        self.block_construct = {
            "init_block": InitBlock,
            "mtrap_block": MTrapBlock,
            "strap_block": STrapBlock,
            "secret_protect_block": SecretProtectBlock,
            "exit_block": ExitBlock,
            "decode_call_block": DecodeCallBlock,
            "decode_block": DecodeBlock,
            "delay_block": DelayBlock,
            "predict_block": PredictBlock,
            "run_time_block": RunTimeBlock,
            "transient_block": TransientBlock,
            "access_secret_block": AccessSecretBlock,
            "encode_block": EncodeBlock,
            "return_block": ReturnBlock,
        }

    def _generate_sections(self):
        self.graph = {}
        self.graph["depth"] = self.transient_depth
        
        block_instr_gen_order = []

        train_vicitm_block_type = {
            "run_time":["run_time_block"],
            "trigger":["delay_block", "predict_block"],
            "transient":["transient_block"],
            "victim":["access_secret_block","encode_block"],
            "return":["return_block"],
        }

        train_block_array = []
        for depth in range(self.transient_depth,0,-1):
            train_block_type = []
            train_block_type.extend(train_vicitm_block_type['trigger'])
            if depth == self.transient_depth:
                transient_type = train_vicitm_block_type["victim"]
            else:
                transient_type = train_vicitm_block_type["transient"]
            if self.block_param["predict_block_param"]["predict_kind"] == "branch_not_taken":
                train_block_type.extend(train_vicitm_block_type["return"])
                train_block_type.extend(transient_type)
            else:
                train_block_type.extend(transient_type)
                train_block_type.extend(train_vicitm_block_type["return"])
            train_block_type.extend(train_vicitm_block_type["run_time"])
            
            block_name_array = []
            for block_type in train_block_type:
                block_name = f'{block_type}_{depth}'
                block = self.block_construct[block_type](depth, self.extension, self.block_param[block_type + "_param"], self.output_path)
                self.graph[block_name] = block
                block_name_array.append(block_name)
            
            block_instr_gen_order.extend(block_name_array)
            train_block_array.insert(0, (block_name_array[-1],block_name_array[0:-1]))

        main_block_type = [
            "mtrap_block",
            "strap_block",
            "secret_protect_block",
            "init_block",
            "decode_call_block",
            "exit_block",
            "decode_block",
        ]

        for block_type in main_block_type:
            block_name = f'{block_type}_1'
            block = self.block_construct[block_type](1 ,self.extension, self.block_param[block_type + "_param"], self.output_path)
            self.graph[block_name] = block
            block_instr_gen_order.append(block_name)
        
        print(block_instr_gen_order)
        for block_name in block_instr_gen_order:
            self.graph[block_name].gen_instr(self.graph)
        
        mtrap_block = ["mtrap_block_1", "secret_protect_block_1"]
        strap_block = ["strap_block_1"]
        poc_block = ["decode_block_1"]
        
        payload_block = ["init_block_1"]
        for train_block in train_block_array:
            payload_block.append(train_block[0])
        payload_block.extend(["decode_call_block_1","exit_block_1"])
        for train_block in train_block_array:
            payload_block.extend(train_block[1])

        text_section = self.section[".text"] = FuzzSection(
            ".text", Flag.U | Flag.X | Flag.R
        )
        data_section = self.section[".data"] = FuzzSection(
            ".data", Flag.U | Flag.W | Flag.R
        )
        mtrap_section = self.section[".mtrap"] = FuzzSection(
            ".mtrap", Flag.X | Flag.R | Flag.W
        )
        strap_section = self.section[".strap"] = FuzzSection(
            ".strap", Flag.X | Flag.R | Flag.W
        )
        poc_section = self.section[".poc"] = FuzzSection(
            ".poc", Flag.U | Flag.X | Flag.R
        )

        def set_section(text_section, data_section, block_list):
            for block_index in block_list:
                block = self.graph[block_index]
                inst_list, data_list = block.gen_asm()
                text_section.add_inst_list(inst_list)
                data_section.add_inst_list(data_list)

        set_section(mtrap_section, mtrap_section, mtrap_block)
        set_section(strap_section, strap_section, strap_block)
        set_section(poc_section, poc_section, poc_block)
        set_section(text_section, data_section, payload_block)
        mtrap_section.add_global_label(
            [
                self.graph["mtrap_block_1"].entry,
                self.graph["secret_protect_block_1"].entry,
                "mtrap_stack_bottom",
            ]
        )
        strap_section.add_global_label(
            [self.graph["strap_block_1"].entry, "strap_stack_bottom"]
        )
        text_section.add_global_label([self.graph["init_block_1"].entry])

    def _distribute_address(self):
        offset = 0
        length = Page.size
        self.section[".mtrap"].get_bound(
            self.memory_bound[0][0] + offset, self.memory_bound[0][0] + offset, length
        )

        offset += length
        length = Page.size
        self.section[".strap"].get_bound(
            self.virtual_memory_bound[0][0] + offset,
            self.memory_bound[0][0] + offset,
            length,
        )

        offset += length
        length = Page.size
        self.section[".text"].get_bound(
            self.virtual_memory_bound[0][0] + offset,
            self.memory_bound[0][0] + offset,
            length,
        )

        offset += length
        length = Page.size
        self.section[".data"].get_bound(
            self.virtual_memory_bound[0][0] + offset,
            self.memory_bound[0][0] + offset,
            length,
        )

        offset = 0
        length = Page.size
        self.section[".poc"].get_bound(
            self.virtual_memory_bound[1][0] + offset,
            self.memory_bound[1][0] + offset,
            length,
        )

    def _write_headers(self, f, is_variant):
        f.write(f'#include "parafuzz.h"\n')
