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

class StackBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('stack_block', extension, output_path)

    def gen_default(self):
        self._load_data_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/stack_block.data.S"))

class ChannelBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('channel_block', extension, output_path)

    def gen_default(self):
        self._load_data_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/channel_block.data.S"))

class SecretBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('secret_block', extension, output_path)

    def gen_default(self):
        self._load_data_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/secret_block.data.S"))

class InitBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('init_block', extension, output_path)

    def gen_default(self):
        self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/init_block.text.S"))

class MTrapBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('mtrap_block', extension, output_path)

    def gen_default(self):
        self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/mtrap_block.text.S"))
        self._load_data_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/mtrap_block.data.S"))

class STrapBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('strap_block', extension, output_path)

    def gen_default(self):
        self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/strap_block.text.S"))

class DummyDataBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('dummy_data_block', extension, output_path)

    def gen_default(self):
        self._load_data_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/dummy_data_block.data.S"))

class AccessFaultDataBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('access_fault_data_block', extension, output_path)

    def gen_default(self):
        self._load_data_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/access_fault_data_block.data.S"))

class PageFaultDataBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('page_fault_data_block', extension, output_path)

    def gen_default(self):
        self._load_data_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/page_fault_data_block.data.S"))

class RandomDataBlock(TransBlock):
    def __init__(self, extension, output_path):
        super().__init__('random_data_block', extension, output_path)

    def gen_default(self):
        def random_data_line(byte_num = 0x800):
            assert byte_num%64==0, "byte_num must be aligned to 64"
            for i in range(0, byte_num, 64):
                data = [hex(random.randint(0,0xffffffffffffffff)) for i in range(8)]
                dataline = " ,".join(data)
                self.data_list.append(RawInstruction(f'.dword {dataline}'))

        self.data_list.append(RawInstruction(f'.global {self.name}_page_base'))
        random_data_line(0x800)
        self.data_list.append(RawInstruction(f'{self.name}_page_base:'))
        random_data_line(0x1800)

