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
        self.victim_privilege = victim_privilege
        self.virtual = virtual
        self.block_param["secret_protect_param"][
            "victim_privilege"
        ] = self.victim_privilege
        self.block_param["secret_protect_param"]["virtual"] = self.virtual
        self.output_path = output_path

    def _generate_sections(self):
        block_index = [
            ("_init", InitBlock),
            ("mtrap", MTrapBlock),
            ("strap", STrapBlock),
            ("secret_protect", SecretProtectBlock),
            ("exit", ExitBlock),
            ("return", ReturnBlock),
            ("delay", DelayBlock),
            ("predict", PredictBlock),
            ("run_time", RunTimeBlock),
            ("access_secret",AccessSecretBlock),
            ("encode", EncodeBlock),
            ("decode_call", DecodeCallBlock),
            ("decode", DecodeBlock),
        ]

        self.graph = {}
        for block_type, block_construct in block_index:
            block = block_construct(self.extension, self.block_param[block_type + "_param"], self.output_path)
            self.graph[block_type] = block

        for block_type, block_construct in block_index:
            self.graph[block_type].gen_instr(self.graph)

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

        mtrap_block = ["mtrap", "secret_protect"]
        strap_block = ["strap"]
        poc_block = ["decode"]
        payload_block = ["_init", "run_time", "decode_call", "exit", "delay", "predict"]
        if self.graph["predict"].predict_kind == "branch_not_taken":
            payload_block.extend(["return", "access_secret", "encode"])
        else:
            payload_block.extend(["access_secret", "encode", "return"])

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
                self.graph["mtrap"].entry,
                self.graph["secret_protect"].entry,
                "mtrap_stack_bottom",
            ]
        )
        strap_section.add_global_label(
            [self.graph["strap"].entry, "strap_stack_bottom"]
        )
        text_section.add_global_label([self.graph["_init"].entry])

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
