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
        self._add_inst_block(BaseBlock(self.entry, self.extension, False))
        if (
            self.victim_privilege == "M" or self.victim_privilege == "S"
        ) and self.virtual:
            self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/secret_protect_block.S.text.S"))
        if self.victim_privilege == "M":
            self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/secret_protect_block.M.text.S"))
        self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/secret_protect_block.ret.text.S"))

class DummyDataBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('dummy_data_block', extension, output_path)

    def gen_instr(self):
        self.data_list.append(RawInstruction('.space 0x4000'))

class AccessFaultDataBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('access_fault_data_block', extension, output_path)

    def gen_instr(self):
        self.data_list.append(RawInstruction('.space 0x800'))
        self.data_list.append(RawInstruction(f'{self.name}_page_base:'))
        self.data_list.append(RawInstruction('.space 0x800'))

class PageFaultDataBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('page_fault_data_block', extension, output_path)

    def gen_instr(self):
        self.data_list.append(RawInstruction('.space 0x800'))
        self.data_list.append(RawInstruction(f'{self.name}_page_base:'))
        self.data_list.append(RawInstruction('.space 0x800'))

class RandomDataBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('random_data_block', extension, output_path)

    def gen_instr(self):
        def random_data_line(byte_num = 0x800):
            assert byte_num%64==0, "byte_num must be aligned to 64"
            for i in range(0, byte_num, 64):
                data = [hex(random.randint(0,0xffffffffffffffff)) for i in range(8)]
                dataline = " ,".join(data)
                self.data_list.append(RawInstruction(f'.dword {dataline}'))

        random_data_line(0x800)
        self.data_list.append(RawInstruction(f'{self.name}_page_base:'))
        random_data_line(0x800)

class TransFrameManager(TransBaseManager):
    def __init__(self, config, extension, victim_privilege, virtual, output_path):
        super().__init__(config, extension, victim_privilege, virtual, output_path)

    def gen_block(self):
        self.init_block = InitBlock(self.extension, self.output_path)
        self.runtime_block = RunTimeBlock(self.extension, self.output_path)
        self.mtrap_block = MTrapBlock(self.extension, self.output_path)
        self.secret_protect_block = SecretProtectBlock(self.extension, self.output_path, self.victim_privilege, self.virtual)
        self.strap_block = STrapBlock(self.extension, self.output_path)
        self.random_data_block = RandomDataBlock(self.extension, self.output_path)
        self.access_fault_block = AccessFaultDataBlock(self.extension, self.output_path)
        self.page_fault_block = PageFaultDataBlock(self.extension, self.output_path)
        self.dummy_data_block = DummyDataBlock(self.extension, self.output_path)

        self.init_block.gen_instr()
        self.runtime_block.gen_instr()
        self.mtrap_block.gen_instr()
        self.secret_protect_block.gen_instr()
        self.strap_block.gen_instr()
        self.random_data_block.gen_instr()
        self.access_fault_block.gen_instr()
        self.page_fault_block.gen_instr()
        self.dummy_data_block.gen_instr()

    def _generate_sections(self):
        if len(self.section) != 0:
            return

        mtrap_section = self.section[".mtrap"] = FuzzSection(
            ".mtrap", Flag.X | Flag.R | Flag.W
        )
        strap_section = self.section[".strap"] = FuzzSection(
            ".strap", Flag.X | Flag.R | Flag.W
        )
        text_frame_section = self.section[".text_frame"] = FuzzSection(
            ".text_frame", Flag.U | Flag.X | Flag.R
        )
        random_data_section = self.section[".random_data"] = FuzzSection(
            ".random_data", Flag.U | Flag.W | Flag.R
        )
        self.data_frame_section = data_frame_section = self.section[".data_frame"] = FuzzSection(
            ".data_frame", Flag.U | Flag.W | Flag.R
        )
        dummy_data_section = self.section[".dummy_data"] = FuzzSection(
            ".dummy_data", Flag.U | Flag.W | Flag.R
        )
        access_fault_data_section = self.section[".access_fault_data"] = FuzzSection(
            ".access_fault_data", Flag.U | Flag.W | Flag.R
        )
        page_fault_data_section = self.section[".page_fault_data"] = FuzzSection(
            ".page_fault_data", 0
        )
        empty_section = FuzzSection(
            "", 0
        )

        self._set_section(mtrap_section, mtrap_section, [self.mtrap_block, self.secret_protect_block])
        self._set_section(strap_section, strap_section, [self.strap_block])
        self._set_section(empty_section, random_data_section, [self.random_data_block])
        self._set_section(text_frame_section, data_frame_section, [self.init_block, self.runtime_block])
        self._set_section(empty_section, dummy_data_section, [self.dummy_data_block])
        self._set_section(empty_section, access_fault_data_section, [self.access_fault_block])
        self._set_section(empty_section, page_fault_data_section, [self.page_fault_block])

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
            self.memory_bound[0][0] + offset, self.memory_bound[0][0] + offset, length, must_m=True
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
        self.section[".text_frame"].get_bound(
            self.virtual_memory_bound[0][0] + offset,
            self.memory_bound[0][0] + offset,
            length,
        )

        offset += length
        length = Page.size
        self.section[".random_data"].get_bound(
            self.virtual_memory_bound[0][0] + offset,
            self.memory_bound[0][0] + offset,
            length,
        )

        offset += length
        length = up_align(len(self.data_frame_section.inst_list), Page.size)
        self.section[".data_frame"].get_bound(
            self.virtual_memory_bound[0][0] + offset,
            self.memory_bound[0][0] + offset,
            length,
        )

        #-------------------------------------------

        offset = 0
        length = Page.size
        offset += length
        self.section[".page_fault_data"].get_bound(
            self.virtual_memory_bound[1][1] - offset,
            self.memory_bound[1][1] - offset,
            length,
        )

        length = Page.size
        offset += length
        self.section[".access_fault_data"].get_bound(
            self.virtual_memory_bound[1][1] - offset,
            self.memory_bound[1][1] - offset,
            length,
        )

        length = 4 * Page.size
        offset += length
        self.section[".dummy_data"].get_bound(
            self.virtual_memory_bound[1][1] - offset,
            self.memory_bound[1][1] - offset,
            length,
        )



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
    def __init__(self, config, extension, victim_privilege, virtual, output_path, trans_frame):
        super().__init__(config, extension, victim_privilege, virtual, output_path)
        self.trans_frame = trans_frame
    
    def gen_block(self):
        self.decode_block = DecodeBlock(self.extension, self.output_path)
        self.exit_block = ExitBlock(self.extension, self.output_path)

        self.decode_block.gen_instr()
        self.exit_block.gen_instr()

    def _generate_sections(self):

        text_swap_section = self.section[".text_swap"] = FuzzSection(
            ".text_swap", Flag.U | Flag.X | Flag.R
        )

        self._set_section(text_swap_section, self.trans_frame.data_frame_section, [self.decode_block, self.exit_block])

    def _distribute_address(self):
        offset = 0
        length = Page.size
        self.section[".text_swap"].get_bound(
            self.virtual_memory_bound[0][0] + offset, self.memory_bound[0][0] + offset, length
        )
