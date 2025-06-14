from BuildManager import *
from InitManager import *
from LinkerManager import *
from PageTableManager import *
from SectionUtils import *
from TransBlockUtils import *
from TransVictimBlock import *
from TransAdjustBlock import *
from TransProtectBlock import *
from TransDecodeBlock import *
from TransTrainBlock import *
from TransFrameBlock import *
import libconf
import csv
import numpy as np
import struct
import os
import random
from enum import *

class MemCfg:
    def __init__(self, mem_start, mem_len, code_repo):
        self.mem_start = mem_start
        self.mem_len = mem_len
        self.mem_regions = {}
        self.mem_region_kind = ['frame', 'data_train', 'data_adjust', 'data_protect',\
            'data_decode', 'data_victim', 'swap']
        for kind in self.mem_region_kind:
            self.mem_regions[kind] = []
        self.swap_list = []
        self.code_repo = code_repo
        self.sub_repo = None
    
    def update_sub_repo(self, sub_repo):
        self.sub_repo = sub_repo
    
    def add_mem_region(self, kind, mem_region):
        assert kind in self.mem_region_kind and kind != 'swap'
        self.mem_regions[kind] = mem_region
    
    def add_swap_list(self, swap_block_list):
        self.swap_list = []
        self.mem_regions['swap'] = []
        for swap_block in swap_block_list:
            if swap_block['swap_id'] not in self.swap_list:
                self.mem_regions['swap'].append(swap_block)
            self.swap_list.append(swap_block['swap_id'])
    
    def dump_conf(self, target='duo'):
        swap_path = os.path.join(self.code_repo, self.sub_repo, 'swap_mem.cfg')
        with open(swap_path, "wt") as file:
            tmp_mem_cfg = {}
            tmp_mem_cfg['start_addr'] = self.mem_start
            tmp_mem_cfg['max_mem_size'] = self.mem_len
            mem_region = []
            for regions in self.mem_regions.values():
                regions = copy.deepcopy(regions)
                for region in regions:
                    match target:
                        case 'duo':
                            pass
                        case 'dut':
                            if region['type'] == 'vnt':
                                continue
                            elif region['type'] == 'duo':
                                region['type'] = 'dut'
                        case 'vnt':
                            if region['type'] == 'dut':
                                continue
                            elif region['type'] == 'duo':
                                region['type'] = 'dut'
                            elif region['type'] == 'vnt':
                                region['type'] = 'dut'
                    mem_region.append(region)
            tmp_mem_cfg['memory_regions'] = tuple(mem_region)
            tmp_mem_cfg['swap_list'] = self.swap_list
            file.write(libconf.dumps(tmp_mem_cfg))
    
    def load_conf(self, output_path):
        with open(os.path.join(output_path, 'swap_mem.cfg'), "rt") as file:
            self.mem_cfg = libconf.load(file)

