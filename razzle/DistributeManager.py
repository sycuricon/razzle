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
import csv
import numpy as np
import struct

class MemCfg:
    def __init__(self, mem_start, mem_len):
        self.mem_start = mem_start
        self.mem_len = mem_len
        self.mem_regions = {}
        self.mem_region_kind = ['frame', 'data_train',\
            'data_tte', 'data_train_tte', 'data_victim', 'swap']
        for kind in self.mem_region_kind:
            self.mem_regions[kind] = []
        self.swap_list = []
    
    def add_mem_region(self, kind, mem_region):
        assert kind in self.mem_region_kind and kind != 'swap'
        self.mem_regions[kind] = mem_region
    
    def add_swap_list(self, swap_block_list):
        self.swap_list = []
        self.mem_regions['swap'] = []
        for swap_block in swap_block_list:
            self.mem_regions['swap'].append(swap_block)
            self.swap_list.append(swap_block['swap_id'])
    
    def dump_conf(self, output_path):
        with open(os.path.join(output_path, 'swap_mem.cfg'), "wt") as file:
            tmp_mem_cfg = {}
            tmp_mem_cfg['start_addr'] = self.mem_start
            tmp_mem_cfg['max_mem_size'] = self.mem_len
            mem_region = []
            for regions in self.mem_regions.values():
                mem_region.extend(regions)
            tmp_mem_cfg['memory_regions'] = tuple(mem_region)
            tmp_mem_cfg['swap_list'] = self.swap_list
            file.write(libconf.dumps(tmp_mem_cfg))
    
    def load_conf(self, output_path):
        with open(os.path.join(output_path, 'swap_mem.cfg'), "rt") as file:
            self.mem_cfg = libconf.load(file)

