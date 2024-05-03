from BuildManager import *
from InitManager import *
from LinkerManager import *
from PageTableManager import *
from SectionUtils import *
from TransBlockUtils import *
from TransVictimBlock import *
from TransTTEBlock import *
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
            if swap_block['swap_id'] not in self.swap_list:
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
    def __init__(self, hjson_filename, output_path, virtual):
        hjson_file = open(hjson_filename)
        self.config = hjson.load(hjson_file)
        hjson_file.close()

        self.baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, output_path
        )
        
        self.attack_privilege = self.config["attack"]
        self.victim_privilege = self.config["victim"]
        privilege_stage = {"M": 3, "S": 1, "U": 0}

        # TODO: is this really necessary ?
        assert (
            privilege_stage[self.attack_privilege]
            <= privilege_stage[self.victim_privilege]
        ), "the privilege of vicitm smaller than attack's is meanless"

        self.output_path = output_path
        self.virtual = virtual if self.attack_privilege != "M" else False

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
            self.virtual,
            self.victim_privilege, 
            self.output_path
        )

        self.page_table = PageTableManager(
            self.config["page_table"], self.attack_privilege == "U"
        )
        self.linker = LinkerManager(self.virtual)

        self.file_list = []
        self.mem_cfg = MemCfg(0x80000000, 0x40000)
        self.coverage = {}

        self.swap_block_list = []
        self.swap_victim_list = []
        self.swap_tte_list = []
        self.swap_id = 0
        self.swap_map = {}

        self.trans_frame = TransFrameManager(self.config['trans_frame'], self.extension, self.victim_privilege, self.virtual, self.output_path)
        self.get_data_section()

        self.trans_exit = TransExitManager(self.config['trans_body'], self.extension, self.victim_privilege, self.virtual, self.output_path, self.data_frame_section)
        self._distr_swap_id(self.trans_exit)

        self.trans_victim = TransVictimManager(self.config['trans_body'], self.extension, self.victim_privilege, self.virtual, self.output_path, self.data_victim_section)
        self._distr_swap_id(self.trans_victim)

        self.trans_tte = TransTTEManager(self.config['trans_body'], self.extension, self.victim_privilege, self.virtual, self.output_path, self.data_tte_section)
        self._distr_swap_id(self.trans_tte)

        self.victim_train = {}
        for train_type in TrainType:
            self.victim_train[train_type] = TransTrainManager(self.config['trans_body'], self.extension, self.victim_privilege, self.virtual, self.output_path, self.data_train_section)
            self._distr_swap_id(self.victim_train[train_type])
            
        self.victim_trigger_pool = []
        for _ in range(3):
            trans_train = TransTrainManager(self.config['trans_body'], self.extension, self.victim_privilege, self.virtual, self.output_path, self.data_tte_train_section)
            self.victim_trigger_pool.append(trans_train)
            self._distr_swap_id(trans_train)

        self.tte_trigger_pool = []
        for _ in range(3):
            trans_train = TransTrainManager(self.config['trans_body'], self.extension, self.victim_privilege, self.virtual, self.output_path, self.data_tte_train_section)
            self.tte_trigger_pool.append(trans_train)
            self._distr_swap_id(trans_train)
    
    def _distr_swap_id(self, trans_swap):
        trans_swap.register_swap_idx(self.swap_id)
        self.swap_map[self.swap_id] = trans_swap
        self.swap_id += 1

    def get_data_section(self):
        data_frame_section, data_train_section, data_tte_section, data_tte_train_section, data_victim_section = self.trans_frame.get_data_section()
        self.data_frame_section = data_frame_section
        self.data_train_section = data_train_section
        self.data_tte_section = data_tte_section
        self.data_tte_train_section = data_tte_train_section
        self.data_victim_section = data_victim_section

    def _collect_compile_file(self, file_list):
        self.file_list.extend(file_list)
    
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

        if self.virtual:
            self.page_table.register_sections(self.section_list)
            self._collect_compile_file(
                self.page_table.file_generate(self.output_path, page_table_name)
            )
            self.section_list.extend(self.page_table.get_section_list())

        self.linker.append_section_list(self.section_list)
        self.linker.file_generate(self.output_path, ld_name)

        self.frame_file_list = []
        for file in self.file_list:
            # TODO: emmm, this is a little bit tricky
            if not file.endswith('trans_exit.S'):
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

        output_name_base = f"$OUTPUT_PATH/Testbench_{swap_idx}"
        baker.add_cmd(gen_elf.gen_cmd([*self.file_list], "-o", output_name_base))

        gen_bin = ShellCommand("riscv64-unknown-elf-objcopy", ["-O", "binary"])
        baker.add_cmd(gen_bin.gen_cmd([gen_elf.last_output, f"{output_name_base}.bin"]))

        gen_sym = ShellCommand("nm")
        baker.add_cmd(gen_sym.gen_cmd([gen_elf.last_output, ">", f"{output_name_base}.symbol"]))

        return baker

    def _generate_frame_block(self):
        swap_idx = self.trans_exit.swap_idx

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
                    'max_len':up_align(common_end, Page.size), 'init_file':file_origin_common, 'swap_id':self.trans_exit.swap_idx}
        vnt_mem_region = {'type':'vnt', 'start_addr':common_begin + address_offset,\
                    'max_len':up_align(common_end, Page.size), 'init_file':file_variant_common, 'swap_id':self.trans_exit.swap_idx}
        self.mem_cfg.add_mem_region('frame', [dut_mem_region, vnt_mem_region])

        file_text_swap = os.path.join(self.output_path, f'text_swap_{swap_idx}.bin')
        text_begin = symbol_table['_text_swap_start'] - address_base
        text_end   = symbol_table['_text_swap_end'] - address_base
        text_swap_byte_array = origin_byte_array[text_begin:text_end]
        with open(file_text_swap, "wb") as file:
            file.write(text_swap_byte_array)
        
        mem_region = {'type':'swap', 'start_addr':text_begin + address_offset,\
                    'max_len':up_align(text_end, Page.size) - text_begin, 'init_file':file_text_swap, 'swap_id':swap_idx}
        self.trans_exit.register_memory_region(mem_region)

        baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.output_path, file_name="disasm_frame.sh"
        )
        gen_asm = ShellCommand("riscv64-unknown-elf-objdump", ["-d"])
        baker.add_cmd(
            gen_asm.gen_cmd(
                [
                    f"$OUTPUT_PATH/Testbench_{swap_idx}",
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
        baker.run()

        self.trans_frame.move_data_section()

    def _generate_body_block(self, trans_block):
        swap_idx = trans_block.swap_idx

        self.file_list = self.frame_file_list + trans_block.file_generate(self.output_path, f'payload_{trans_block.swap_idx}.S')
        baker = self._generate_compile_shell(swap_idx)
        baker.run()

        symbol_table = get_symbol_file(os.path.join(self.output_path, f'Testbench_{swap_idx}.symbol'))
        trans_block.add_symbol_table(symbol_table)

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
        trans_block.register_memory_region(mem_region)

        trans_body_type = type(trans_block)
        if trans_body_type == TransVictimManager:
            data_name = 'data_victim'
        elif trans_body_type == TransTTEManager:
            data_name = 'data_tte'
        elif trans_body_type == TransTrainManager:
            if type(trans_block.trans_victim) == TransVictimManager:
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
            gen_asm.gen_cmd(
                [
                    f"$OUTPUT_PATH/Testbench_{swap_idx}",
                    f"-j .text_swap",
                    f'-j .{data_name}'
                ],
                ">",
                f"$OUTPUT_PATH/Testbench_body_{swap_idx}.asm"
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
        baker.add_cmd(gen_asm.gen_cmd())
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
        is_trigger = False
        for line in open(f'{self.taint_log}.log', 'r'):
            exec_time, exec_info, exec_id = list(map(str.strip ,line.strip().split(',')))
            exec_time = int(exec_time)
            id = int(exec_id)
            if exec_info == "DELAY_END_ENQ":
                windows_begin = int(exec_time)
            if exec_info == 'DELAY_END_DEQ':
                sync_time = int(exec_time)
            if exec_info == 'VCTM_END_DEQ':
                vicitm_end = int(exec_time)
            if exec_info == "TEXE_START_ENQ":
                is_trigger = True

        is_leak = False
        cover_expand = False
        if not is_trigger:
            return is_trigger, is_leak, cover_expand
        else:
            # TODO: this baker is repeated, and it not necessary
            cp_baker = BuildManager(
                {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.repo_path, file_name=f"get_taint_log.sh"
            )
            gen_asm = ShellCommand("cp", [])
            cp_baker.add_cmd(gen_asm.gen_cmd([f'{self.taint_log}.log', f'{self.repo_path}']))
            cp_baker.add_cmd(gen_asm.gen_cmd([f'{self.taint_log}.csv', f'{self.repo_path}']))
            cp_baker.run()
        
        base_windows_list = base_list[windows_begin:sync_time]
        variant_windows_list = variant_list[windows_begin:sync_time]
        cover_expand = self._compute_coverage(base_windows_list, variant_windows_list)

        base_spread_list = base_list[sync_time:vicitm_end]
        variant_spread_list = variant_list[sync_time:vicitm_end]

        base_array = np.array(base_spread_list)
        base_array = base_array - np.average(base_array)
        variant_array = np.array(variant_spread_list)
        variant_array = variant_array - np.average(variant_array)

        cosim_result = 1 - base_array.dot(variant_array) / (np.linalg.norm(base_array) * np.linalg.norm(variant_array))
        
        if cosim_result > 0.1:
            is_leak = True
        elif max(base_windows_list) > 40:
            is_leak = True
        else:
            is_leak = False

        return is_trigger, is_leak, cover_expand
    
    def _gen_train_swap_list(self):
        train_prob = {
            TrainType.BRANCH_NOT_TAKEN: 0.15,
            TrainType.JALR: 0.1,
            TrainType.CALL: 0.15,
            TrainType.RETURN: 0.15,
            TrainType.JMP: 0.05
        }
        match self.trans_victim.trigger_type:
            case TriggerType.BRANCH:
                train_prob[TrainType.BRANCH_NOT_TAKEN] += 0.4
            case TriggerType.JALR | TriggerType.JMP:
                train_prob[TrainType.JALR] += 0.4
            case TriggerType.RETURN:
                train_prob[TrainType.CALL] += 0.2
                train_prob[TrainType.RETURN] += 0.2
        train_type = random_choice(train_prob)
        match(train_type):
            case TrainType.BRANCH_NOT_TAKEN:
                not_taken_swap_idx = self.victim_train[TrainType.BRANCH_NOT_TAKEN].mem_region
                taken_swap_idx = self.victim_train[TrainType.BRANCH_TAKEN].mem_region
                branch_not_taken_1 = [not_taken_swap_idx]
                branch_not_taken_2 = [not_taken_swap_idx, not_taken_swap_idx]
                branch_taken_1 = [taken_swap_idx]
                branch_taken_2 = [taken_swap_idx, taken_swap_idx]
                branch_balance = random.choice([[not_taken_swap_idx, taken_swap_idx], [taken_swap_idx, not_taken_swap_idx]])
                return random.choice([branch_not_taken_1, branch_not_taken_2, branch_taken_1, branch_taken_2, branch_balance])
            case _:
                return [self.victim_train[train_type].mem_region]

    def _stage1_reorder_swap_list(self):
        swap_block_list = [self.trans_victim.mem_region, self.trans_exit.mem_region]
        if self.trans_victim.need_train():
            for _ in range(0, 4):
                if random.random() < 0.2:
                    break
                swap_block_list[0:0] = self._gen_train_swap_list()
        self.swap_block_list = swap_block_list
        self.mem_cfg.add_swap_list(self.swap_block_list)
        self.mem_cfg.dump_conf(self.output_path)
    
    def store_tte(self, swap_list, template_folder):
        file_list = []
        for i,swap_id in enumerate(swap_list[:-1]):
            train_fold = os.path.join(template_folder, f'train_{i}')
            file_list.append(train_fold)
            if not os.path.exists(train_fold):
                os.makedirs(train_fold)
            trans_body = self.swap_map[swap_id]
            trans_body.dump_trigger_block(train_fold)
        
        train_fold = os.path.join(template_folder, f'tte')
        file_list.append(train_fold)
        if not os.path.exists(train_fold):
            os.makedirs(train_fold)
        trans_body = self.swap_map[swap_list[-1]]
        trans_body.dump_trigger_block(train_fold)

        block_order = os.path.join(template_folder, f'block_order')
        with open(block_order, "wt") as file:
            for file_name in file_list:
                file.write(f'{file_name}\n')
    
    def store_template(self, iter_num, repo_path, template_folder, only_trigger):
        self.swap_list = []
        for swap_block in self.swap_block_list:
            if type(swap_block) == list:
                sub_swap_list = []
                for swap_sub_block in swap_block:
                    sub_swap_list.append(swap_sub_block['swap_id'])
                self.swap_list.append(sub_swap_list)
            else:
                self.swap_list.append(swap_block['swap_id'])

        trigger_repo_path = os.path.join(repo_path, template_folder)
        if not os.path.exists(trigger_repo_path):
            os.makedirs(trigger_repo_path)

        file_list = []

        new_template = os.path.join(trigger_repo_path, str(iter_num))
        if not os.path.exists(new_template):
            os.makedirs(new_template)
        for i,swap_id in enumerate(self.swap_list[:-2]):
            if type(swap_id) == list:
                train_fold = os.path.join(new_template, f'tte')
                file_list.append(train_fold)
                if not os.path.exists(train_fold):
                    os.makedirs(train_fold)
                self.store_tte(self, swap_id, train_fold)
            else:
                train_fold = os.path.join(new_template, f'train_{i}')
                file_list.append(train_fold)
                if not os.path.exists(train_fold):
                    os.makedirs(train_fold)
                trans_body = self.swap_map[swap_id]
                trans_body.dump_trigger_block(train_fold)
        
        train_fold = os.path.join(new_template, f'victim')
        file_list.append(train_fold)
        if not os.path.exists(train_fold):
            os.makedirs(train_fold)
        trans_body = self.swap_map[self.swap_list[-2]]

        if only_trigger:
            trans_body.dump_trigger_block(train_fold)
        else:
            trans_body.dump_leak_block(train_fold)

        block_order = os.path.join(new_template, f'block_order')
        with open(block_order, "wt") as file:
            for file_name in file_list:
                file.write(f'{file_name}\n')

        # this baker is repeated, and it not necessary
        cp_baker = BuildManager(
                {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, repo_path, file_name=f"store_taint_log.sh"
            )
        gen_asm = ShellCommand("cp", [])
        cp_baker.add_cmd(gen_asm.gen_cmd([f'{repo_path}/*.log', f'{new_template}']))
        cp_baker.add_cmd(gen_asm.gen_cmd([f'{repo_path}/*.csv', f'{new_template}']))
        cp_baker.run()
    
    def _trigger_reduce(self):
        swap_block_list = self.swap_block_list
        for _ in range(len(swap_block_list)-2):
            for i in range(0, len(swap_block_list)-2):
                tmp_swap_block_list = copy.copy(swap_block_list)
                tmp_swap_block_list.pop(i)
                self.mem_cfg.add_swap_list(tmp_swap_block_list)
                self.mem_cfg.dump_conf(self.output_path)
                is_trigger, is_leak, cover_expand = self._sim_and_analysis()
                if is_trigger:
                    swap_block_list = tmp_swap_block_list
                    break
            else:
                break
        self.swap_block_list = swap_block_list
        self.mem_cfg.add_swap_list(swap_block_list)
        self.mem_cfg.dump_conf(self.output_path)

    def generate(self):
        self._generate_frame()
        self._generate_frame_block()

        self.trans_victim.gen_block('default', None)
        self._generate_body_block(self.trans_victim)

        self.mem_cfg.add_swap_list([self.trans_victim.mem_region, self.trans_exit.mem_region])
        self.mem_cfg.dump_conf(self.output_path)
    
    def gen_victim_train(self):
        self.data_train_section.clear()
        for train_type,trans_block in self.victim_train.items():
            trans_block.gen_block(train_type, self.trans_victim, None)
            self._generate_body_block(trans_block)
    
    def fuzz_stage1(self, rtl_sim, rtl_sim_mode, taint_log, repo_path, do_fuzz = True):
        if repo_path is None:
            self.repo_path = self.output_path
        else:
            self.repo_path = repo_path
        if not os.path.exists(self.repo_path):
            os.makedirs(self.repo_path)
        template_folder = "trigger_template"
        
        self.rtl_sim = rtl_sim
        assert rtl_sim_mode in ['vcs', 'vlt'], "the rtl_sim_mode must be in vcs and vlt"
        self.rtl_sim_mode = rtl_sim_mode
        self.taint_log = taint_log
        
        # get frame and exit
        self._generate_frame()
        self._generate_frame_block()

        VICTIM_FUZZ_MAX_ITER = 200
        TRAIN_GEN_MAX_ITER = 2
        REORDER_SWAP_LIST_MAX_ITER = 3
        ENCODE_MUTATE_MAX_ITER = 5

        stage1_iter_num_file = os.path.join(self.repo_path, "stage1_iter_num")
        if not os.path.exists(stage1_iter_num_file):
            begin_iter_num = 0
        else:
            with open(stage1_iter_num_file, "rt") as file:
                begin_iter_num = 1 + int(file.readline().strip())

        victim_fuzz_iter = VICTIM_FUZZ_MAX_ITER
        for iter_num in range(begin_iter_num, begin_iter_num + victim_fuzz_iter):
            self.trans_victim.gen_block('default', None)
            self._generate_body_block(self.trans_victim)

            max_train_gen = TRAIN_GEN_MAX_ITER if self.trans_victim.need_train() else 1
            for _ in range(max_train_gen):
                self.gen_victim_train()

                max_reorder_swap_list = REORDER_SWAP_LIST_MAX_ITER if self.trans_victim.need_train() else 1
                for _ in range(max_reorder_swap_list):
                    self._stage1_reorder_swap_list()
                    is_trigger, is_leak, cover_expand = self._sim_and_analysis()
                    if not do_fuzz:
                        return
                    if not is_trigger:
                        continue
                    else:
                        break
                else:
                    continue
                break
            
            if is_trigger:
                self._trigger_reduce()
                if is_leak:
                    self.store_template(iter_num, self.repo_path, template_folder, True)
                else:
                    max_mutate_time = ENCODE_MUTATE_MAX_ITER
                    for _ in range(max_mutate_time):
                        self.trans_victim.mutate()
                        self._generate_body_block(self.trans_victim)
                        is_trigger, is_leak, cover_expand = self._sim_and_analysis()
                        if is_leak:
                            self.store_template(iter_num, self.repo_path, template_folder, True)
                            break
            
            self.record_fuzz(iter_num, is_trigger, is_leak, stage_num=1)
    
    def fuzz_stage2(self, rtl_sim, rtl_sim_mode, taint_log, repo_path, do_fuzz = True):
        

    def record_fuzz(self, iter_num, is_trigger, is_leak, stage_num):
        with open(os.path.join(self.repo_path, f'stage{stage_num}_iter_record'), "at") as file:
            file.write(f'iter_num:\t{iter_num}\n')
            file.write(f'is_trigger:\t{is_trigger}\n')
            file.write(f'is_leak:\t{is_leak}\n')
            for swap_block in self.swap_block_list:
                trans_body = self.swap_map[swap_block['swap_id']]
                trans_body.record_fuzz(file)
            file.write('\n')

        with open(os.path.join(self.repo_path, f"stage{stage_num}_iter_num"), "wt") as file:
            file.write(str(iter_num))

    def run(self, cmd=None):
        self.baker.run(cmd)
    