class TransFrameManager(TransBaseManager):
    def __init__(self, config, extension, output_path):
        super().__init__(config, extension, output_path)
        self.dist = False

        self.section[".data_frame"] = TransDataSection(
            ".data_frame", Flag.U | Flag.W | Flag.R
        )
        self.section[".data_train"] = TransDataSection(
            ".data_train", Flag.U | Flag.W | Flag.R
        )
        self.section[".data_adjust"] = TransDataSection(
            ".data_adjust", Flag.U | Flag.W | Flag.R
        )
        self.section[".data_protect"] = TransDataSection(
            ".data_protect", Flag.U | Flag.W | Flag.R
        )
        self.section[".data_victim"] = TransDataSection(
            ".data_victim", Flag.U | Flag.W | Flag.R
        )
        self.section[".data_decode"] = TransDataSection(
            ".data_decode", Flag.U | Flag.W | Flag.R
        )

    def gen_block(self):
        self.secret_block = SecretBlock(self.extension, self.output_path)
        self.channel_block = ChannelBlock(self.extension, self.output_path)
        self.init_block = InitBlock(self.extension, self.output_path)
        self.mtrap_block = MTrapBlock(self.extension, self.output_path)
        self.strap_block = STrapBlock(self.extension, self.output_path)
        self.random_data_block = RandomDataBlock(self.extension, self.output_path)
        self.access_fault_block = AccessFaultDataBlock(self.extension, self.output_path)
        self.page_fault_block = PageFaultDataBlock(self.extension, self.output_path)
        self.stack_block = StackBlock(self.extension, self.output_path)
        self.dummy_data_block = DummyDataBlock(self.extension, self.output_path)

        self.secret_block.gen_instr(None)
        self.channel_block.gen_instr(None)
        self.init_block.gen_instr(None)
        self.mtrap_block.gen_instr(None)
        self.strap_block.gen_instr(None)
        self.random_data_block.gen_instr(None)
        self.access_fault_block.gen_instr(None)
        self.page_fault_block.gen_instr(None)
        self.stack_block.gen_instr(None)
        self.dummy_data_block.gen_instr(None)
    
    def get_data_section(self):
        data_frame_section = self.section['.data_frame']
        data_train_section = self.section['.data_train']
        data_adjust_section = self.section['.data_adjust']
        data_protect_section = self.section['.data_protect']
        data_victim_section = self.section['.data_victim']
        data_decode_section = self.section['.data_decode']
        return  data_frame_section, data_train_section, data_adjust_section, data_protect_section, data_victim_section, data_decode_section

    def move_data_section(self):
        self.section.pop('.data_train')
        self.section.pop('.data_adjust')
        self.section.pop('.data_protect')
        self.section.pop('.data_victim')
        self.section.pop('.data_decode')

    def _generate_sections(self):
        secret_section = self.section[".secret"] = FuzzSection(
            ".secret", Flag.U | Flag.W | Flag.R
        )
        channel_section = self.section[".channel"] = FuzzSection(
            ".channel", Flag.U | Flag.W | Flag.R
        )
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

        dummy_data_section = self.section[".dummy_data"] = FuzzSection(
            ".dummy_data", Flag.U | Flag.W | Flag.R
        )
        access_fault_data_section = self.section[".access_fault_data"] = FuzzSection(
            ".access_fault_data", Flag.U | Flag.W | Flag.R
        )
        page_fault_data_section = self.section[".page_fault_data"] = FuzzSection(
            ".page_fault_data", 0
        )
        stack_section = self.section[".stack"] = FuzzSection(
            ".stack", Flag.U | Flag.W | Flag.R
        )
        empty_section = FuzzSection(
            "", 0
        )

        self._set_section(empty_section, secret_section, [self.secret_block])
        self._set_section(empty_section, channel_section, [self.channel_block])
        self._set_section(mtrap_section, mtrap_section, [self.mtrap_block])
        self._set_section(strap_section, strap_section, [self.strap_block])
        self._set_section(empty_section, random_data_section, [self.random_data_block])
        self._set_section(text_frame_section, empty_section, [self.init_block])
        self._set_section(empty_section, dummy_data_section, [self.dummy_data_block])
        self._set_section(empty_section, access_fault_data_section, [self.access_fault_block])
        self._set_section(empty_section, page_fault_data_section, [self.page_fault_block])
        self._set_section(empty_section, stack_section, [self.stack_block])

        mtrap_section.add_global_label(
            [
                self.mtrap_block.entry,
                "mtrap_stack_bottom",
            ]
        )
        strap_section.add_global_label(
            [
                self.strap_block.entry,
                "strap_stack_bottom",
            ]
        )
        text_frame_section.add_global_label([self.init_block.entry])
        

    def _distribute_address(self):
        if self.dist == True:
            return
        else:
            self.dist = True

        offset = 0
        length = Page.size
        self.section[".secret"].get_bound(
            self.virtual_memory_bound[0][0] + offset,
            self.memory_bound[0][0] + offset,
            length,
        )

        offset += length
        length = Page.size * 4
        self.section[".channel"].get_bound(
            self.virtual_memory_bound[0][0] + offset,
            self.memory_bound[0][0] + offset,
            length,
        )

        offset += length
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
        length = Page.size * 2
        self.section[".random_data"].get_bound(
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
        self.section[".data_victim"].get_bound(
            self.virtual_memory_bound[0][0] + offset,
            self.memory_bound[0][0] + offset,
            length,
        )

        offset += length
        length = Page.size
        self.section[".data_decode"].get_bound(
            self.virtual_memory_bound[0][0] + offset,
            self.memory_bound[0][0] + offset,
            length,
        )

        offset += length
        length = Page.size
        self.section[".data_adjust"].get_bound(
            self.virtual_memory_bound[0][0] + offset,
            self.memory_bound[0][0] + offset,
            length,
        )

        offset += length
        length = Page.size
        self.section[".data_protect"].get_bound(
            self.virtual_memory_bound[0][0] + offset,
            self.memory_bound[0][0] + offset,
            length,
        )

        offset += length
        length = Page.size
        self.section[".data_train"].get_bound(
            self.virtual_memory_bound[0][0] + offset,
            self.memory_bound[0][0] + offset,
            length,
        )

        #-------------------------------------------

        offset = 0
        length = Page.size * 2
        offset += length
        self.section[".stack"].get_bound(
            self.virtual_memory_bound[1][1] - offset,
            self.memory_bound[1][1] - offset,
            length,
        )

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

    def gen_default(self):
        self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/exit_block.text.S"))
        self._load_data_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/exit_block.data.S"))

class TransExitManager(TransBaseManager):
    def __init__(self, config, extension, output_path, data_section, trans_frame):
        super().__init__(config, extension, output_path)
        self.data_section = data_section
        self.trans_frame = trans_frame
    
    def gen_block(self):
        self.mode = 'Mp'
        self.exit_block = ExitBlock(self.extension, self.output_path)
        self.exit_block.gen_instr(None)
    
    def record_fuzz(self,file):
        pass

    def _generate_sections(self):

        text_swap_section = self.section[".text_swap"] = FuzzSection(
            ".text_swap", Flag.U | Flag.X | Flag.R
        )

        self._set_section(text_swap_section, self.data_section, [self.exit_block])
        # self._set_section(text_swap_section, self.trans_frame.section['.data_frame'], [self.decode_block, self.exit_block])