class DistributeManager:
    def __init__(self, hjson_filename, output_path, virtual, do_fuzz, do_debug,\
        rtl_sim, rtl_sim_mode, taint_log, repo_path):
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

        if repo_path is None:
            self.repo_path = self.output_path
        else:
            self.repo_path = repo_path

        if do_fuzz:
            self.trans = self.code["payload"] = TransManager(
                self.config["trans"], self.victim_privilege, self.virtual, self.output_path, self.do_debug, self.repo_path
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

        self.rtl_sim = rtl_sim
        assert rtl_sim_mode in ['vcs', 'vlt'], "the rtl_sim_mode must be in vcs and vlt"
        self.rtl_sim_mode = rtl_sim_mode
        self.taint_log = taint_log

        self.coverage = {}

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

        self.frame_file_list = []
        for file in self.file_list:
            if not file.endswith('payload.S'):
                self.frame_file_list.append(file)
    
    def _generate_compile_shell(self, swap_idx):
        baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.output_path, file_name=f"compile_{swap_idx}.sh"
        )

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
        baker.add_cmd(
            gen_elf.save_cmd([*self.file_list, "-o", f"$OUTPUT_PATH/Testbench_{swap_idx}"])
        )

        gen_bin = ShellCommand("riscv64-unknown-elf-objcopy", ["-O", "binary"])
        baker.add_cmd(
            gen_bin.save_cmd(
                [f"$OUTPUT_PATH/Testbench_{swap_idx}", f"$OUTPUT_PATH/Testbench_{swap_idx}.bin"]
            )
        )

        dump_symbol = ShellCommand("nm")
        baker.add_cmd(
            dump_symbol.save_cmd(
                [
                    f"$OUTPUT_PATH/Testbench_{swap_idx}",
                    f"> $OUTPUT_PATH/Testbench_{swap_idx}.symbol",
                ]
            )
        )

        return baker
    
    def _generate_frame_block(self):
        swap_idx = self.trans.get_swap_idx()

        baker = self._generate_compile_shell(swap_idx)
        baker.run()
        symbol_table = get_symbol_file(os.path.join(self.output_path, f'Testbench_{swap_idx}.symbol'))

        file_origin = os.path.join(self.output_path, f'Testbench_{swap_idx}.bin')
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

        dut_mem_region = {'type':'dut', 'start_addr':common_begin + address_offset,\
                    'max_len':up_align(common_end, Page.size), 'init_file':file_origin_common, 'swap_id':self.trans.get_swap_idx()}
        vnt_mem_region = {'type':'vnt', 'start_addr':common_begin + address_offset,\
                    'max_len':up_align(common_end, Page.size), 'init_file':file_variant_common, 'swap_id':self.trans.get_swap_idx()}
        self.mem_cfg.add_mem_region('frame', [dut_mem_region, vnt_mem_region])

        file_text_swap = os.path.join(self.output_path, f'text_swap_{swap_idx}.bin')
        text_begin = symbol_table['_text_swap_start'] - address_base
        text_end   = symbol_table['_text_swap_end'] - address_base
        text_swap_byte_array = origin_byte_array[text_begin:text_end]
        with open(file_text_swap, "wb") as file:
            file.write(text_swap_byte_array)
        
        mem_region = {'type':'swap', 'start_addr':text_begin + address_offset,\
                    'max_len':up_align(text_end, Page.size) - text_begin, 'init_file':file_text_swap, 'swap_id':swap_idx}
        self.trans.trans_body.register_memory_region(mem_region)

        baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.output_path, file_name="disasm_frame.sh"
        )
        gen_asm = ShellCommand("riscv64-unknown-elf-objdump", ["-d"])
        baker.add_cmd(
            gen_asm.save_cmd(
                [
                    f"$OUTPUT_PATH/Testbench_{swap_idx}",
                    "-j .init",
                    "-j .mtrap",
                    "-j .strap",
                    "-j .text_frame",
                    "-j .data_frame",
                    "-j .swap_text",
                    f"> $OUTPUT_PATH/Testbench_frame.asm",
                ]
            )
        )
        baker.run()

    def _generate_body_block(self):
        swap_idx = self.trans.get_swap_idx()

        baker = self._generate_compile_shell(swap_idx)
        baker.run()

        symbol_table = get_symbol_file(os.path.join(self.output_path, f'Testbench_{swap_idx}.symbol'))
        self.trans.update_symbol_table(symbol_table)

        file_origin = os.path.join(self.output_path, f'Testbench_{swap_idx}.bin')
        with open(file_origin, "rb") as file:
            origin_byte_array = bytearray(file.read())
        
        if self.virtual:
            address_base = 0
        else:
            address_base = 0x80000000
        
        address_offset = 0x80000000
        
        file_text_swap = os.path.join(self.output_path, f'text_swap_{swap_idx}.bin')
        text_begin = symbol_table['_text_swap_start'] - address_base
        text_end   = symbol_table['_text_swap_end'] - address_base
        text_swap_byte_array = origin_byte_array[text_begin:text_end]
        with open(file_text_swap, "wb") as file:
            file.write(text_swap_byte_array)
        
        mem_region = {'type':'swap', 'start_addr':text_begin + address_offset,\
                    'max_len':up_align(text_end, Page.size) - text_begin, 'init_file':file_text_swap, 'swap_id':swap_idx}
        self.trans.trans_body.register_memory_region(mem_region)

        trans_body_type = type(self.trans.trans_body)
        if trans_body_type == TransVictimManager:
            data_name = 'data_victim'
        elif trans_body_type == TransTTEManager:
            data_name = 'data_tte'
        elif trans_body_type == TransTrainManager:
            if type(self.trans.trans_body.trans_victim) == TransVictimManager:
                data_name = 'data_train'
            else:
                data_name = 'data_tte_train'
        else:
            raise Exception('the type of trans_body is invalid')
        
        data_begin_label = f'_{data_name}_start'
        data_end_label = f'_{data_name}_end'

        file_data = os.path.join(self.output_path, f'{data_name}_{swap_idx}.bin')
        data_begin = symbol_table[data_begin_label] - address_base
        data_end   = symbol_table[data_end_label] - address_base
        data_byte_array = origin_byte_array[data_begin:data_end]
        with open(file_data, "wb") as file:
            file.write(data_byte_array)
        
        dut_mem_region = {'type':'dut', 'start_addr':data_begin + address_offset,\
            'max_len':up_align(data_end, Page.size) - data_begin, 'init_file':file_data, 'swap_id':swap_idx}
        vnt_mem_region = {'type':'vnt', 'start_addr':data_begin + address_offset,\
            'max_len':up_align(data_end, Page.size) - data_begin, 'init_file':file_data, 'swap_id':swap_idx}
        self.mem_cfg.add_mem_region(data_name, [dut_mem_region, vnt_mem_region])
        
        baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.output_path, file_name=f"disasm_body_{swap_idx}.sh"
        )
        gen_asm = ShellCommand("riscv64-unknown-elf-objdump", ["-d"])
        baker.add_cmd(
            gen_asm.save_cmd(
                [
                    f"$OUTPUT_PATH/Testbench_{swap_idx}",
                    f"-j .text_swap",
                    f'-j .{data_name}',
                    f"> $OUTPUT_PATH/Testbench_body_{swap_idx}.asm",
                ]
            )
        )
        baker.run()
    
    def _compute_coverage(self, base_list, variant_list):
        if max(base_list) != 0:
            try:
                base_list.remove(0)
                variant_list = variant_list[-1-len(base_list):-1]
            except ValueError:
                pass
        
        idx = 0.0
        list_len = len(base_list)
        interval = list_len/101
        diff_rate_byte_array = []
        for _ in range(100):
            idx = min(idx, list_len)
            new_idx = min(idx + interval, list_len)
            sample_base_diff = base_list[int(new_idx)] - base_list[int(idx)]
            sample_variant_diff = variant_list[int(new_idx)] - variant_list[int(idx)]
            diff_rate = sample_base_diff - sample_variant_diff
            diff_rate_byte_array.append(struct.pack('<i', diff_rate))
            idx = new_idx
        
        coverage_hash = hash(b''.join(diff_rate_byte_array))
        old_len = len(self.coverage)
        self.coverage[coverage_hash] = self.coverage.get(coverage_hash, 0) + 1
        new_len = len(self.coverage)

        if new_len > old_len:
            return True
        else:
            return False
    
    def _sim_and_analysis(self):
        baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.rtl_sim, file_name=f"rtl_sim.sh"
        )
        gen_asm = ShellCommand("make", [f'{self.rtl_sim_mode}'])
        baker.add_cmd(
            gen_asm.save_cmd(
                [

                ]
            )
        )
        baker.run()

        with open(f'{self.taint_log}.csv', "r") as file:
            taint_log = csv.reader(file)
            _ = next(taint_log)
            time_list = []
            base_list = []
            variant_list = []
            for time, base, variant in taint_log:
                time_list.append(int(time))
                base_list.append(int(base))
                variant_list.append(int(variant))
        
        windows_begin = 0
        sync_time = 0
        vicitm_end = 0
        for line in open(f'{self.taint_log}.log', 'r'):
            exec_info, exec_time = list(map(str.strip ,line.strip().split(',')))
            if exec_info == "DELAY_END_ENQ":
                windows_begin = int(exec_time)
            if exec_info == 'DELAY_END_DEQ':
                sync_time = int(exec_time)
            if exec_info == 'VCTM_END_DEQ':
                vicitm_end = int(exec_time)
        
        base_windows_list = base_list[windows_begin:sync_time]
        variant_windows_list = variant_list[windows_begin:sync_time]
        cover_expand = self._compute_coverage(base_windows_list, variant_windows_list)

        base_spread_list = base_list[sync_time:vicitm_end]
        variant_spread_list = variant_list[sync_time:vicitm_end]

        is_trigger = False
        is_leak = False
        if max(base_spread_list) > 0:
            is_trigger = True      
        else:
            return is_trigger, is_leak, cover_expand

        base_array = np.array(base_spread_list)
        base_array = base_array - np.average(base_array)
        variant_array = np.array(variant_spread_list)
        variant_array = variant_array - np.average(variant_array)

        cosim_result = 1 - base_array.dot(variant_array) / (np.linalg.norm(base_array) * np.linalg.norm(variant_array))
        
        if cosim_result > 0.1:
            is_leak = True
        elif cosim_result > 0.0000001:
            is_leak = False
        elif max(base_spread_list) > 40:
            is_leak = True
        else:
            is_leak = False

        return is_trigger, is_leak, cover_expand

    def _reorder_swap_list(self, stage):
        self.mem_cfg.add_swap_list(self.trans.generate_swap_list(stage))
        self.mem_cfg.dump_conf(self.output_path)
    
    def fuzz_stage1(self):
        # get frame and exit
        self._generate_frame()
        self._generate_frame_block()
        self.trans.move_data_section()

        victim_fuzz_iter = 2
        for _ in range(victim_fuzz_iter):
            self.trans.gen_victim()
            self.file_list = self.frame_file_list + \
                self.trans.file_generate(self.output_path, f'payload_{self.trans.get_swap_idx()}.S')
            
            self._generate_body_block()

            max_train_gen = 2 if self.trans.need_train() else 1
            for _ in range(max_train_gen):
                for _ in self.trans.gen_victim_train():
                    self.file_list = self.frame_file_list + \
                        self.trans.file_generate(self.output_path, f'payload_{self.trans.get_swap_idx()}.S')
                    self._generate_body_block()

                max_reorder_swap_list = 2 if self.trans.need_train() else 1
                for _ in range(max_reorder_swap_list):
                    self._reorder_swap_list(stage=1)
                    is_trigger, is_leak, cover_expand = self._sim_and_analysis()
                    if not is_trigger:
                        continue
                    else:
                        self.trans.store_trigger()
                        break
                else:
                    continue
                break
            else:
                continue

            if is_leak and cover_expand:
                self.trans.store_leak()
            else:
                max_mutate_time = 2
                for _ in range(max_mutate_time):
                    self.trans.mutate_victim()
                    self.file_list = self.frame_file_list + \
                        self.trans.file_generate(self.output_path, f'payload_{self.trans.get_swap_idx()}.S')
                    self._generate_body_block()

                    is_trigger, is_leak, cover_expand = self._sim_and_analysis()
                    if is_leak and cover_expand:
                        self.trans.store_leak()

    def run(self, cmd=None):
        self.baker.run(cmd)
    
