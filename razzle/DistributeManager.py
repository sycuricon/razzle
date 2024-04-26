from BuildManager import *
from ChannelManger import *
from InitManager import *
from LoaderManager import *
from PageTableManager import *
from PocManager import *
from PayloadManager import *
from SecretManager import *
from StackManager import *
from TransManager import *
from SectionUtils import *
import libconf

class MemCfg:
    def __init__(self, mem_start, mem_len):
        self.mem_cfg = {}
        self.mem_cfg['start_addr'] = mem_start
        self.mem_cfg['max_mem_size'] = mem_len
        self.mem_cfg['memory_regions'] = []
        self.mem_cfg['swap_list'] = []
    
    def register_swap_id(self):
        return len(self.mem_cfg['memory_regions'])
    
    def add_mem_region(self, mem_type, start_addr, max_len, init_file, swap_id):
        assert mem_type in ['dut', 'vnt', 'swap']
        mem_region = {'type':mem_type, 'start_addr':start_addr,\
                    'max_len':max_len, 'init_file':init_file, 'swap_id':swap_id}
        self.mem_cfg['memory_regions'].append(mem_region)
    
    def add_swap_list(self, swap_list):
        self.mem_cfg['swap_list'] = swap_list
    
    def dump_conf(self, output_path):
        with open(os.path.join(output_path, 'swap_mem.cfg'), "wt") as file:
            tmp_mem_cfg = {}
            for key,value in self.mem_cfg.items():
                tmp_mem_cfg[key] = value
            tmp_mem_cfg['memory_regions'] = tuple(tmp_mem_cfg['memory_regions'])
            file.write(libconf.dumps(tmp_mem_cfg))
    
    def load_conf(self, output_path):
        with open(os.path.join(output_path, 'swap_mem.cfg'), "rt") as file:
            self.mem_cfg = libconf.load(file)

