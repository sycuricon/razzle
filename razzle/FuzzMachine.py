from FuzzBody import *
from FuzzUtils import *
import threading
import matplotlib.pyplot as plt

class FuzzMachine:
    def __init__(self, hjson_filename, output_path, prefix, core="BOOM"):
        self.hjson_filename = hjson_filename
        self.build_path = output_path
        assert core in ['BOOM', 'XiangShan']
        self.core = core
        self.prefix_domain = f'{self.core}_{prefix}'
        self.output_path = os.path.join(self.build_path, f'{self.prefix_domain}.fuzz_code')
        self.repo_path = os.path.join(self.build_path, f'{self.prefix_domain}.template_repo')
        if not os.path.exists(self.output_path):
            os.makedirs(self.output_path)
        if not os.path.exists(self.repo_path):
            os.makedirs(self.repo_path)

        hjson_file = open(hjson_filename)
        fuzz_config = hjson.load(hjson_file)
        self.TRIGGER_RARE = fuzz_config['trigger_rate']
        self.ACCESS_RATE = fuzz_config['access_rate']
        
        self.origin_fuzz_body = FuzzBody(fuzz_config, self.output_path, self.prefix_domain, self.core)
    
    def _load_stage_record(self, stage_name, thread_num):
        stage_file_name = os.path.join(self.repo_path, f'{stage_name}_iter_record')
        stage_file = open(stage_file_name, "rt")
        record_hjson = f'[{stage_file.read()}]'
        record_list = hjson.loads(record_hjson)

        record_tuple_list = []
        for record in record_list:
            record_tuple = {'config':record}
            iter_num = record['iter_num']
            if thread_num == None:
                taint_name = f'{self.prefix_domain}_{stage_name}'
            else:
                taint_name = f'{self.prefix_domain}_{stage_name}_thread_{iter_num%thread_num}'
            testcase_path = os.path.join(self.output_path, f'{stage_name}_{iter_num}', taint_name)
            if os.path.exists(f'{testcase_path}.taint.cov'):
                coverage = self.origin_fuzz_body.compute_coverage(testcase_path)
                record_tuple['coverage'] = coverage
            if os.path.exists(f'{testcase_path}.taint.live'):
                comp = self.origin_fuzz_body.compute_comp(testcase_path)
                record_tuple['comp'] = comp
            record_tuple_list.append(record_tuple)
        return record_tuple_list
    
    def _trigger_record_analysis(self, trigger_record):
        trigger_dict = {}
        for record in trigger_record:
            record = record['config']
            trigger_type = record['trans']['victim']['block_info']['trigger_block']['type']
            if len(record['trans']['train']) == 0:
                train_type = TrainType.NONE
            else:
                train_type = record['trans']['train'][0]['block_info']['train_block']['type']
            result = eval(record['result'])
            if trigger_type not in trigger_dict:
                trigger_dict[trigger_type] = {}
            trigger_type_dict = trigger_dict[trigger_type]
            if train_type not in trigger_type_dict:
                trigger_type_dict[train_type] = {'summary':0, 'success':0, 'list':[]}
            trigger_type_dict[train_type]['summary'] += 1
            if result == FuzzResult.SUCCESS:
                trigger_type_dict[train_type]['success'] += 1
                trigger_type_dict[train_type]['list'].append(int(record['iter_num']))
        
        analysis_file_name = os.path.join(self.repo_path, 'trigger_analysis_result.md')
        with open(analysis_file_name, "wt") as file:
            file.write('|trigger_type|train_type|summary|success|rate|\n')
            file.write('|----|----|----|----|-----|\n')
            for trigger_type, trigger_content in trigger_dict.items():
                for train_type, train_content in trigger_content.items():
                    summary = train_content['summary']
                    success = train_content['success']
                    test_list = train_content['list']
                    rate = success/summary
                    if success > 0:
                        file.write(f'|{trigger_type}|{train_type}|{summary}|{success}|{rate}|\n')
                        file.write(f'{test_list}\n')
                

    def _access_record_analysis(self, access_record):
        access_success = []
        access_testcase = []
        for record in access_record:
            record = record['config']
            result = eval(record['result'])
            if result == FuzzResult.FAIL:
                continue
            testcase = {}
            testcase['train_type'] = record['trans']['adjust']['block_info']['secret_migrate_block']['type']
            testcase['pmp_r'] = record['trans']['protect']['block_info']['secret_protect_block']['pmp_r']
            testcase['pmp_l'] = record['trans']['protect']['block_info']['secret_protect_block']['pmp_l']
            testcase['pte_r'] = record['trans']['protect']['block_info']['secret_protect_block']['pte_r']
            testcase['pte_v'] = record['trans']['protect']['block_info']['secret_protect_block']['pte_v']
            testcase['victim_priv'] = record['threat']['victim_priv']
            testcase['victim_addr'] = record['threat']['victim_addr']
            testcase['attack_priv'] = record['threat']['attack_priv']
            testcase['attack_addr'] = record['threat']['attack_addr']
            testcase['li_offset'] = record['trans']['victim']['block_info']['access_secret_block']['li_offset']
            testcase['addr'] = hex(record['trans']['victim']['block_info']['access_secret_block']['address'])           
            try:
                idx = access_success.index(testcase)
                access_testcase[idx].append(record['iter_num'])
            except ValueError:
                access_success.append(testcase)
                access_testcase.append([record['iter_num']])

        analysis_file_name = os.path.join(self.repo_path, 'access_analysis_result.md')
        with open(analysis_file_name, "wt") as file:
            file.write('|train_type|pmp_r|pmp_l|pte_r|pte_v|threat|li_offset|addr|\n')
            file.write('|----|----|----|----|----|----|----|----|\n')
            for testcase, testcase_idx in zip(access_success,access_testcase):
                file.write(f"|{testcase['train_type']}|{testcase['pmp_r']}|{testcase['pmp_l']}|{testcase['pte_r']}|{testcase['pte_v']}|{testcase['victim_priv']}{testcase['victim_addr']}{testcase['attack_priv']}{testcase['attack_addr']}|{testcase['li_offset']}|{testcase['addr']}|\n")
                file.write(f'{testcase_idx}\n')

    def _leak_record_analysis(self, leak_record):
        leak_success = []
        leak_index = []
        for record in leak_record:
            result = eval(record['config']['result'])
            if result == FuzzResult.FAIL or result is None:
                continue
            if 'comp' not in record:
                continue

            idx = record['config']['iter_num']
            if record['config']['is_divergent'] == True:
                comp_simple = ['divergent']
            else:
                record = record['comp']
                comp_simple = set()
                comp = record.comp_map
                for name, value in comp.items():
                    name = list(name.split('.'))
                    match self.core:
                        case 'BOOM':
                            name = '.'.join(name[5:-2])
                        case 'XiangShan':
                            name = '.'.join(name[7:-2])
                        case _:
                            raise Exception("invalid core type")
                    comp_simple.add(name)
                comp_simple = list(comp_simple)
                comp_simple.sort()
            try:
                leak_idx = leak_success.index(comp_simple)
                leak_index[leak_idx].append(idx)
            except ValueError:
                leak_success.append(comp_simple)
                leak_index.append([idx])
        
        analysis_file_name = os.path.join(self.repo_path, 'leak_analysis_result.md')
        with open(analysis_file_name, "wt") as file:
            for comp, idx in zip(leak_success, leak_index):
                file.write(f'{idx}\n{comp}\n')

    def _part_coverage_record_analysis(self, leak_record, stage_name):
        cov_contr = [0]

        coverage = Coverage()
        for record in leak_record:
            if 'coverage' not in record:
                record['coverage_contr'] = 0
                record['comp'] = TaintComp()
                cov_contr.append(cov_contr[-1])
            else:
                coverage_contr = coverage.update_coverage(record['coverage'])
                record['coverage_contr'] = coverage_contr
                cov_contr.append(cov_contr[-1] + coverage_contr)
        leak_record.sort(key=lambda x:x['coverage_contr'], reverse=True)

        analysis_file_name = os.path.join(self.repo_path, f'{stage_name}_coverage_analysis_result.md')
        with open(analysis_file_name, "wt") as file:
            file.write(f"|iter_num|coverage_contr|taint_sum|strategy|\n")
            file.write(f"|--------|--------------|---------|--------|\n")
            for record in leak_record:
                if 'config' not in record:
                    continue
                strategy = eval(record['config']['trans']['adjust']['block_info']['encode_block']['strategy'])
                file.write(f"{record['config']['iter_num']} {record['coverage_contr']} {record['comp'].taint_sum} {strategy}\n")
    
        plt.plot(cov_contr, label=stage_name)
    
    def _coverage_record_analysis(self, leak_record):
        data_leak_record = []
        ctrl_leak_record = []
        full_leak_record = []
        for record in leak_record:
            # if 'is_divergent' in record['config'] and record['config']['is_divergent'] == True:
            #     continue
            if 'coverage' not in record:
                continue
            strategy = eval(record['config']['trans']['adjust']['block_info']['encode_block']['strategy'])
            if strategy == EncodeType.FUZZ_PIPELINE:
                ctrl_leak_record.append(record)
                full_leak_record.append(record)
                data_leak_record.append({})
            elif strategy in [EncodeType.FUZZ_BACKEND, EncodeType.FUZZ_FRONTEND]:
                ctrl_leak_record.append({})
                data_leak_record.append(record)
                full_leak_record.append(record)
        
        self._part_coverage_record_analysis(full_leak_record, 'full')
        self._part_coverage_record_analysis(data_leak_record, 'data')
        self._part_coverage_record_analysis(ctrl_leak_record, 'ctrl')

        plt.legend()
        plt.savefig(os.path.join(self.repo_path, f'coverage.png'))

        coverage_contr = {}
        for record in full_leak_record:
            coverage = record['coverage']
            for comp, hash_value in coverage:
                if comp not in coverage_contr:
                    coverage_contr[comp] = {hash_value}
                else:
                    coverage_contr[comp].add(hash_value)
        with open(os.path.join(self.repo_path, f'coverage_contr.md'), 'wt') as file:
            for comp, value_list in coverage_contr.items():
                file.write(f'{comp}\n{len(value_list)}\n{value_list}\n')

    def fuzz_analysis(self, thread_num):
        thread_num = int(thread_num)
        # trigger_record = self._load_stage_record('trigger', None)
        # access_record = self._load_stage_record('access', None)
        
        leak_record = self._load_stage_record('leak', thread_num)
        self._trigger_record_analysis(leak_record)
        self._access_record_analysis(leak_record)
        self._leak_record_analysis(leak_record)
        self._coverage_record_analysis(leak_record)
    
    def offline_compile(self, mem_cfg_file_name):
        mem_cfg_file = open(mem_cfg_file_name)
        mem_cfg = libconf.load(mem_cfg_file)
        self.origin_fuzz_body.update_sub_repo('frame')
        self.origin_fuzz_body.trans.build_frame()
        self.origin_fuzz_body.offline_compile(mem_cfg)
    
    def generate(self):
        self.coverage = Coverage()
        self.trigger_seed = TriggerSeed(self.coverage)
        self.access_seed = AccessSeed(self.coverage)
        self.leak_seed = LeakSeed(self.coverage)

        self.origin_fuzz_body.update_sub_repo('frame')
        self.origin_fuzz_body.trans.build_frame()

        self.origin_fuzz_body.update_sub_repo('gen')
        config = self.trigger_seed.mutate({}, True)
        config = self.access_seed.mutate(config, True)
        config = self.leak_seed.mutate(config, True)
        self.origin_fuzz_body.generate(config)

        with open(os.path.join(self.origin_fuzz_body.output_path, self.origin_fuzz_body.sub_repo, 'config'), 'wt') as file:
            for key, value in config.items():
                file.write(f'{key}:{value}\n')
    
    def get_repo(self, stage_name, thread_num=0):
        iter_num_file = os.path.join(self.repo_path, f"{stage_name}_iter_num")
        if not os.path.exists(iter_num_file):
            iter_num = 0 + thread_num
        else:
            with open(iter_num_file, "rt") as file:
                iter_num = 1 + thread_num + int(file.readline().strip())

        sub_repo = f'{stage_name}_{iter_num}'
        repo = os.path.join(self.output_path, sub_repo)
        if not os.path.exists(repo):
            os.makedirs(repo)

        return iter_num, sub_repo
    
    def record_fuzz(self, fuzz_body:FuzzBody, stage_name):
        match stage_name:
            case 'trigger':
                iter_num = fuzz_body.trigger_iter_num
                result = fuzz_body.trigger_result
                taint_folder = fuzz_body.trigger_taint_folder
                max_taint = None
                cosim_result = None
            case 'access':
                iter_num = fuzz_body.access_iter_num
                result = fuzz_body.access_result
                taint_folder = fuzz_body.access_taint_folder
                max_taint = fuzz_body.access_max_taint
                cosim_result = fuzz_body.access_cosim_result
            case 'leak':
                iter_num = fuzz_body.leak_iter_num
                result = fuzz_body.leak_result
                taint_folder = fuzz_body.leak_taint_folder
                max_taint = fuzz_body.leak_max_taint
                cosim_result = fuzz_body.leak_cosim_result
        config = fuzz_body.config
        is_divergent = fuzz_body.is_divergent

        with open(os.path.join(self.repo_path, f'{stage_name}_iter_record'), "at") as file:
            record = fuzz_body.record_fuzz()
            record['iter_num'] = iter_num
            record['result'] = f'{result}'
            if cosim_result is not None:
                record['cosim_result'] = cosim_result
            if max_taint is not None:
                record['max_taint'] = max_taint
            if is_divergent is not None:
                record['is_divergent'] = is_divergent
            # print(record)
            file.write(hjson.dumps(record))
        
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
                cp_baker.add_cmd(gen_asm.gen_cmd([file_name, f'{self.output_path}/{fuzz_body.sub_repo}']))
        if stage_name == 'leak' and result == FuzzResult.SUCCESS:
            post_taint_folder = taint_folder.replace('leak', 'post')
            for suffix in suffix_taint:
                file_name = f'{post_taint_folder}{suffix}'
                if os.path.exists(file_name):
                    cp_baker.add_cmd(gen_asm.gen_cmd([file_name, f'{self.output_path}/{fuzz_body.sub_repo}']))
        
        rm_asm = ShellCommand("rm", [])
        cp_baker.add_cmd(rm_asm.gen_cmd([f'{self.output_path}/{fuzz_body.sub_repo}/*.elf']))
        cp_baker.add_cmd(rm_asm.gen_cmd([f'{self.output_path}/{fuzz_body.sub_repo}/*.symbol']))
        cp_baker.add_cmd(rm_asm.gen_cmd([f'{self.output_path}/{fuzz_body.sub_repo}/Testbench*.bin']))
        if stage_name == 'leak':
            post_sub_repo = f"{self.output_path}/{fuzz_body.sub_repo.replace('leak', 'post')}"
            if os.path.exists(post_sub_repo):
                cp_baker.add_cmd(rm_asm.gen_cmd([f'-rf', post_sub_repo]))
        cp_baker.run()
    
        if result == FuzzResult.SUCCESS:
            folder = f'{stage_name}_template'
            template_repo_path = os.path.join(self.repo_path, folder)
            if not os.path.exists(template_repo_path):
                os.mkdir(template_repo_path)

            template_repo_path = os.path.join(self.repo_path, folder, str(iter_num))
            target_repo_path = os.path.join(self.output_path, fuzz_body.sub_repo)
            os.system(f'ln -s {target_repo_path} {template_repo_path}')

    def fuzz_trigger(self, config, fuzz_body:FuzzBody):
        iter_num, sub_repo = self.get_repo('trigger', 0)
        fuzz_body = copy.deepcopy(fuzz_body)
        fuzz_body.trigger_iter_num = iter_num
        fuzz_body.update_sub_repo(sub_repo)
        fuzz_body.fuzz_trigger(config)
        self.record_fuzz(fuzz_body, 'trigger')
        return fuzz_body.trigger_result, fuzz_body
    
    def fuzz_access(self, config, fuzz_body:FuzzBody):
        iter_num, sub_repo = self.get_repo('access', 0)
        fuzz_body.access_iter_num = iter_num
        fuzz_body.update_sub_repo(sub_repo)
        fuzz_body.fuzz_access(config)
        self.record_fuzz(fuzz_body, 'access')
        # cov_inc = self.coverage.update_coverage(fuzz_body.access_coverage, is_leak=False)
        # self.fuzz_log.log_cover(fuzz_body.access_iter_num, cov_inc)
        return fuzz_body.access_result, fuzz_body
    
    def fuzz_leak(self, config_list, fuzz_body:FuzzBody):
        fuzz_body_list = [copy.deepcopy(fuzz_body) for _ in config_list]
        for i, config, fuzz_body in zip(range(self.thread_num), config_list, fuzz_body_list):
            iter_num, sub_repo = self.get_repo('leak', i)
            fuzz_body.leak_iter_num = iter_num
            fuzz_body.update_sub_repo(sub_repo)
            fuzz_body.gen_leak(config)
        
        def leak_func(fuzz_body:FuzzBody, thread_i):
            fuzz_body.fuzz_leak(thread_i)
        
        thread_list = []
        for thread_i in range(self.thread_num):
            thread = threading.Thread(target=leak_func, args=(fuzz_body_list[thread_i], thread_i))
            thread.start()
            thread_list.append(thread)
        for thread in thread_list:
            thread.join()
        
        for fuzz_body in fuzz_body_list:
            self.record_fuzz(fuzz_body, 'leak')
            cov_inc = 0
            if not fuzz_body.is_divergent:
                cov_inc += self.coverage.update_coverage(fuzz_body.leak_coverage, is_leak=True)
                cov_inc += self.coverage.update_coverage(fuzz_body.post_coverage, is_leak=False)
                self.fuzz_log.log_cover(fuzz_body.leak_iter_num, cov_inc)

    def fuzz(self, rtl_sim, rtl_sim_mode, taint_log, thread_num):
        self.fuzz_log = FuzzLog(self.repo_path)
        self.thread_num = thread_num

        self.rtl_sim = rtl_sim
        assert rtl_sim_mode in ['vcs', 'vlt'], "the rtl_sim_mode must be in vcs and vlt"
        self.rtl_sim_mode = rtl_sim_mode
        self.taint_log = taint_log
        self.origin_fuzz_body.set_sim_param(self.rtl_sim, self.rtl_sim_mode, self.taint_log)

        class FuzzFSM(Enum):
            IDLE = auto()
            MUTATE_TRIGGER = auto()
            MUTATE_ACCESS = auto()
            ACCUMULATE = auto()
            MUTATE_LEAK = auto()
            STOP = auto()

        last_state = FuzzFSM.IDLE
        state = FuzzFSM.IDLE

        self.coverage = Coverage(self.thread_num)
        self.trigger_seed = TriggerSeed(self.coverage)
        self.access_seed = AccessSeed(self.coverage)
        self.leak_seed_list = [LeakSeed(self.coverage) for _ in range(self.thread_num)]
        config = {}

        MAX_TRIGGER_MUTATE_ITER = 10
        MAX_ACCESS_MUTATE_ITER = 5
        LEAK_ACCUMULATE_ITER = (16 + self.thread_num - 1) // self.thread_num

        self.origin_fuzz_body.update_sub_repo('frame')
        self.origin_fuzz_body.trans.build_frame()

        while True:
            iter_num = 0
            last_state = state
            match(state):
                case FuzzFSM.IDLE:
                    config = self.trigger_seed.mutate({}, True)
                    config = self.access_seed.mutate(config, True)
                    state = FuzzFSM.MUTATE_TRIGGER
                case FuzzFSM.MUTATE_TRIGGER:
                    for iter_num in range(MAX_TRIGGER_MUTATE_ITER):
                        trigger_result, trigger_fuzz_body = self.fuzz_trigger(config, self.origin_fuzz_body)
                        if trigger_result == FuzzResult.SUCCESS:
                            state = FuzzFSM.MUTATE_ACCESS
                            break
                        else:
                            config = self.trigger_seed.mutate({})
                            config = self.access_seed.parse(config)
                    else:
                        config = self.trigger_seed.mutate({}, True)
                        config = self.access_seed.mutate(config, True)
                case FuzzFSM.MUTATE_ACCESS:
                    for iter_num in range(MAX_ACCESS_MUTATE_ITER):
                        access_result, access_fuzz_body = self.fuzz_access(config, trigger_fuzz_body)
                        if access_result == FuzzResult.SUCCESS:
                            state = FuzzFSM.ACCUMULATE
                            break
                        else:
                            config = self.access_seed.mutate(config)
                    else:
                        config = self.trigger_seed.mutate({}, True)
                        config = self.access_seed.mutate(config, True)
                        state = FuzzFSM.MUTATE_TRIGGER
                case FuzzFSM.ACCUMULATE:
                    self.coverage.accumulate()

                    config_list = []
                    for leak_seed in self.leak_seed_list:
                        config = leak_seed.mutate(config, True)
                        config_list.append(config)

                    for iter_num in range(LEAK_ACCUMULATE_ITER):
                        self.fuzz_leak(config_list, access_fuzz_body)

                        new_config_list = []
                        for leak_seed, config in zip(self.leak_seed_list, config_list):
                            config = leak_seed.mutate(config, True)
                            new_config_list.append(config)
                        config_list = new_config_list

                    state = FuzzFSM.MUTATE_LEAK
                case FuzzFSM.MUTATE_LEAK:
                    while True:
                        self.fuzz_leak(config_list, access_fuzz_body)
                        cover_contr = self.coverage.evalute_coverage()
                        self.fuzz_log.log_rate(cover_contr)

                        iter_num += 1
                        if cover_contr < self.TRIGGER_RARE:
                            config = self.trigger_seed.mutate({}, True)
                            config = self.access_seed.mutate(config, True)
                            state = FuzzFSM.MUTATE_TRIGGER
                            break
                        elif cover_contr < self.ACCESS_RATE:
                            config = self.access_seed.mutate(config, True)
                            state = FuzzFSM.MUTATE_ACCESS
                            break
                        else:
                            new_config_list = []
                            for leak_seed, config in zip(self.leak_seed_list, config_list):
                                config = leak_seed.mutate(config)
                                new_config_list.append(config)
                            config_list = new_config_list
                case FuzzFSM.STOP:
                    break
            self.fuzz_log.log_state(last_state, state, iter_num)

        
