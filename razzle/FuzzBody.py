from TransManager import *
from FuzzUtils import *

class FuzzBody:
    def __init__(self, fuzz_config, output_path, prefix, core):
        self.output_path = output_path
        self.prefix_domain = prefix
        self.core = core
        
        self.train_single = eval(fuzz_config['train_single'])
        self.train_align = eval(fuzz_config['train_align'])
        self.mem_cfg = MemCfg(int(fuzz_config['mem_start'], base=16), int(fuzz_config['mem_size'], base=16), self.output_path)
        self.trans = TransManager(fuzz_config, self.output_path, self.mem_cfg)
        
        self.config = None
        self.trigger_iter_num = None
        self.trigger_result = None
        self.trigger_taint_folder = None

        self.access_iter_num = None
        self.access_result = None
        self.access_taint_folder = None
        self.access_max_taint = None
        self.access_cosim_result = None
        self.access_coverage = None
        self.access_comp_taint = None

        self.leak_iter_num = None
        self.leak_result = None
        self.leak_taint_folder = None
        self.leak_max_taint = None
        self.leak_cosim_result = None
        self.leak_coverage = None
        self.leak_comp_taint = None
        self.is_divergent = None

        self.post_coverage = None
        self.post_comp_taint = None
        
        self.rtl_sim = None
        self.rtl_sim_mode = None
        self.taint_log = None
    
    def set_sim_param(self, rtl_sim, rtl_sim_mode, taint_log):
        self.rtl_sim = rtl_sim
        self.rtl_sim_mode = rtl_sim_mode
        self.taint_log = taint_log

    def generate(self, config):
        self.config = config
        random.seed(self.config['trigger_seed'])
        self.trans.trans_victim.gen_block(self.config, EncodeType.FUZZ_DEFAULT)
        self.trans._generate_body_block(self.trans.trans_victim)
        self.trans.trans_protect.gen_block(self.config)
        self.trans._generate_body_block(self.trans.trans_protect)
        self.trans.trans_adjust.gen_block(self.config, self.trans.trans_victim)
        self.trans._generate_body_block(self.trans.trans_adjust)
        self.trans.gen_train_swap_list(self.config, True, True)

        self.trans.trans_victim.mutate_access(self.config)
        self.trans._generate_body_block(self.trans.trans_victim)
        self.trans.trans_adjust.mutate_access(self.config, self.trans.trans_victim)
        self.trans._generate_body_block(self.trans.trans_adjust)

        self.trans.trans_victim.mutate_encode(self.config)
        self.trans._generate_body_block(self.trans.trans_victim)
        self.trans.trans_adjust.mutate_encode(self.config, self.trans.trans_victim)
        self.trans._generate_body_block(self.trans.trans_adjust)
        
        self.mem_cfg.add_swap_list(self.trans.swap_block_list)
        self.mem_cfg.dump_conf('duo')
    
    def offline_compile(self, mem_cfg):
        mem_region_list = mem_cfg['memory_regions']
        for mem_region in mem_region_list[-1::-1]:
            init_file = mem_region['init_file']
            sub_repo = init_file.split('/')[-2]
            if mem_region['type'] != 'swap':
                continue
            self.update_sub_repo(sub_repo)
            self.trans._generate_body_block(None, mem_region)
    
    def update_sub_repo(self, sub_repo):
        self.sub_repo = sub_repo
        self.mem_cfg.update_sub_repo(sub_repo)
        self.trans.update_sub_repo(sub_repo)
        repo_path = os.path.join(self.output_path, sub_repo)
        if not os.path.exists(repo_path):
            os.mkdir(repo_path)
    
    def stage_simulate(self, mode, label="swap_mem", target="duo"):
        self.mem_cfg.dump_conf(target)

        assert mode in ['normal', 'robprofile', 'variant']
        baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.rtl_sim, file_name=f"{label}_rtl_sim.sh"
        )
        export_cmd = ShellCommand("export", [])
        gen_asm = ShellCommand("make", [f'{self.rtl_sim_mode}'])
        baker.add_cmd(export_cmd.gen_cmd([f'SIM_MODE={mode}']))
        baker.add_cmd(export_cmd.gen_cmd([f'TARGET_CORE={self.core}']))
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
                {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.rtl_sim, file_name=f"{self.prefix_domain}_reduce_trigger.sh"
            )
            rm_asm = ShellCommand("rm", [])
            idx_set = set()
            for idx in reduce_list:
                if idx not in idx_set:
                    idx_set.add(idx)
                    reduce_baker.add_cmd(rm_asm.gen_cmd([f'{self.output_path}/{self.sub_repo}/*{idx}*']))
            reduce_baker.run()
        else:
            if len(self.trans.swap_block_list) > 4:
                reduce_baker = BuildManager(
                    {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.rtl_sim, file_name=f"{self.prefix_domain}_reduce_trigger.sh"
                )
                rm_asm = ShellCommand("rm", [])
                idx_set = set()
                for swap_mem in self.trans.swap_block_list:
                    idx = swap_mem['swap_id']
                    if 0 <= idx < 4:
                        continue
                    if idx not in idx_set:
                        idx_set.add(idx)
                        reduce_baker.add_cmd(rm_asm.gen_cmd([f'{self.output_path}/{self.sub_repo}/*{idx}*']))
                reduce_baker.run()
    
    def fuzz_trigger(self, config):
        self.config = config

        random.seed(config['trigger_seed'])
        self.trans.trans_victim.gen_block(config, EncodeType.FUZZ_DEFAULT)
        self.trans._generate_body_block(self.trans.trans_victim)
        self.trans.trans_protect.gen_block(config)
        self.trans._generate_body_block(self.trans.trans_protect)
        self.trans.trans_adjust.gen_block(config, self.trans.trans_victim)
        self.trans._generate_body_block(self.trans.trans_adjust)

        TRAIN_GEN_MAX_ITER = 4

        max_train_gen = TRAIN_GEN_MAX_ITER
        self.trigger_result = FuzzResult.FAIL
        for _ in range(max_train_gen):
            self.trans.gen_train_swap_list(config, self.train_align, self.train_single)
            self.mem_cfg.add_swap_list(self.trans.swap_block_list)
            self.trigger_taint_folder, barker = self.stage_simulate('robprofile', f'{self.prefix_domain}_trigger', 'dut')
            barker.run()
            is_trigger = self.trigger_analysis(self.trigger_taint_folder)
            self._trigger_reduce(is_trigger)
            if is_trigger:
                self.trigger_result = FuzzResult.SUCCESS
                break
    
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
        coverage = []
        for line in open(f'{taint_folder}.taint.cov', "r"):
            line = line.strip()
            line = list(line.split())
            comp = line[0][:-1]
            if 'l2' in comp:
                continue
            # if 'regfile' in comp:
            #     continue
            # if 'rob' in comp:
            #     continue
            hash_value = line[1:]
            for value in hash_value:
                value = int(value, base=16)
                coverage.append((comp, value))
        return coverage
    
    def compute_comp(self, taint_folder):
        taint_comp = TaintComp()
        for line in open(f'{taint_folder}.taint.live', "r"):
            line = line.strip()
            if ':' in line:
                line = list(line.split())
                comp = line[0][:-1]
                if 'l2' in comp:
                    continue
                hash_value = int(line[1])
                taint_comp[comp] = hash_value
            else:
                comp = line[:-1]
                if 'l2' in comp:
                    continue
                taint_comp[comp] = 1
        return taint_comp

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

        dut_window_begin = 0
        dut_window_end = 0
        for line in open(f'{taint_folder}.taint.log', 'rt'):
            exec_time, exec_info, _, is_dut = list(map(str.strip ,line.strip().split(',')))
            exec_time = int(exec_time)
            is_dut = True if int(is_dut) == 1 else False
            if exec_info == 'DELAY_END_ENQ' and is_dut:
                dut_window_begin = exec_time + 1 
            if exec_info in ['VCTM_END_DEQ', 'TEXE_START_DEQ'] and is_dut:
                dut_window_end = exec_time
        
        is_access = False
        base_window_list = base_list[dut_window_begin:dut_window_end]
        for i in range(len(base_window_list)-1):
            if base_window_list[i+1] > base_window_list[i]:
                is_access = True
                break
        self.access_max_taint = max(base_window_list)

        self.access_coverage = self.compute_coverage(taint_folder)
        self.access_comp_taint = self.compute_comp(taint_folder)

        return is_access
    
    def fuzz_access(self, config):
        self.config = config

        self.trans.trans_victim.mutate_access(config)
        self.trans._generate_body_block(self.trans.trans_victim)
        self.trans.trans_adjust.mutate_access(config, self.trans.trans_victim)
        self.trans._generate_body_block(self.trans.trans_adjust)
        self.trans.swap_block_list[-2] = self.trans.trans_victim.mem_region
        self.trans.swap_block_list[-4] = self.trans.trans_adjust.mem_region
        self.mem_cfg.add_swap_list(self.trans.swap_block_list)
        self.access_taint_folder, barker = self.stage_simulate('variant', f'{self.prefix_domain}_access', 'duo')
        barker.run()
        is_access = self.access_analysis(self.access_taint_folder)
        self.access_result = FuzzResult.SUCCESS if is_access else FuzzResult.FAIL

    def taint_leak_more(self, access_comp_taint, leak_comp_taint):
        result = False
        for leak_comp, leak_value in leak_comp_taint.comp_map.items():
            access_value = access_comp_taint.comp_map.get(leak_comp, 0)
            if leak_value > access_value:
                result = True
                break
        return result

    def leak_analysis(self, taint_folder):
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
        dut_window_end = 0
        vnt_window_end = 0
        dut_texe_enq_num = 0
        dut_texe_deq_num = 0
        is_trigger = False
        for line in open(f'{taint_folder}.taint.log', 'rt'):
            exec_time, exec_info, _, is_dut = list(map(str.strip ,line.strip().split(',')))
            exec_time = int(exec_time)
            is_dut = True if int(is_dut) == 1 else False
            if exec_info == 'DELAY_END_DEQ' and is_dut:
                dut_sync_time = exec_time + 1
            if exec_info in ['VCTM_END_ENQ', 'TEXE_START_ENQ'] and is_dut:
                dut_window_end = exec_time

            if exec_info in ['VCTM_END_ENQ', 'TEXE_START_ENQ'] and not is_dut:
                vnt_window_end = exec_time

            if exec_info == "TEXE_START_ENQ" and is_dut:
                dut_texe_enq_num += 1
            if exec_info == "TEXE_START_DEQ" and is_dut:
                dut_texe_deq_num += 1
        
        is_trigger = dut_texe_enq_num > dut_texe_deq_num
        is_divergent = dut_window_end != vnt_window_end

        leak_result = FuzzResult.FAIL
        self.is_divergent = False
        self.leak_coverage = [('',0)]
        self.leak_comp_taint = TaintComp()
        self.leak_cosim_result = None
        self.leak_max_taint = None

        if is_trigger:
            self.leak_coverage = self.compute_coverage(taint_folder)
            self.leak_comp_taint = self.compute_comp(taint_folder)

            base_spread_list = base_list[dut_sync_time:dut_window_end]
            variant_spread_list = variant_list[dut_sync_time:dut_window_end]
            self.leak_cosim_result, ave_dist, self.leak_max_taint = self.taint_analysis(base_spread_list, variant_spread_list)

            if is_divergent:
                leak_result = FuzzResult.SUCCESS
                self.is_divergent = True
            elif self.taint_leak_more(self.access_comp_taint, self.leak_comp_taint):
                leak_result = FuzzResult.MAYBE
        
        return leak_result
    
    def post_analysis(self, taint_folder):
        self.post_coverage = self.compute_coverage(taint_folder)
        self.post_comp_taint = self.compute_comp(taint_folder)
        if self.taint_leak_more(self.post_comp_taint, self.leak_comp_taint):
            return FuzzResult.SUCCESS
        else:
            return FuzzResult.FAIL
    
    def gen_leak(self, config):
        self.config = config

        self.trans.trans_victim.mutate_encode(config)
        self.trans._generate_body_block(self.trans.trans_victim)
        self.trans.trans_adjust.mutate_encode(config, self.trans.trans_victim)
        self.trans._generate_body_block(self.trans.trans_adjust)
        self.trans.swap_block_list[-2] = self.trans.trans_victim.mem_region
        self.trans.swap_block_list[-4] = self.trans.trans_adjust.mem_region
        self.mem_cfg.add_swap_list(self.trans.swap_block_list)

    def fuzz_leak(self, thread_i):
        self.leak_taint_folder, barker = self.stage_simulate('variant', f'{self.prefix_domain}_leak_thread_{thread_i}', 'duo')
        barker.run()
        self.leak_result = self.leak_analysis(self.leak_taint_folder)

        if self.leak_result != FuzzResult.MAYBE:
            return
        
        old_sub_repo = self.sub_repo
        sub_repo = self.sub_repo.replace('leak', 'post')
        self.update_sub_repo(sub_repo)
        self.trans.trans_victim.clear_encode()
        self.trans._generate_body_block(self.trans.trans_victim)
        self.trans.swap_block_list[-2] = self.trans.trans_victim.mem_region
        self.mem_cfg.add_swap_list(self.trans.swap_block_list)
        
        self.post_taint_folder, barker = self.stage_simulate('variant', f'{self.prefix_domain}_post_thread_{thread_i}', 'duo')
        barker.run()
        self.leak_result = self.post_analysis(self.post_taint_folder)
        self.update_sub_repo(old_sub_repo)
    
    def record_fuzz(self):
        record = {}
        record['trans'] = self.trans.record_fuzz()
        thread_record = record['threat'] = {}
        thread_record['victim_priv'] = self.config['victim_priv']
        thread_record['victim_addr'] = self.config['victim_addr']
        thread_record['attack_priv'] = self.config['attack_priv']
        thread_record['attack_addr'] = self.config['attack_addr']
        seed_record = record['seed'] = {}
        seed_record['trigger'] = self.config['trigger_seed']
        seed_record['access'] = self.config['access_seed']
        seed_record['leak'] = self.config.get('leak_seed', 0)

        return record
    
    
    

                        




