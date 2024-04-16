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

    def _generate_body(self):
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
            "RV_C",
            "RV64_C",
            "RV_C_D",
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
            "decode_block": DecodeBlock,
            "load_init_block": LoadInitBlock,
            "delay_block": DelayBlock,
            "predict_block": PredictBlock,
            "run_time_block": RunTimeBlock,
            "transient_block": TransientBlock,
            "access_secret_block": AccessSecretBlock,
            "encode_block": EncodeBlock,
            "return_block": ReturnBlock,
            "random_data_block": RandomDataBlock,
        }
    
    def _block_construct(self, block_type_array, depth):
        block_name_array = []
        for block_type in block_type_array:
            block_name = f'{block_type}_{depth}'
            block = self.block_construct[block_type](depth, self.transient_depth, self.extension, self.block_param[block_type + "_param"], self.output_path)
            self.graph[block_name] = block
            self.block_instr_gen_order.append(block_name)
            block_name_array.append(block_name)
        return block_name_array

    def _generate_sections(self):
        self.graph = {}
        
        self.block_instr_gen_order = []

        system_block_type = [
            "secret_protect_block",
            "mtrap_block",
            "strap_block",
            "random_data_block",
        ]

        self._block_construct(system_block_type, 1)

        train_block_array = []
        for depth in range(self.transient_depth,0,-1):
            block_name_array = []
            train_block_type = ["delay_block", "predict_block"]
            block_name_array.extend(self._block_construct(train_block_type, depth))

            if depth == self.transient_depth:
                transient_type = ["access_secret_block","encode_block"]
            else:
                transient_type = ["transient_block"]
            if self.graph[block_name_array[-1]].predict_kind == 'branch_not_taken':
                train_block_type = ["return_block"]
                train_block_type.extend(transient_type)
            else:
                train_block_type = transient_type
                train_block_type.append("return_block")
            block_name_array.extend(self._block_construct(train_block_type, depth))

            train_block_type = ["load_init_block"]
            block_name_array.insert(0, self._block_construct(train_block_type, depth)[0])

            run_time_block = self._block_construct(['run_time_block'], depth)[0]

            train_block_array.insert(0, (run_time_block,block_name_array))

        main_block_type = [
            "init_block",
            "decode_block",
            "exit_block",
        ]

        self._block_construct(main_block_type, 1)
        
        for block_name in self.block_instr_gen_order:
            print(block_name)
            self.graph[block_name].gen_instr(self.graph)
        
        mtrap_block = ["mtrap_block_1", "secret_protect_block_1"]
        strap_block = ["strap_block_1"]
        random_data_block = ["random_data_block_1"]
        
        main_block = ["init_block_1"]
        for train_block in train_block_array:
            main_block.append(train_block[0])
        main_block.extend(["decode_block_1","exit_block_1"])

        mtrap_section = self.section[".mtrap"] = FuzzSection(
            ".mtrap", Flag.X | Flag.R | Flag.W
        )
        strap_section = self.section[".strap"] = FuzzSection(
            ".strap", Flag.X | Flag.R | Flag.W
        )
        data_section = self.section[".data"] = FuzzSection(
            ".data", Flag.U | Flag.W | Flag.R
        )
        random_data_section = self.section[".random_data"] = FuzzSection(
            ".random_data", Flag.U | Flag.W | Flag.R
        )
        text_section = self.section[".text"] = FuzzSection(
            ".text", Flag.U | Flag.X | Flag.R
        )
        train_section_array = []
        for i in range(self.transient_depth):
            section_name = f'.text_train_{i+1}'
            train_section = self.section[section_name] = FuzzSection(
                section_name, Flag.U | Flag.X | Flag.R
            )
            train_section_array.append(train_section)

        def set_section(text_section, data_section, block_list):
            for block_index in block_list:
                print(block_index)
                block = self.graph[block_index]
                inst_list, data_list = block.gen_asm()
                text_section.add_inst_list(inst_list)
                data_section.add_inst_list(data_list)

        set_section(mtrap_section, mtrap_section, mtrap_block)
        set_section(strap_section, strap_section, strap_block)
        set_section(text_section, data_section, main_block)
        set_section(text_section, random_data_section, random_data_block)
        for i in range(self.transient_depth):
            set_section(train_section_array[i], data_section, train_block_array[i][1])

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
        self.section[".data"].get_bound(
            self.virtual_memory_bound[0][0] + offset,
            self.memory_bound[0][0] + offset,
            length,
        )

        offset += length
        length = Page.size * self.graph['random_data_block_1'].page_num
        self.section[".random_data"].get_bound(
            self.virtual_memory_bound[0][0] + offset,
            self.memory_bound[0][0] + offset,
            length,
        )

        offset = 0
        length = Page.size
        self.section[".text"].get_bound(
            self.virtual_memory_bound[0][1] + offset,
            self.memory_bound[0][1] + offset,
            length,
        )

        for i in range(self.transient_depth):
            offset += length
            length = Page.size
            self.section[f'.text_train_{i+1}'].get_bound(
                self.virtual_memory_bound[0][1] + offset,
                self.memory_bound[0][1] + offset,
                length,
            )

    def _write_headers(self, f):
        f.write(f'#include "parafuzz.h"\n')
        f.write(f'#include "fuzzing.h"\n')
        if self.virtual:
            f.write('#define __VIRTUAL__\n')
