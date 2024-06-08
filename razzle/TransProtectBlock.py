import os
import random
import sys
import copy
from enum import *
from BuildManager import *
from SectionUtils import *
from SectionManager import *
from TransBlockUtils import *
from TransBodyBlock import *

from payload.Instruction import *
from payload.MagicDevice import *
from payload.Block import *

class SecretProtectBlock(TransBlock):
    def __init__(self, extension, output_path, victim_privilege, virtual):
        super().__init__('secret_protect_block', extension, output_path)
        self.victim_privilege = victim_privilege
        self.virtual = virtual

    def gen_default(self):
        self._add_inst_block(BaseBlock(self.entry, self.extension, False))
        if (
            self.victim_privilege == "M" or self.victim_privilege == "S"
        ) and self.virtual:
            self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/secret_protect_block.S.text.S"))
        if self.victim_privilege == "M":
            self._load_inst_file(os.path.join(os.environ["RAZZLE_ROOT"], "template/trans/secret_protect_block.M.text.S"))
        
class TransProtectManager(TransBaseManager):
    def __init__(self, config, extension, output_path, data_section, trans_frame):
        super().__init__(config, extension, output_path)
        self.data_section = data_section
        self.trans_frame = trans_frame
    
    def gen_block(self, config, template):
        self.mode = 'Mp'
        self.secret_protect_block = SecretProtectBlock(self.extension, self.output_path, config['victim_priv'], config['victim_addr'])
        self.secret_protect_block.gen_instr(None)
        
        self.return_block = ReturnBlock(self.extension, self.output_path)
        self.return_block.gen_instr(None)
        
    def record_fuzz(self, file):
        file.write(f'protect: {self.swap_idx}\n')

    def _generate_sections(self):
        
        text_swap_section = self.section[".text_swap"] = FuzzSection(
            ".text_swap", Flag.U | Flag.X | Flag.R
        )

        self.section[".data_protect"] = self.data_section

        empty_section = FuzzSection(
            "", 0
        )

        self.data_section.clear()

        self._set_section(text_swap_section, empty_section, [self.secret_protect_block, self.return_block])


            




        

