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
    def __init__(self, extension, output_path, pmp_r, pmp_l, pte_r, pte_v, victim_priv, victim_addr, attack_priv, attack_addr):
        super().__init__('secret_protect_block', extension, output_path)
        self.pmp_r = pmp_r
        self.pmp_l = pmp_l
        self.pte_r = pte_r
        self.pte_v = pte_v
        self.victim_priv = victim_priv
        self.victim_addr = victim_addr
        self.attack_priv = attack_priv
        self.attack_addr = attack_addr

    def gen_instr(self):
        block = BaseBlock(self.entry, self.extension, False)
        self._add_inst_block(block)
        if self.pmp_r == False or self.pmp_l == True:
            pmpcfg0_value = (int(self.pmp_l) << 7) | (0b11 << 3) | (int(self.pmp_r) << 0) 
            inst_list = [
                'protect_M_mode:  ',
                'li t0, 0x200011ff',
                'csrw pmpaddr0, t0',
                'csrr t0, pmpcfg0',
                f'ori t0, t0, {hex(pmpcfg0_value)}',
                'csrw pmpcfg0, t0',
            ]
            self._load_inst_str(inst_list)
        if self.pte_r == False or self.pte_v == False:
            vaddr_label = 'vaddr_0xfffffffffff04000_paddr_0x80004000'\
                if self.victim_priv == 'S' and self.victim_addr == 'v' or self.attack_priv == 'S' and self.victim_addr == 'p' else\
                'vaddr_0x4000_paddr_0x80004000'
            mask = (int(self.pte_r == False) << 1) | (int(self.pte_v == False) << 0)
            inst_list = [
                'protect_S_mode:',   
                f'la t0, {vaddr_label}',
                'ld t1, 0(t0)',
                f'andi t1, t1, ~({hex(mask)})',
                'sd t1, 0(t0)',
                'sfence.vma',
            ]
            self._load_inst_str(inst_list)
        
class TransProtectManager(TransBaseManager):
    def __init__(self, config, extension, output_path, data_section, trans_frame):
        super().__init__(config, extension, output_path)
        self.data_section = data_section
        self.trans_frame = trans_frame
    
    def gen_block(self, config):
        self.mode = 'Mp'
        self.secret_protect_block = SecretProtectBlock(self.extension, self.output_path, \
            config['pmp_l'], config['pmp_r'], config['pte_r'], config['pte_v'], config['victim_priv'],  \
            config['victim_addr'], config['attack_priv'], config['attack_addr'])
        self.secret_protect_block.gen_instr()
        
        self.return_block = ReturnBlock(self.extension, self.output_path)
        self.return_block.gen_instr()
        
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


            




        

