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

class ExitBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('exit_block', extension, output_path)

    def gen_instr(self):
        self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/exit_block.text.S"))
        self._load_data_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/exit_block.data.S"))

class DecodeBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('decode_block', extension, output_path)

    def _gen_block_begin(self):
        inst_begin = [
            'INFO_LEAK_START'
        ]
        self._load_inst_str(inst_begin)
    
    def _gen_block_end(self):
        inst_end = [
            'decode_exit:',
            'INFO_LEAK_END',
        ]
        self._load_inst_str(inst_end)

    def gen_instr(self):
        self._gen_block_begin()
        self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/decode_block.cache.text.S"), mutate=True)
        self._gen_block_end()

class TransExitManager(TransBaseManager):
    def __init__(self, config, extension, victim_privilege, virtual, output_path):
        super().__init__(config, extension, victim_privilege, virtual, output_path)
    
    def gen_block(self):
        self.decode_block = DecodeBlock(self.extension, self.output_path)
        self.exit_block = ExitBlock(self.extension, self.output_path)

        self.decode_block.gen_instr()
        self.exit_block.gen_instr()

    def _generate_sections(self):

        text_swap_section = self.section[".text_swap"] = FuzzSection(
            ".text_swap", Flag.U | Flag.X | Flag.R
        )
        data_swap_section = self.section[".data_swap"] = FuzzSection(
            ".data_swap", Flag.U | Flag.W | Flag.R
        )

        self._set_section(text_swap_section, data_swap_section, [self.decode_block, self.exit_block])

    def _distribute_address(self):
        offset = 0
        length = Page.size
        self.section[".text_swap"].get_bound(
            self.virtual_memory_bound[0][0] + offset, self.memory_bound[0][0] + offset, length
        )

        offset += length
        length = Page.size
        self.section[".data_swap"].get_bound(
            self.virtual_memory_bound[0][0] + offset,
            self.memory_bound[0][0] + offset,
            length,
        )
        

