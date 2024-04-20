import os
import random
import sys
from BuildManager import *
from SectionUtils import *
from SectionManager import *
from TransBlockUtils import *

from payload.Instruction import *
from payload.MagicDevice import *
from payload.Block import *

class InitBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('init_block', extension, output_path)

    def gen_instr(self):
        self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/init_block.text.S"))
        self._load_data_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/init_block.data.S"))

class RunTimeBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('run_time_block', extension, output_path)

    def gen_instr(self):
        self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/run_time_block.text.S"))
        self._load_data_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/run_time_block.data.S"))

class MTrapBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('mtrap_block', extension, output_path)

    def gen_instr(self):
        self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/mtrap_block.text.S"))
        self._load_data_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/mtrap_block.data.S"))

class STrapBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('strap_block', extension, output_path)

    def gen_instr(self):
        self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/strap_block.text.S"))
        self._load_data_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/strap_block.data.S"))

class SecretProtectBlock(TransBlock):
    def __init__(self, extension, output_path, victim_privilege, virtual):
        super().__init__('secret_protect_block', extension, output_path)
        self.victim_privilege = victim_privilege
        self.virtual = virtual

    def gen_instr(self):
        self._add_inst_block(BaseBlock(self.entry, self.extension, None, False))
        if (
            self.victim_privilege == "M" or self.victim_privilege == "S"
        ) and self.virtual:
            self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/secret_protect_block.S.text.S"))
        if self.victim_privilege == "M":
            self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/secret_protect_block.M.text.S"))
        self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/secret_protect_block.ret.text.S"))

class TransFrameManager(TransBaseManager):
    def __init__(self, config, extension, victim_privilege, virtual, output_path):
        super().__init__(config, extension, victim_privilege, virtual, output_path)

    def gen_block(self):
        self.init_block = InitBlock(self.extension, self.output_path)
        self.runtime_block = RunTimeBlock(self.extension, self.output_path)
        self.mtrap_block = MTrapBlock(self.extension, self.output_path)
        self.secret_protect_block = SecretProtectBlock(self.extension, self.output_path, self.victim_privilege, self.virtual)
        self.strap_block = STrapBlock(self.extension, self.output_path)

        self.init_block.gen_instr()
        self.runtime_block.gen_instr()
        self.mtrap_block.gen_instr()
        self.secret_protect_block.gen_instr()
        self.strap_block.gen_instr()

    def _generate_sections(self):
        mtrap_section = self.section[".mtrap"] = FuzzSection(
            ".mtrap", Flag.X | Flag.R | Flag.W
        )
        strap_section = self.section[".strap"] = FuzzSection(
            ".strap", Flag.X | Flag.R | Flag.W
        )
        text_frame_section = self.section[".text_frame"] = FuzzSection(
            ".text_frame", Flag.U | Flag.X | Flag.R
        )
        data_frame_section = self.section[".data_frame"] = FuzzSection(
            ".data_frame", Flag.U | Flag.W | Flag.R
        )

        self._set_section(mtrap_section, mtrap_section, [self.mtrap_block, self.secret_protect_block])
        self._set_section(strap_section, strap_section, [self.strap_block])
        self._set_section(text_frame_section, data_frame_section, [self.init_block, self.runtime_block])

        mtrap_section.add_global_label(
            [
                self.mtrap_block.entry,
                self.secret_protect_block.entry,
                "mtrap_stack_bottom",
            ]
        )
        strap_section.add_global_label(
            [self.strap_block.entry, "strap_stack_bottom"]
        )
        text_frame_section.add_global_label([self.init_block.entry])

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
        self.section[".data_frame"].get_bound(
            self.virtual_memory_bound[0][0] + offset,
            self.memory_bound[0][0] + offset,
            length,
        )

        offset += length
        length = Page.size
        self.section[".text_frame"].get_bound(
            self.virtual_memory_bound[0][0] + offset,
            self.memory_bound[0][0] + offset,
            length,
        )
