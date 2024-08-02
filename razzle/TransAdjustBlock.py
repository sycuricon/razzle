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
from TransVictimBlock import *

from payload.Instruction import *
from payload.MagicDevice import *
from payload.Block import *

class SecretMigrateType(Enum):
    MEMORY = auto()
    CACHE = auto()
    LOAD_BUFFER = auto()
    STORE_BUFFER = auto()

class SecretMigrateBlock(TransBlock):
    def __init__(self, extension, output_path, protect_gpr_list, secret_migrate_type):
        super().__init__('secret_migrate_block', extension, output_path)
        self.protected_gpr_list = protect_gpr_list
        self.secret_migrate_type = secret_migrate_type
    
    def gen_instr(self):
        if len(self.protected_gpr_list) >= 30:
            self.secret_migrate_type = SecretMigrateType.MEMORY

        inst_list = []
        used_reg = list(set(reg_range) - {'ZERO'} - set(self.protected_gpr_list))
        used_reg.sort()
        used_reg = list(map(str.lower, used_reg[0:2]))
        
        if self.secret_migrate_type == SecretMigrateType.STORE_BUFFER:
            inst_list.extend(
                [
                    f'la {used_reg[0]}, give_me_secret',
                    f'ld {used_reg[1]}, 0({used_reg[0]})',
                    f'csrrw {used_reg[0]}, 0x800, {used_reg[1]}',
                    f'la {used_reg[1]}, secret',
                    f'sd {used_reg[0]}, 0({used_reg[1]})',
                    f'mv {used_reg[0]}, zero',
                ]
            )
        else:
            if self.secret_migrate_type != SecretMigrateType.MEMORY:
                inst_list.extend(
                    [
                        f'la {used_reg[0]}, secret',
                        f'ld {used_reg[1]}, 0({used_reg[0]})',
                        f'mv {used_reg[1]}, zero'
                    ]
                )
            
            if self.secret_migrate_type == SecretMigrateType.LOAD_BUFFER:
                inst_list.extend(
                    [
                        f'la {used_reg[0]}, dummy_data_block_data_top',
                        f'lui {used_reg[1]}, 0x1',
                        f'sd zero, 0({used_reg[0]})',
                        f'add {used_reg[0]}, {used_reg[0]}, {used_reg[1]}',
                        f'sd zero, 0({used_reg[0]})',
                        f'add {used_reg[0]}, {used_reg[0]}, {used_reg[1]}',
                        f'sd zero, 0({used_reg[0]})',
                        f'add {used_reg[0]}, {used_reg[0]}, {used_reg[1]}',
                        f'sd zero, 0({used_reg[0]})',
                    ]
                )

        self._load_inst_str(inst_list)

        need_len = self._get_inst_len()
        now_len = TransBlock._get_inst_len(self)
        inst_list = ['c.nop'] * ((need_len - now_len)//2)
        inst_list.insert(0, f'{self.name}_fill_nop:')
        self._load_inst_str(inst_list)
    
    def _get_inst_len(self):
        return (20 + 8) * 2
    
    def record_fuzz(self):
        record = {}
        record['type'] = f'{self.secret_migrate_type}'

        return self.name, record
        
class TransAdjustManager(TransBaseManager):
    def __init__(self, config, extension, output_path, data_section, trans_frame):
        super().__init__(config, extension, output_path)
        self.data_section = data_section
        self.trans_frame = trans_frame
    
    def gen_block(self, config, trans_victim):
        self.mode = ''.join([config['attack_priv'], config['attack_addr']])

        self.secret_migrate_block = SecretMigrateBlock(self.extension, self.output_path, [], config['secret_migrate_type'])
        self.secret_migrate_block.gen_instr()

        self.encode_block = EncodeBlock(self.extension, self.output_path, None, EncodeType.FUZZ_DEFAULT)
        self.encode_block.gen_instr()

        self.warm_up_block = WarmUpBlock(self.extension, self.output_path)
        self.warm_up_block.gen_instr()

        self.load_init_block = LoadInitBlock(self.swap_idx, self.extension, self.output_path, [], self.mode)
        self.load_init_block.gen_instr()

        self.return_block = ReturnBlock(self.extension, self.output_path)
        self.return_block.gen_instr()

        nop_len = trans_victim.symbol_table['encode_block_entry'] - trans_victim.symbol_table['_text_swap_start']
        need_nop_len = nop_len - self.warm_up_block._get_inst_len() - self.load_init_block._get_inst_len() - self.secret_migrate_block._get_inst_len()
        self.nop_block = NopBlock(self.extension, self.output_path, need_nop_len)
        self.nop_block.gen_instr()
        
    def mutate_access(self, config, trans_victim):
        self.gen_block(config, trans_victim)

    def mutate_encode(self, config, trans_victim):
        self.mode = ''.join([config['attack_priv'], config['attack_addr']])

        self.encode_block = copy.deepcopy(trans_victim.encode_block)
        if self.encode_block.loop:
            self.encode_block.break_loop()
        
        self.load_init_block = LoadInitBlock(self.swap_idx, self.extension, self.output_path, [self.encode_block], self.mode)
        self.load_init_block.gen_instr()

        self.secret_migrate_block = SecretMigrateBlock(self.extension, self.output_path, self.load_init_block.GPR_init_list, config['secret_migrate_type'])
        self.secret_migrate_block.gen_instr()

        nop_len = trans_victim.symbol_table['encode_block_entry'] - trans_victim.symbol_table['_text_swap_start']
        need_nop_len = nop_len - self.warm_up_block._get_inst_len() - self.load_init_block._get_inst_len() - self.secret_migrate_block._get_inst_len()
        self.nop_block = NopBlock(self.extension, self.output_path, need_nop_len)
        self.nop_block.gen_instr()

    def record_fuzz(self):
        block_list = [self.secret_migrate_block, self.encode_block]
        record = self._base_record_fuzz(block_list)
        return 'adjust', record

    def _generate_sections(self):
        
        text_swap_section = self.section[".text_swap"] = FuzzSection(
            ".text_swap", Flag.U | Flag.X | Flag.R
        )

        self.section[".data_victim"] = self.data_section

        empty_section = FuzzSection(
            "", 0
        )

        self.data_section.clear()

        self._set_section(text_swap_section, empty_section, [self.warm_up_block])
        self._set_section(text_swap_section, self.data_section, [self.load_init_block])
        self._set_section(text_swap_section, empty_section, [self.secret_migrate_block, self.nop_block, self.encode_block, self.return_block])


            




        