class DistributeManager:
    def __init__(self, hjson_filename, output_path, virtual, do_fuzz, do_debug):
        hjson_file = open(hjson_filename)
        self.config = hjson.load(hjson_file)
        hjson_file.close()
        self.do_debug = do_debug

        self.baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, output_path
        )
        
        self.attack_privilege = self.config["attack"]
        self.victim_privilege = self.config["victim"]
        privilege_stage = {"M": 3, "S": 1, "U": 0}
        assert (
            privilege_stage[self.attack_privilege]
            <= privilege_stage[self.victim_privilege]
        ), "the privilege of vicitm smaller than attack's is meanless"

        self.output_path = output_path
        self.virtual = virtual if self.attack_privilege != "M" else False

        self.code = {}
        self.code["secret"] = SecretManager(self.config["secret"])
        self.code["channel"] = ChannelManager(self.config["channel"])
        self.code["stack"] = StackManager(self.config["stack"])
        if do_fuzz:
            self.trans = self.code["payload"] = TransManager(
                self.config["trans"], self.victim_privilege, self.virtual, output_path, self.do_debug
            )
        else:
            self.code["payload"] = PayloadManager(self.config["payload"])
            self.code["poc"] = PocManager(self.config["poc"])
        self.code["init"] = InitManager(
            self.config["init"], do_fuzz, self.virtual, self.attack_privilege, output_path
        )

        self.page_table = PageTableManager(
            self.config["page_table"], self.attack_privilege == "U"
        )
        self.loader = LoaderManager(self.virtual)

        self.file_list = []

        self.mem_cfg = MemCfg(0x80000000, 0x40000)

    def _collect_compile_file(self, file_list):
        self.file_list.extend(file_list)
    
    def _generate_frame(self):
        page_table_name = "page_table.S"
        ld_name = "link.ld"

        self.section_list = []
        for key, value in self.code.items():
            self._collect_compile_file(
                value.file_generate(self.output_path, f"{key}.S")
            )
            self.section_list.extend(value.get_section_list())

        if self.virtual:
            self.page_table.register_sections(self.section_list)
            self._collect_compile_file(
                self.page_table.file_generate(self.output_path, page_table_name)
            )
            self.section_list.extend(self.page_table.get_section_list())

        self.loader.append_section_list(self.section_list)
        self.loader.file_generate(self.output_path, ld_name)
    
    def _generate_compile_shell(self):
        RAZZLE_ROOT = os.environ["RAZZLE_ROOT"]
        gen_elf = ShellCommand(
            "riscv64-unknown-elf-gcc",
            [
                "-march=rv64gc_zicsr_zifencei",
                "-mabi=lp64f",
                "-mcmodel=medany",
                "-nostdlib",
                "-nostartfiles",
                f"-I$OUTPUT_PATH",
                f"-I$RAZZLE_ROOT/template",
                f"-I$RAZZLE_ROOT/template/trans",
                f"-I$RAZZLE_ROOT/template/loader",
                f"-T$OUTPUT_PATH/link.ld",
            ],
        )
        self.baker.add_cmd(
            gen_elf.save_cmd([*self.file_list, "-o", f"$OUTPUT_PATH/Testbench"])
        )

        gen_bin = ShellCommand("riscv64-unknown-elf-objcopy", ["-O", "binary"])
        self.baker.add_cmd(
            gen_bin.save_cmd(
                [f"$OUTPUT_PATH/Testbench", f"$OUTPUT_PATH/Testbench.bin"]
            )
        )

        dump_symbol = ShellCommand("nm")
        self.baker.add_cmd(
            dump_symbol.save_cmd(
                [
                    f"$OUTPUT_PATH/Testbench",
                    f"> $OUTPUT_PATH/Testbench.symbol",
                ]
            )
        )
    
    def _generate_frame_block(self):
        symbol_table = get_symbol_file(os.path.join(self.output_path, 'Testbench.symbol'))

        file_origin = os.path.join(self.output_path, 'Testbench.bin')
        with open(file_origin, "rb") as file:
            origin_byte_array = bytearray(file.read())
        
        if self.virtual:
            address_base = 0
        else:
            address_base = 0x80000000
        
        address_offset = 0x80000000
        
        file_origin_common  = os.path.join(self.output_path, 'origin_common.bin')
        file_variant_common = os.path.join(self.output_path, 'variant_common.bin')

        common_begin = 0
        common_end   = symbol_table['_data_frame_end'] - address_base
        common_byte_array = origin_byte_array[common_begin:common_end]
        with open(file_origin_common, "wb") as file:
            file.write(common_byte_array)

        secret_begin = symbol_table['secret_begin'] - address_base
        secret_end   = symbol_table['secret_end'] - address_base
        common_byte_array[secret_begin:secret_end] = bytes([0 for i in range(0, secret_end - secret_begin)])
        with open(file_variant_common, "wb") as file:
            file.write(common_byte_array)

        self.mem_cfg.add_mem_region('dut', common_begin + address_offset, up_align(common_end, Page.size), file_origin_common, 0)
        self.mem_cfg.add_mem_region('vnt', common_begin + address_offset, up_align(common_end, Page.size), file_variant_common, 0)

        baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.output_path, file_name="disasm_frame.sh"
        )
        gen_asm = ShellCommand("riscv64-unknown-elf-objdump", ["-d"])
        baker.add_cmd(
            gen_asm.save_cmd(
                [
                    f"$OUTPUT_PATH/Testbench",
                    "-j .init",
                    "-j .mtrap",
                    "-j .strap",
                    "-j .text_frame",
                    "-j .data_frame",
                    f"> $OUTPUT_PATH/Testbench_frame.asm",
                ]
            )
        )
        baker.run()

    def _generate_body_block(self):
        body_idx = self.mem_cfg.register_swap_id()
        symbol_table = get_symbol_file(os.path.join(self.output_path, 'Testbench.symbol'))

        file_origin = os.path.join(self.output_path, 'Testbench.bin')
        with open(file_origin, "rb") as file:
            origin_byte_array = bytearray(file.read())
        
        if self.virtual:
            address_base = 0
        else:
            address_base = 0x80000000
        
        address_offset = 0x80000000
        
        file_text_swap = os.path.join(self.output_path, f'text_swap_{body_idx}.bin')
        text_begin = symbol_table['_text_swap_start'] - address_base
        text_end   = symbol_table['_text_swap_end'] - address_base
        text_swap_byte_array = origin_byte_array[text_begin:text_end]
        with open(file_text_swap, "wb") as file:
            file.write(text_swap_byte_array)
        
        self.mem_cfg.add_mem_region('swap', text_begin + address_offset, up_align(text_end, Page.size) - text_begin, file_text_swap, body_idx)
        
        baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.output_path, file_name=f"disasm_body_{body_idx}.sh"
        )
        gen_asm = ShellCommand("riscv64-unknown-elf-objdump", ["-d"])
        baker.add_cmd(
            gen_asm.save_cmd(
                [
                    f"$OUTPUT_PATH/Testbench",
                    "-j .text_swap",
                    f"> $OUTPUT_PATH/Testbench_body_{body_idx}.asm",
                ]
            )
        )
        baker.run()

    def generate_test(self):
        self._generate_frame()
        self._generate_compile_shell()
        self.run()

        swap_index = 0
        self._generate_body_block()
        swap_index += 1

        while not self.trans.mem_mutate_halt():
            if self.trans.mem_mutate_iter():
                self.trans.file_generate(self.output_path, 'payload.S')
                self.run()
                self.trans.update_symbol_table()
                self._generate_body_block()
                swap_index += 1
        
        self._generate_frame_block()
        
        self.mem_cfg.add_swap_list(self.trans._generate_swap_list())
        self.mem_cfg.dump_conf(self.output_path)

    def run(self, cmd=None):
        self.baker.run(cmd)
    
