from TransVictimBlock import *
import copy

class ReplaceBlock(TransBlock):
    def __init__(self, extension, output_path, c_nop_len):
        super().__init__('replace_block', extension, output_path)
        assert c_nop_len >= 0
        self.c_nop_len = c_nop_len

    def gen_default(self):
        inst_list = [
            'addi s0, zero, 0x1e'
        ]
        inst_list.extend(['c.nop']*(self.c_nop_len - 4))

        self._load_inst_str(inst_list)

class TransDecodeManager(TransBaseManager):
    def __init__(self, config, extension, victim_privilege, virtual, output_path, data_section):
        super().__init__(config, extension, victim_privilege, virtual, output_path)
        self.data_section = data_section
    
    def gen_block(self, trans_victim, template_path):
        self.trans_victim = trans_victim
        if template_path is not None:
            template_list = os.listdir(template_path)
            encode_template = None if 'encode_block.text' not in template_list else os.path.join(template_path, 'encode_block')
        else:
            encode_template = None

        self.load_init_block = copy.deepcopy(trans_victim.load_init_block)
        self.load_init_block.update_depth(self.swap_idx)

        nop_begin = self.trans_victim.symbol_table['secret_migrate_block_entry']
        nop_end = self.trans_victim.symbol_table['delay_block_entry']
        self.nop_block = NopBlock(self.extension, self.output_path, nop_end - nop_begin)
        
        self.delay_block = copy.deepcopy(self.trans_victim.delay_block)

        nop_begin = self.trans_victim.symbol_table['trigger_block_entry']
        nop_end = self.trans_victim.symbol_table['encode_block_entry']
        self.replace_block = ReplaceBlock(self.extension, self.output_path, nop_end - nop_begin)

        if encode_template is None:
            self.encode_block = EncodeBlock(self.extension, self.output_path, 'S0', 'default')
            self.encode_block.gen_instr(encode_template)
        else:
            self.encode_block = copy.deepcopy(trans_victim.encode_block)
            if self.encode_block.loop:
                self.encode_block.break_loop()
    
    def record_fuzz(self, file):
        pass
        
    def store_template(self, folder):
        self._dump_trans_block(folder, [self.encode_block], False)

    def _generate_sections(self):

        text_swap_section = self.section[".text_swap"] = FuzzSection(
            ".text_swap", Flag.U | Flag.X | Flag.R
        )

        self.section[".data_decode"] = self.data_section

        empty_section = FuzzSection(
            "", 0
        )

        self._set_section(text_swap_section, self.data_section, [self.load_init_block])
        self._set_section(text_swap_section, empty_section, [self.nop_block, self.delay_block, self.replace_block, self.encode_block])


