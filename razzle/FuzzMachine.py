from FuzzBody import *
from FuzzUtils import *
import threading

class FuzzMachine:
    def __init__(self, hjson_filename, output_path, prefix):
        self.hjson_filename = hjson_filename
        self.build_path = output_path
        self.prefix_domain = prefix
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
        
        self.origin_fuzz_body = FuzzBody(fuzz_config, self.output_path, prefix)
        self.origin_fuzz_body.update_sub_repo('frame')
        self.origin_fuzz_body.trans.build_frame()
    
    def generate(self):
        self.coverage = Coverage()
        self.trigger_seed = TriggerSeed(self.coverage)
        self.access_seed = AccessSeed(self.coverage)
        self.leak_seed = LeakSeed(self.coverage)

        self.origin_fuzz_body.update_sub_repo('gen')
        config = self.trigger_seed.mutate({}, True)
        config = self.access_seed.mutate(config, True)
        config = self.leak_seed.mutate(config, True)
        self.origin_fuzz_body.generate(config)
    
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
            # fuzz_body.trans.record_fuzz(file)
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
        cov_inc = self.coverage.update_coverage(fuzz_body.access_coverage, is_leak=False)
        self.fuzz_log.log_cover(fuzz_body.access_iter_num, cov_inc)
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

        self.coverage = Coverage()
        self.trigger_seed = TriggerSeed(self.coverage)
        self.access_seed = AccessSeed(self.coverage)
        self.leak_seed_list = [LeakSeed(self.coverage) for _ in range(self.thread_num)]
        config = {}

        MAX_TRIGGER_MUTATE_ITER = 10
        MAX_ACCESS_MUTATE_ITER = 5
        LEAK_ACCUMULATE_ITER = (16 + self.thread_num - 1) // self.thread_num

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
                        config = self.trigger_seed.mutate({})
                        config = self.access_seed.mutate(config)
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
                                config = leak_seed.mutate(config, True)
                                new_config_list.append(config)
                            config_list = new_config_list
                case FuzzFSM.STOP:
                    break
            self.fuzz_log.log_state(last_state, state, iter_num)

        
