from TransManager import *
import hjson
import threading
from FuzzUtils import *

class FuzzManager:
    def __init__(self, hjson_filename, output_path, prefix):
        self.output_path = output_path
        self.prefix_domain = prefix
        self.mem_cfg = MemCfg(0x80000000, 0x40000, self.output_path)
        hjson_file = open(hjson_filename)
        config = hjson.load(hjson_file)
        self.trans = TransManager(config, self.output_path, self.mem_cfg)
        self.LEAK_REMAIN_THRESHOLD = config['leak_remain_threshold']
        self.LEAK_EXPLODE_THRESHOLD = config['leak_explode_threshold']
        self.LEAK_COSIM_THRESHOLD = config['leak_cosim_threshold']
        self.LEAK_DIST_THRESHOLD = config['leak_dist_threshold']
        self.TRIGGER_RARE = config['trigger_rate']
        self.ACCESS_RATE = config['access_rate']
        self.train_single = eval(config['train_single'])
        self.train_align = eval(config['train_align'])
        self.coverage = Coverage()

    def generate(self):
        self.update_sub_repo('gen')
        repo_path = os.path.join(self.output_path, 'gen')
        if not os.path.exists(repo_path):
            os.mkdir(repo_path)

        self.trans.build_frame()
        seed = TriggerSeed(self.coverage)
        config = seed.mutate({}, True)
        seed = AccessSeed(self.coverage)
        config = seed.mutate(config, True)
        random.seed(config['trigger_seed'])
        self.trans.trans_victim.gen_block(config, EncodeType.FUZZ_DEFAULT, None)
        self.trans._generate_body_block(self.trans.trans_victim)
        self.trans.trans_protect.gen_block(config, None)
        self.trans._generate_body_block(self.trans.trans_protect)
        self.trans.trans_adjust.gen_block(config, self.trans.trans_victim, None)
        self.trans._generate_body_block(self.trans.trans_adjust)
        self.trans.gen_train_swap_list(config, True, True)

        seed = AccessSeed(self.coverage)
        config = seed.mutate(config, True)
        self.trans.trans_victim.mutate_access(config)
        self.trans._generate_body_block(self.trans.trans_victim)
        self.trans.trans_adjust.mutate_access(config, self.trans.trans_victim)
        self.trans._generate_body_block(self.trans.trans_adjust)

        seed = LeakSeed(self.coverage)
        config = seed.mutate(config, True)
        self.trans.trans_victim.mutate_encode(config)
        self.trans._generate_body_block(self.trans.trans_victim)
        self.trans.trans_adjust.mutate_encode(config, self.trans.trans_victim)
        self.trans._generate_body_block(self.trans.trans_adjust)
        
        self.mem_cfg.add_swap_list(self.trans.swap_block_list)
        self.mem_cfg.dump_conf('duo')

        print(config)
    
    def stage_simulate(self, mode, label="swap_mem.cfg", target="duo"):
        self.mem_cfg.dump_conf(target)

        assert mode in ['normal', 'robprofile', 'variant']
        baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.rtl_sim, file_name=f"{label}_rtl_sim.sh"
        )
        export_cmd = ShellCommand("export", [])
        gen_asm = ShellCommand("make", [f'{self.rtl_sim_mode}'])
        baker.add_cmd(export_cmd.gen_cmd([f'SIM_MODE={mode}']))
        baker.add_cmd(export_cmd.gen_cmd([f'STARSHIP_TESTCASE={self.output_path}/{self.sub_repo}/swap_mem.cfg']))
        baker.add_cmd(export_cmd.gen_cmd([f'SIMULATION_LABEL={label}']))
        baker.add_cmd(gen_asm.gen_cmd())

        return f'{self.taint_log}_{mode}/wave/{label}', baker
    
    def trigger_analysis(self, taint_folder):
        texe_enq_num = 0
        texe_deq_num = 0
        for line in open(f'{taint_folder}.taint.log', 'rt'):
            _, exec_info, _, _ = list(map(str.strip ,line.strip().split(',')))
            if exec_info == "TEXE_START_ENQ":
                texe_enq_num += 1
            if exec_info == "TEXE_START_DEQ":
                texe_deq_num += 1
                
        if texe_enq_num > texe_deq_num:
            is_trigger = True
        else:
            is_trigger = False

        return is_trigger

    def _trigger_reduce(self, is_trigger):
        if is_trigger:
            swap_block_list = self.trans.swap_block_list
            for _ in range(len(swap_block_list)-4):
                for i in range(0, len(swap_block_list)-4):
                    tmp_swap_block_list = copy.copy(swap_block_list)
                    tmp_swap_block_list.pop(i)
                    self.mem_cfg.add_swap_list(tmp_swap_block_list)
                    taint_folder, barker = self.stage_simulate('robprofile', f'{self.prefix_domain}_trigger', 'dut')
                    barker.run()
                    is_trigger = self.trigger_analysis(taint_folder)
                    if is_trigger:
                        swap_block_list = tmp_swap_block_list
                        break
                else:
                    break
            reduce_list = [swap_mem['swap_id'] for swap_mem in self.trans.swap_block_list if swap_mem not in swap_block_list]
            self.trans.swap_block_list = swap_block_list
            self.mem_cfg.add_swap_list(swap_block_list)
            
            self.mem_cfg.add_mem_region('data_train', [])
            if len(swap_block_list) > 4:
                swap_region = swap_block_list[0]
                for iter_swap_region in swap_block_list:
                    if iter_swap_region['swap_id'] > swap_region['swap_id']:
                        swap_region = iter_swap_region
                self.mem_cfg.add_mem_region('data_train', [swap_region])
            
            reduce_baker = BuildManager(
                {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.repo_path, file_name=f"reduce_trigger.sh"
            )
            rm_asm = ShellCommand("rm", [])
            for idx in reduce_list:
                reduce_baker.add_cmd(rm_asm.gen_cmd([f'{self.output_path}/{self.sub_repo}/*{idx}*']))
            reduce_baker.run()
        else:
            if len(self.trans.swap_block_list) > 4:
                reduce_baker = BuildManager(
                    {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.repo_path, file_name=f"reduce_trigger.sh"
                )
                rm_asm = ShellCommand("rm", [])
                for swap_mem in self.trans.swap_block_list:
                    idx = swap_mem['swap_id']
                    if 0 <= idx < 4:
                        continue
                    reduce_baker.add_cmd(rm_asm.gen_cmd([f'{self.output_path}/{self.sub_repo}/*{idx}*']))
                reduce_baker.run()

    
    def get_repo(self, stage_name, thread_num=0):
        iter_num_file = os.path.join(self.repo_path, f"{stage_name}_iter_num")
        if not os.path.exists(iter_num_file):
            iter_num = 0 + thread_num
        else:
            with open(iter_num_file, "rt") as file:
                iter_num = 1 + thread_num + int(file.readline().strip())

        sub_repo = f'{stage_name}_{iter_num}'
        self.update_sub_repo(sub_repo)
        repo = os.path.join(self.output_path, sub_repo)
        if not os.path.exists(repo):
            os.makedirs(repo)

        return iter_num, sub_repo
    
    def fuzz_trigger(self, config):
        trigger_iter_num, trigger_repo = self.get_repo('trigger')

        random.seed(config['trigger_seed'])
        self.trans.trans_victim.gen_block(config, EncodeType.FUZZ_DEFAULT, None)
        self.trans._generate_body_block(self.trans.trans_victim)
        self.trans.trans_protect.gen_block(config, None)
        self.trans._generate_body_block(self.trans.trans_protect)
        self.trans.trans_adjust.gen_block(config, self.trans.trans_victim, None)
        self.trans._generate_body_block(self.trans.trans_adjust)

        TRAIN_GEN_MAX_ITER = 4

        max_train_gen = TRAIN_GEN_MAX_ITER
        trigger_result = FuzzResult.FAIL
        for _ in range(max_train_gen):
            self.trans.gen_train_swap_list(config, self.train_align, self.train_single)
            self.mem_cfg.add_swap_list(self.trans.swap_block_list)
            taint_folder, barker = self.stage_simulate('robprofile', f'{self.prefix_domain}_trigger', 'dut')
            barker.run()
            is_trigger = self.trigger_analysis(taint_folder)
            self._trigger_reduce(is_trigger)
            if is_trigger:
                trigger_result = FuzzResult.SUCCESS
                break

        self.record_fuzz(trigger_iter_num, trigger_result, None, None, config, 'trigger', taint_folder = taint_folder)
        if trigger_result == FuzzResult.SUCCESS:
            self.store_template(trigger_iter_num, self.repo_path, 'trigger')

        return trigger_result

    def access_analysis(self, taint_folder):
        with open(f'{taint_folder}.taint.csv', "r") as file:
            taint_log = csv.reader(file)
            _ = next(taint_log)
            time_list = []
            base_list = []
            variant_list = []
            for time, base, variant in taint_log:
                time_list.append(int(time))
                base_list.append(int(base))
                variant_list.append(int(variant))

        dut_sync_time = 0
        dut_window_begin = 0
        dut_vicitm_end = 0
        for line in open(f'{taint_folder}.taint.log', 'rt'):
            exec_time, exec_info, _, is_dut = list(map(str.strip ,line.strip().split(',')))
            exec_time = int(exec_time)
            is_dut = True if int(is_dut) == 1 else False
            if exec_info == 'DELAY_END_ENQ' and dut_window_begin == 0 and is_dut:
                dut_window_begin = exec_time + 1 
            if exec_info == 'DELAY_END_DEQ' and dut_sync_time == 0 and is_dut:
                dut_sync_time = exec_time + 1
            if exec_info == 'VCTM_END_DEQ' and dut_sync_time != 0 and dut_vicitm_end == 0 and is_dut:
                dut_vicitm_end = exec_time
        
        is_access = False
        base_window_list = base_list[dut_window_begin:dut_vicitm_end]
        for i in range(len(base_window_list)-1):
            if base_window_list[i+1] > base_window_list[i]:
                is_access = True
                break
        max_taint = max(base_window_list)

        coverage = self.compute_coverage(taint_folder)
        comp_taint = self.compute_comp(taint_folder)

        return is_access, max_taint, coverage, comp_taint
    
    def fuzz_access(self, config):
        access_iter_num, access_repo = self.get_repo('access')

        self.trans.trans_victim.mutate_access(config)
        self.trans._generate_body_block(self.trans.trans_victim)
        self.trans.trans_adjust.mutate_access(config, self.trans.trans_victim)
        self.trans._generate_body_block(self.trans.trans_adjust)
        self.trans.swap_block_list[-2] = self.trans.trans_victim.mem_region
        self.trans.swap_block_list[-4] = self.trans.trans_adjust.mem_region
        self.mem_cfg.add_swap_list(self.trans.swap_block_list)
        taint_folder, barker = self.stage_simulate('variant', f'{self.prefix_domain}_access', 'duo')
        barker.run()
        is_access, max_taint, coverage, comp_taint = self.access_analysis(taint_folder)
        access_result = FuzzResult.SUCCESS if is_access else FuzzResult.FAIL

        self.record_fuzz(access_iter_num, access_result, None, max_taint, config, 'access', taint_folder)
        if access_result == FuzzResult.SUCCESS:
            self.store_template(access_iter_num, self.repo_path, 'access')
        
        return access_result, coverage, access_iter_num, comp_taint
    
    def store_template(self, iter_num, repo_path, stage_name):
        folder = f'{stage_name}_template'
        template_repo_path = os.path.join(repo_path, folder)
        if not os.path.exists(template_repo_path):
            os.mkdir(template_repo_path)

        template_repo_path = os.path.join(repo_path, folder, str(iter_num))
        target_repo_path = os.path.join(self.output_path, self.sub_repo)
        os.system(f'ln -s {target_repo_path} {template_repo_path}')

    def record_fuzz(self, iter_num, result, cosim_result, max_taint, config, stage_name, taint_folder):
        with open(os.path.join(self.repo_path, f'{stage_name}_iter_record'), "at") as file:
            file.write(f'iter_num:\t{iter_num}\n')
            file.write(f'result:\t{result}\n')
            if cosim_result is not None:
                file.write(f'cosim:\t{cosim_result}\n')
            if max_taint is not None:
                file.write(f'max_taint:\t{max_taint}\n')
            for i,(key, value) in enumerate(config.items()):
                file.write(f'\t{key}: {value}')
                if i%2 == 0:
                    file.write('\n')
                else:
                    file.write('\t')
            # self.trans.record_fuzz(file)
            file.write('\n')
        
        with open(os.path.join(self.repo_path, f"{stage_name}_iter_num"), "wt") as file:
            file.write(f'{iter_num}\n')
        
        cp_baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.repo_path, file_name=f"store_taint_log.sh"
        )
        gen_asm = ShellCommand("cp", [])
        suffix_taint = ['.taint.log', '.taint.csv', '.taint.live', '.taint.cov']
        for suffix in suffix_taint:
            file_name = f'{taint_folder}{suffix}'
            if os.path.exists(file_name):
                cp_baker.add_cmd(gen_asm.gen_cmd([file_name, f'{self.output_path}/{self.sub_repo}']))
        
        rm_asm = ShellCommand("rm", [])
        cp_baker.add_cmd(rm_asm.gen_cmd([f'{self.output_path}/{self.sub_repo}/*.elf']))
        cp_baker.add_cmd(rm_asm.gen_cmd([f'{self.output_path}/{self.sub_repo}/*.symbol']))
        cp_baker.add_cmd(rm_asm.gen_cmd([f'{self.output_path}/{self.sub_repo}/Testbench*.bin']))
        cp_baker.run()
    
    def taint_analysis(self, base_spread_list, variant_spread_list):
        base_array = np.array(base_spread_list, dtype=float)
        base_array = base_array[1:] - base_array[0:-1]
        base_array /= len(base_spread_list)
        variant_array = np.array(variant_spread_list, dtype=float)
        variant_array = variant_array[1:] - variant_array[0:-1]
        variant_array /= len(variant_spread_list)

        norm = np.linalg.norm(base_array) * np.linalg.norm(variant_array)
        cosine = base_array.dot(variant_array)
        cosim_result = norm - cosine
        max_taint = max(max(base_spread_list), max(variant_spread_list))

        base_array = np.array(base_spread_list, dtype=float)
        variant_array = np.array(variant_spread_list, dtype=float)
        ave_dist = abs(np.average(base_array - variant_array))

        return cosim_result, ave_dist, max_taint

    def compute_coverage(self, taint_folder):
        coverage = set()
        for line in open(f'{taint_folder}.taint.cov', "r"):
            line = line.strip()
            line = list(line.split())
            comp = line[0][:-1]
            hash_value = line[1:]
            for value in hash_value:
                value = int(value, base=16)
                coverage.add((comp, value))
        return coverage
    
    def compute_comp(self, taint_folder):
        taint_comp = TaintComp()
        for line in open(f'{taint_folder}.taint.live', "r"):
            line = line.strip()
            if ':' in line:
                line = list(line.split())
                comp = line[0][:-1]
                hash_value = int(line[1])
                taint_comp[comp] = hash_value
            else:
                comp = line[:-1]
                taint_comp[comp] = 1
        return taint_comp

    def leak_analysis(self, access_comp_taint, taint_folder, strategy):
        with open(f'{taint_folder}.taint.csv', "r") as file:
            taint_log = csv.reader(file)
            _ = next(taint_log)
            time_list = []
            base_list = []
            variant_list = []
            for time, base, variant in taint_log:
                time_list.append(int(time))
                base_list.append(int(base))
                variant_list.append(int(variant))
        
        dut_sync_time = 0
        dut_window_begin = 0
        dut_vicitm_end = 0
        vnt_sync_time = 0
        vnt_window_begin = 0
        vnt_vicitm_end = 0
        dut_texe_begin = 0
        dut_texe_enq_num = 0
        dut_texe_deq_num = 0
        is_trigger = False
        for line in open(f'{taint_folder}.taint.log', 'rt'):
            exec_time, exec_info, _, is_dut = list(map(str.strip ,line.strip().split(',')))
            exec_time = int(exec_time)
            is_dut = True if int(is_dut) == 1 else False
            if exec_info == 'DELAY_END_ENQ' and dut_window_begin == 0 and is_dut:
                dut_window_begin = exec_time + 1 
            if exec_info == 'DELAY_END_DEQ' and dut_sync_time == 0 and is_dut:
                dut_sync_time = exec_time + 1
            if exec_info == 'VCTM_END_DEQ' and dut_sync_time != 0 and dut_vicitm_end == 0 and is_dut:
                dut_vicitm_end = exec_time

            if exec_info == 'DELAY_END_ENQ' and vnt_window_begin == 0 and not is_dut:
                vnt_window_begin = exec_time + 1 
            if exec_info == 'DELAY_END_DEQ' and vnt_sync_time == 0 and not is_dut:
                vnt_sync_time = exec_time + 1
            if exec_info == 'VCTM_END_DEQ' and vnt_sync_time != 0 and vnt_vicitm_end == 0 and not is_dut:
                vnt_vicitm_end = exec_time

            if exec_info == "TEXE_START_ENQ" and dut_texe_begin == 0 and is_dut:
                dut_texe_begin = exec_time
            if exec_info == "TEXE_START_ENQ" and is_dut:
                dut_texe_enq_num += 1
            if exec_info == "TEXE_START_DEQ" and is_dut:
                dut_texe_deq_num += 1
        
        is_trigger = dut_texe_enq_num > dut_texe_deq_num
        is_divergent = dut_vicitm_end != vnt_vicitm_end

        if not is_trigger:
            return FuzzResult.FAIL, None, None, [('',0)]

        coverage = self.compute_coverage(taint_folder)
        leak_comp_taint = self.compute_comp(taint_folder)

        base_spread_list = base_list[dut_sync_time:dut_vicitm_end]
        variant_spread_list = variant_list[dut_sync_time:dut_vicitm_end]
        cosim_result, ave_dist, max_taint = self.taint_analysis(base_spread_list, variant_spread_list)

        leak_result = FuzzResult.FAIL
        if strategy in [EncodeType.FUZZ_PIPELINE] and is_divergent:
            leak_result = FuzzResult.SUCCESS
        elif self.taint_leak_more(access_comp_taint, leak_comp_taint):
            leak_result = FuzzResult.SUCCESS
        
        return leak_result, cosim_result, max_taint, coverage
    
    def taint_leak_more(self, access_comp_taint, leak_comp_taint):
        result = False
        for leak_comp, leak_value in leak_comp_taint.comp_map.items():
            access_value = access_comp_taint.comp_map.get(leak_comp, 0)
            if leak_value > access_value:
                result = True
                break
        return result

    def fuzz_leak(self, access_comp_taint, config_list):
        def barker_func(barker):
            barker.run()

        leak_iter_num_list = []
        leak_repo_list = []
        taint_folder_list = []
        barker_list = []
        thread_list = []
        for i, config in enumerate(config_list):
            leak_iter_num, leak_repo = self.get_repo('leak', i)
            self.trans.trans_victim.mutate_encode(config)
            self.trans._generate_body_block(self.trans.trans_victim)
            self.trans.trans_adjust.mutate_encode(config, self.trans.trans_victim)
            self.trans._generate_body_block(self.trans.trans_adjust)
            self.trans.swap_block_list[-2] = self.trans.trans_victim.mem_region
            self.trans.swap_block_list[-4] = self.trans.trans_adjust.mem_region
            self.mem_cfg.add_swap_list(self.trans.swap_block_list)
            taint_folder, barker = self.stage_simulate('variant', f'{self.prefix_domain}_leak_thread_{i}', 'duo')

            leak_iter_num_list.append(leak_iter_num)
            leak_repo_list.append(leak_repo)
            taint_folder_list.append(taint_folder)
            barker_list.append(barker)

            thread = threading.Thread(target=barker_func, args=[barker])
            thread.start()
            thread_list.append(thread)

        for thread in thread_list:
            thread.join()
        
        coverage_list = []

        for i, leak_iter_num, leak_repo, taint_folder, config in\
            zip(range(len(leak_iter_num_list)), leak_iter_num_list, leak_repo_list, taint_folder_list, config_list):
            self.update_sub_repo(leak_repo)
            leak_result, cosim_result, max_taint, coverage = self.leak_analysis(access_comp_taint, taint_folder, config['encode_fuzz_type'])
            coverage_list.append(coverage)
            self.record_fuzz(leak_iter_num, leak_result, cosim_result, max_taint, config, 'leak', taint_folder)
            if leak_result == FuzzResult.SUCCESS:
                self.store_template(leak_iter_num, self.repo_path, 'leak')

        return coverage_list, leak_iter_num_list
    
    def update_sub_repo(self, sub_repo):
        self.sub_repo = sub_repo
        self.mem_cfg.update_sub_repo(sub_repo)
        self.trans.update_sub_repo(sub_repo)
    
    def fuzz(self, rtl_sim, rtl_sim_mode, taint_log, repo_path, thread_num):
        self.fuzz_log = FuzzLog(repo_path)
        self.thread_num = thread_num

        if repo_path is None:
            self.repo_path = self.output_path
        else:
            self.repo_path = repo_path
        if not os.path.exists(self.repo_path):
            os.makedirs(self.repo_path)
        self.rtl_sim = rtl_sim
        assert rtl_sim_mode in ['vcs', 'vlt'], "the rtl_sim_mode must be in vcs and vlt"
        self.rtl_sim_mode = rtl_sim_mode
        self.taint_log = taint_log

        class FuzzFSM(Enum):
            IDLE = auto()
            MUTATE_TRIGGER = auto()
            MUTATE_ACCESS = auto()
            ACCUMULATE = auto()
            MUTATE_LEAK = auto()
            STOP = auto()

        last_state = FuzzFSM.IDLE
        state = FuzzFSM.IDLE

        trigger_seed = TriggerSeed(self.coverage)
        access_seed = AccessSeed(self.coverage)
        leak_seed_list = [LeakSeed(self.coverage) for _ in range(self.thread_num)]
        config = {}

        MAX_TRIGGER_MUTATE_ITER = 10
        MAX_ACCESS_MUTATE_ITER = 5
        LEAK_ACCUMULATE_ITER = (10 + self.thread_num - 1) // self.thread_num

        while True:
            iter_num = 0
            last_state = state
            match(state):
                case FuzzFSM.IDLE:
                    self.update_sub_repo('frame')
                    path = os.path.join(self.output_path, 'frame')
                    if not os.path.exists(path):
                        os.mkdir(path)
                    self.trans.build_frame()

                    trigger_seed = TriggerSeed(self.coverage)
                    config = trigger_seed.mutate({}, True)
                    access_seed = AccessSeed(self.coverage)
                    config = access_seed.mutate(config, True)
                    state = FuzzFSM.MUTATE_TRIGGER
                case FuzzFSM.MUTATE_TRIGGER:
                    for iter_num in range(MAX_TRIGGER_MUTATE_ITER):
                        trigger_result = self.fuzz_trigger(config)
                        if trigger_result == FuzzResult.SUCCESS:
                            state = FuzzFSM.MUTATE_ACCESS
                            break
                        else:
                            config = trigger_seed.mutate({})
                            config = access_seed.parse(config)
                    else:
                        config = trigger_seed.mutate({}, True)
                        config = access_seed.mutate(config, True)
                case FuzzFSM.MUTATE_ACCESS:
                    for iter_num in range(MAX_ACCESS_MUTATE_ITER):
                        access_result, coverage, access_iter_num, access_comp_taint = self.fuzz_access(config)
                        cov_inc = self.coverage.update_coverage(coverage, is_leak=False)
                        self.fuzz_log.log_cover(access_iter_num, cov_inc)
                        if access_result == FuzzResult.SUCCESS:
                            state = FuzzFSM.ACCUMULATE
                            break
                        else:
                            config = access_seed.mutate(config)
                    else:
                        config = trigger_seed.mutate({})
                        config = access_seed.mutate(config)
                        state = FuzzFSM.MUTATE_TRIGGER
                case FuzzFSM.ACCUMULATE:
                    self.coverage.accumulate()

                    config_list = []
                    for leak_seed in leak_seed_list:
                        config = leak_seed.mutate(config, True)
                        config_list.append(config)

                    for iter_num in range(LEAK_ACCUMULATE_ITER):
                        coverage_list, leak_iter_num_list =\
                            self.fuzz_leak(access_comp_taint, config_list)
                        
                        for leak_seed, coverage, leak_iter_num in \
                            zip(leak_seed_list, coverage_list, leak_iter_num_list):
                            cov_inc = leak_seed.update_coverage(coverage)
                            self.fuzz_log.log_cover(leak_iter_num, cov_inc)

                        new_config_list = []
                        for leak_seed, config in zip(leak_seed_list, config_list):
                            config = leak_seed.mutate(config, True)
                            new_config_list.append(config)
                        config_list = new_config_list

                    state = FuzzFSM.MUTATE_LEAK
                case FuzzFSM.MUTATE_LEAK:
                    while True:
                        coverage_list, leak_iter_num_list =\
                            self.fuzz_leak(access_comp_taint, config_list)
                        
                        for leak_seed, coverage, leak_iter_num in \
                            zip(leak_seed_list, coverage_list, leak_iter_num_list):
                            cov_inc = leak_seed.update_coverage(coverage)
                            self.fuzz_log.log_cover(leak_iter_num, cov_inc)
                        cover_contr = self.coverage.evalute_coverage()

                        iter_num += 1
                        if cover_contr < self.TRIGGER_RARE:
                            config = trigger_seed.mutate({}, True)
                            config = access_seed.mutate(config, True)
                            state = FuzzFSM.MUTATE_TRIGGER
                            break
                        elif cover_contr < self.ACCESS_RATE:
                            config = access_seed.mutate(config, True)
                            state = FuzzFSM.MUTATE_ACCESS
                            break
                        else:
                            new_config_list = []
                            for leak_seed, config in zip(leak_seed_list, config_list):
                                config = leak_seed.mutate(config, True)
                                new_config_list.append(config)
                            config_list = new_config_list
                case FuzzFSM.STOP:
                    break
            self.fuzz_log.log_state(last_state, state, iter_num)

                        