class TransManager:
    def __init__(self, config, output_path, mem_cfg):
        self.config = config

        self.baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, output_path, output_path
        )

        self.output_path = output_path
        self.sup_repo = output_path
        self.sub_repo = None

        self.extension = [
            "RV_I",
            "RV64_I",
            "RV_ZICSR",
            "RV_F",
            "RV64_F",
            "RV_D",
            "RV64_D",
            "RV_A",
            "RV64_A",
            "RV_M",
            "RV64_M",
            "RV_C",
            "RV64_C",
            "RV_C_D",
        ]

        self.init = InitManager(
            self.config['init'],
            self.output_path
        )

        self.page_table = PageTableManager(
            self.config["page_table"]
        )
        self.linker = LinkerManager()

        self.file_list = []
        self.link_file = None
        self.mem_cfg = mem_cfg
        self.coverage = {}

        self.swap_block_list = []
        self.swap_id = 0
        self.swap_map = {}

        self.trans_frame = TransFrameManager(self.config['trans_frame'], self.extension, self.output_path)
        self.get_data_section()

        self.trans_exit = TransExitManager(self.config['trans_body'], self.extension, self.output_path, self.data_frame_section, self.trans_frame)
        self._distr_swap_id(self.trans_exit)

        self.trans_victim = TransVictimManager(self.config['trans_body'], self.extension, self.output_path, self.data_victim_section, self.trans_frame)
        self._distr_swap_id(self.trans_victim)

        self.trans_protect = TransProtectManager(self.config['trans_body'], self.extension, self.output_path, self.data_protect_section, self.trans_frame)
        self._distr_swap_id(self.trans_protect)

        self.trans_adjust = TransAdjustManager(self.config['trans_body'], self.extension, self.output_path, self.data_adjust_section, self.trans_frame)
        self._distr_swap_id(self.trans_adjust)

        self.trans_decode = TransDecodeManager(self.config['trans_body'], self.extension, self.output_path, self.data_decode_section, self.trans_frame)
        self._distr_swap_id(self.trans_decode)
            
        self.trans_train_pool = []
        self.trans_train_id = 0
        for _ in range(10):
            trans_train = TransTrainManager(self.config['trans_body'], self.extension, self.output_path, self.data_train_section, self.trans_frame)
            self.trans_train_pool.append(trans_train)
            self._distr_swap_id(trans_train)
    
    def _distr_swap_id(self, trans_swap):
        trans_swap.register_swap_idx(self.swap_id)
        self.swap_map[self.swap_id] = trans_swap
        self.swap_id += 1

    def get_data_section(self):
        data_frame_section, data_train_section, data_adjust_section, data_protect_section, data_victim_section, data_decode_section = self.trans_frame.get_data_section()
        self.data_frame_section = data_frame_section
        self.data_train_section = data_train_section
        self.data_adjust_section = data_adjust_section
        self.data_protect_section = data_protect_section
        self.data_victim_section = data_victim_section
        self.data_decode_section = data_decode_section

    def _collect_compile_file(self, file_list):
        self.file_list.extend(file_list)
    
    def update_sub_repo(self, sub_repo):
        self.sub_repo = sub_repo
        self.output_path = os.path.join(self.sup_repo, self.sub_repo)
            
    def _generate_frame(self):
        page_table_name = "page_table.S"
        ld_name = "link.ld"

        self.trans_frame.gen_block()
        self.trans_exit.gen_block()

        self.section_list = []
        self._collect_compile_file(
            self.init.file_generate(self.output_path, f"init.S")
        )
        self._collect_compile_file(
            self.trans_exit.file_generate(self.output_path, 'trans_exit.S')
        )
        self._collect_compile_file(
            self.trans_frame.file_generate(self.output_path, 'trans_frame.S')
        )
        self.section_list.extend(self.init.get_section_list())
        self.section_list.extend(self.trans_frame.get_section_list())
        self.section_list.extend(self.trans_exit.get_section_list())

        self.page_table.register_sections(self.section_list)
        self._collect_compile_file(
            self.page_table.file_generate(self.output_path, page_table_name)
        )
        self.section_list.extend(self.page_table.get_section_list())

        self.linker.append_section_list(self.section_list)
        self.link_file = self.linker.file_generate(self.output_path, ld_name)

        self.frame_file_list = []
        for file in self.file_list:
            # TODO: emmm, this is a little bit tricky
            if not file.endswith('trans_exit.S'):
                self.frame_file_list.append(file)
    
    def _generate_compile_shell(self, swap_idx, trans_block):
        baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.output_path, self.output_path, file_name=f"compile_{swap_idx}.sh"
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
                f"-T{self.link_file}",
            ],
        )

        output_name_base = f"$OUTPUT_PATH/Testbench_{swap_idx}"
        output_name = f'{output_name_base}.elf'
        baker.add_cmd(gen_elf.gen_cmd([*self.file_list], "-o", output_name))

        gen_bin = ShellCommand("riscv64-unknown-elf-objcopy", ["-O", "binary"])
        baker.add_cmd(gen_bin.gen_cmd([gen_elf.last_output, f"{output_name_base}.bin"]))

        gen_sym = ShellCommand("nm")
        baker.add_cmd(gen_sym.gen_cmd([gen_elf.last_output, ">", f"{output_name_base}.symbol"]))

        trans_body_type = type(trans_block)
        gen_asm = ShellCommand("riscv64-unknown-elf-objdump", ["-d"])
        data_name = None
        phase = 'exit'
        if trans_body_type == TransExitManager:
            baker.add_cmd(
                gen_asm.gen_cmd(
                    [
                        f"{output_name}",
                        "-j .init",
                        "-j .mtrap",
                        "-j .strap",
                        "-j .text_frame",
                        "-j .data_frame",
                        "-j .swap_text"
                    ],
                    ">",
                    f"$OUTPUT_PATH/Testbench_frame.asm"
                )
            )
        else:
            if trans_body_type == TransVictimManager:
                data_name = 'data_victim'
                phase = 'attack'
            elif trans_body_type == TransDecodeManager:
                data_name = 'data_decode'
                phase = 'decode'
            elif trans_body_type == TransTrainManager:
                data_name = 'data_train'
                phase = 'train'
            elif trans_body_type == TransAdjustManager:
                data_name = 'data_adjust'
                phase = 'adjust'
            elif trans_body_type == TransProtectManager:
                data_name = 'data_protect'
                phase = 'protect'
            else:
                raise Exception('the type of trans_body is invalid')
            baker.add_cmd(
                gen_asm.gen_cmd(
                    [
                        f"{output_name}",
                        f"-j .text_swap",
                        f'-j .{data_name}'
                    ],
                    ">",
                    f"$OUTPUT_PATH/Testbench_body_{swap_idx}.asm"
                )
            )

        baker.run()

        return baker, data_name, phase

    def _generate_frame_block(self):
        swap_idx = self.trans_exit.swap_idx

        baker, _, phase = self._generate_compile_shell(swap_idx, self.trans_exit)
        baker.run()
        symbol_table = get_symbol_file(os.path.join(self.output_path, f'Testbench_{swap_idx}.symbol'))

        file_origin = os.path.join(self.output_path, f'Testbench_{swap_idx}.bin')
        with open(file_origin, "rb") as file:
            origin_byte_array = bytearray(file.read())

        address_base = 0
        
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

        origin_text_base = 'origin_common.bin'
        origin_text = os.path.join(self.output_path, origin_text_base)
        variant_text_base = 'variant_common.bin'
        variant_text = os.path.join(self.output_path, variant_text_base)
        dut_mem_region = {'type':'dut', 'start_addr':common_begin + address_offset,\
                    'max_len':up_align(common_end, Page.size), 'init_file':origin_text}
        vnt_mem_region = {'type':'vnt', 'start_addr':common_begin + address_offset,\
                    'max_len':up_align(common_end, Page.size), 'init_file':variant_text}
        self.mem_cfg.add_mem_region('frame', [dut_mem_region, vnt_mem_region])

        file_text_swap_base = f'text_swap_{swap_idx}.bin'
        file_text_swap = os.path.join(self.output_path, file_text_swap_base)
        text_begin = symbol_table['_text_swap_start'] - address_base
        text_end   = symbol_table['_text_swap_end'] - address_base
        text_swap_byte_array = origin_byte_array[text_begin:text_end]
        with open(file_text_swap, "wb") as file:
            file.write(text_swap_byte_array)
        
        mem_region = {'type':'swap', 'start_addr':text_begin + address_offset,\
                    'max_len':up_align(text_end, Page.size) - text_begin, \
                    'init_file':file_text_swap, 'swap_id':swap_idx, \
                    'phase':phase, 'mode':self.trans_exit.mode}
        self.trans_exit.register_memory_region(mem_region)

        self.trans_frame.move_data_section()

    def _generate_body_block(self, trans_block, mem_region=None):
        if mem_region is None:
            swap_idx = trans_block.swap_idx
            self.file_list = self.frame_file_list + trans_block.file_generate(self.output_path, f'payload_{trans_block.swap_idx}.S')
            baker, data_name, phase = self._generate_compile_shell(swap_idx, trans_block)
            baker.run()
        else:
            swap_idx = mem_region['swap_id']
            swap_phase = mem_region['phase']
            match swap_phase:
                case 'attack':
                    data_name = 'data_victim'
                case 'adjust':
                    data_name = 'data_adjust'
                case 'decode':
                    data_name = 'data_decode'
                case 'protect':
                    data_name = 'data_protect'
                case 'train':
                    data_name = 'data_train'
                case 'exit':
                    return
                case _:
                    raise Exception(f"invalid phase name:{swap_phase}")
            compile_shell = os.path.join(self.output_path, f'compile_{swap_idx}.sh')
            os.system(f'{compile_shell}')

        symbol_table = get_symbol_file(os.path.join(self.output_path, f'Testbench_{swap_idx}.symbol'))
        if trans_block is not None:
            trans_block.add_symbol_table(symbol_table)

        file_origin = os.path.join(self.output_path, f'Testbench_{swap_idx}.bin')
        with open(file_origin, "rb") as file:
            origin_byte_array = bytearray(file.read())
        
        address_base = 0
        address_offset = 0x80000000
        
        file_text_swap_base = f'text_swap_{swap_idx}.bin'
        file_text_swap = os.path.join(self.output_path, file_text_swap_base)
        text_begin = symbol_table['_text_swap_start'] - address_base
        text_end   = symbol_table['_text_swap_end'] - address_base
        text_swap_byte_array = origin_byte_array[text_begin:text_end]
        with open(file_text_swap, "wb") as file:
            file.write(text_swap_byte_array)

        data_begin_label = f'_{data_name}_start'
        data_end_label = f'_{data_name}_end'

        file_data_base = f'{data_name}_{swap_idx}.bin'
        file_data = os.path.join(self.output_path, file_data_base)
        data_begin = symbol_table[data_begin_label] - address_base
        data_end   = symbol_table[data_end_label] - address_base
        data_byte_array = origin_byte_array[data_begin:data_end]
        with open(file_data, "wb") as file:
            file.write(data_byte_array)
        
        if mem_region is None:
            swap_mem_region = {'type':'swap', 'start_addr':text_begin + address_offset,\
                        'max_len':up_align(text_end, Page.size) - text_begin, \
                        'init_file':file_text_swap, 'swap_id':swap_idx, \
                        'phase':phase, 'mode':trans_block.mode}
            trans_block.register_memory_region(swap_mem_region)
            
            duo_mem_region = {'type':'duo', 'start_addr':data_begin + address_offset,\
                'max_len':up_align(data_end, Page.size) - data_begin, \
                'init_file':file_data}
            self.mem_cfg.add_mem_region(data_name, [duo_mem_region])
    
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
            # sample_variant_diff = variant_list[int(new_idx)] - variant_list[int(idx)]
            # diff_rate = sample_base_diff - sample_variant_diff
            diff_rate_byte_array.append(struct.pack('<i', sample_base_diff))
            idx = new_idx
        
        coverage_hash = hash(b''.join(diff_rate_byte_array))
        old_len = len(self.coverage)
        self.coverage[coverage_hash] = self.coverage.get(coverage_hash, 0) + 1
        new_len = len(self.coverage)

        if new_len > old_len:
            return True
        else:
            return False
    
    def gen_train_swap_list(self, config, align, single):
        self.trans_train_id = 0
        self.data_train_section.clear()
        self.mem_cfg.add_mem_region('data_train', [])

        windows_param = 0.8 if self.trans_victim.need_train() else 0.4

        swap_block_list = [self.trans_adjust.mem_region, self.trans_protect.mem_region, self.trans_victim.mem_region, self.trans_exit.mem_region]
        for i in range(0, 10):
            random_value = random.random()
            if random_value >= windows_param:
                break
            elif random_value < windows_param * 0.6 and i != 0:
                trans_body = self.trans_train_pool[self.trans_train_id - 1]
                swap_block_list.insert(0, trans_body.mem_region)
            else:
                train_type_array = [
                    TrainType.BRANCH_NOT_TAKEN,
                    TrainType.BRANCH_TAKEN,
                    TrainType.JALR,
                    TrainType.CALL,
                    TrainType.RETURN,
                    TrainType.JMP,

                    TrainType.FLOAT,
                    TrainType.INT,
                    TrainType.SYSTEM,
                    TrainType.LOAD,
                    TrainType.STORE,
                    TrainType.AMO
                ]

                train_type = random.choice(train_type_array)

                trans_body = self.trans_train_pool[self.trans_train_id]
                self.trans_train_id += 1
                trans_body.gen_block(config, train_type, align, single, self.trans_victim)
                self._generate_body_block(trans_body)

                swap_block_list.insert(0, trans_body.mem_region)

        self.swap_block_list = swap_block_list

    def build_frame(self):
        self._generate_frame()
        self._generate_frame_block()

    def generate(self):
        self.trans_victim.gen_block(EncodeType.FUZZ_DEFAULT)
        self._generate_body_block(self.trans_victim)
        self.swap_block_list = [self.trans_protect.mem_region, self.trans_victim.mem_region, self.trans_exit.mem_region]
    
    def record_fuzz(self):
        record = {'train':[]}
        for swap_mem_region in self.swap_block_list[:-1]:
            trans_body = self.swap_map[swap_mem_region['swap_id']]
            name, trans_record = trans_body.record_fuzz()
            if name == 'train':
                record['train'].append(trans_record)
            else:
                record[name] = trans_record
        return record
