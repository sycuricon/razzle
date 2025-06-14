from TransVictimBlock import *
import copy

class ReplaceBlock(TransBlock):
    def __init__(self, extension, output_path, begin_addr, access_addr, end_addr, return_addr):
        super().__init__('replace_block', extension, output_path)
        self.begin_addr = begin_addr
        self.end_addr = end_addr
        self.return_addr = return_addr
        self.access_addr = access_addr

    def gen_instr(self):
        if self.return_addr == None:
            inst_list = ['c.nop'] * ((self.access_addr - self.begin_addr) // 2)
            self._load_inst_str(inst_list)

            inst_list = [
                'access_secret_block_entry:',
                'addi s0, zero, GUESS_TARGET',
            ]
            inst_list.extend(['c.nop'] * ((self.end_addr - self.access_addr - 4)//2))

            self._load_inst_str(inst_list)

        else:
            inst_list = ['c.nop'] * ((self.return_addr - self.begin_addr) // 2)
            self._load_inst_str(inst_list)

            inst_list = ['return_block_entry:']
            inst_list.extend(['c.nop'] * ((self.access_addr - self.return_addr) // 2))
            self._load_inst_str(inst_list)

            inst_list = [
                'access_secret_block_entry:',
                'addi s0, zero, GUESS_TARGET',
            ]
            inst_list.extend(['c.nop'] * ((self.end_addr - self.access_addr - 4)//2))

            self._load_inst_str(inst_list)

class TransDecodeManager(TransBaseManager):
    def __init__(self, config, extension, output_path, data_section, trans_frame):
        super().__init__(config, extension, output_path)
        self.data_section = data_section
        self.trans_frame = trans_frame

    def gen_block(self, config, trans_victim):
        self.mode = ''.join([config['train_priv'], config['train_addr']])

        self.load_init_block = copy.deepcopy(trans_victim.load_init_block)
        self.load_init_block.update_depth(self.swap_idx)

        nop_begin = self.trans_victim.symbol_table['secret_migrate_block_entry']
        nop_end = self.trans_victim.symbol_table['delay_block_entry']
        self.nop_block = NopBlock(self.extension, self.output_path, nop_end - nop_begin)
        self.nop_block.gen_instr()
        
        self.delay_block = copy.deepcopy(self.trans_victim.delay_block)
        self.delay_block.move_sync()

        nop_begin = self.trans_victim.symbol_table['trigger_block_entry']
        nop_end = self.trans_victim.symbol_table['encode_block_entry']
        nop_access = self.trans_victim.symbol_table['access_secret_block_entry']
        nop_return = self.trans_victim.symbol_table['return_block_entry'] if self.trans_victim.return_front else None
        self.replace_block = ReplaceBlock(self.extension, self.output_path, nop_begin, nop_access, nop_end, nop_return)
        self.replace_block.gen_instr()

        self.encode_block = copy.deepcopy(trans_victim.encode_block)
        if self.encode_block.loop:
            self.encode_block.break_loop()
        
        self.return_block = ReturnBlock(self.extension, self.output_path)
        self.return_block.gen_instr()
    
    def record_fuzz(self):
        pass
        
    def store_template(self, folder):
        self._dump_trans_block(folder, [self.encode_block], False)

    def _generate_sections(self):

        text_swap_section = self.section[".text_swap"] = FuzzSection(
            ".text_swap", Flag.U | Flag.X | Flag.R
        )

        self.data_section.clear()
        self.section[".data_decode"] = self.data_section

        empty_section = FuzzSection(
            "", 0
        )

        self._set_section(text_swap_section, self.data_section, [self.load_init_block])
        self._set_section(text_swap_section, empty_section, [self.nop_block, self.delay_block, self.replace_block, self.encode_block])
        self._set_section(empty_section, self.data_section, [self.trans_victim.access_secret_block])
        if not self.trans_victim.return_front:
            self._set_section(text_swap_section, empty_section, [self.return_block])


