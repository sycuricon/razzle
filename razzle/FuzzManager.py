import datetime
from bitstring import BitArray
from TransManager import *
from enum import *
import hjson
import random
import time

global_random_state = random.getstate()

class FuzzResult(Enum):
    SUCCESS = auto()
    FAIL = auto()
    MAYBE = auto()

class FuzzLog:
    def __init__(self, repo_path):
        self.log_filename = os.path.join(repo_path, 'fuzz.log')

    def log_record(self, string):
        with open(self.log_filename, "at") as file:
            file.write(string)
            file.write('\n')

    def log_state(self, last_state, next_state, iter_num):
        self.log_record(f'state switch: [{last_state}] -{iter_num}-> [{next_state}]')
    
    def log_cover(self, cover_inc):
        self.log_record(f'inc coverage: {cover_inc}')

class Coverage:
    def __init__(self):
        self.state_list = []
        self.trigger_set = set()
        self.coverage_set = set()
        self.coverage_list = []

        self.access_list = None
        self.access_set = None
        self.leak_list = None
        self.leak_set = None

        self.acc_state = True
        

    def add_trigger_state(self, trigger_seed):
        trigger_hash = trigger_seed.uint
        if trigger_hash in self.trigger_set:
            return False
        trigger_struct = (trigger_seed, [], set())
        self.trigger_set.add(trigger_hash)
        self.access_list = trigger_struct[1]
        self.access_set = trigger_struct[2]
        self.state_list.append(trigger_struct)
        return True

    def add_access_state(self, access_seed):
        access_hash = access_seed.uint
        if access_hash in self.access_set:
            return False
        
        access_struct = (access_seed, [], set())
        self.leak_list = access_struct[1]
        self.leak_set = access_struct[2]
        self.access_list.append(access_struct)
        self.access_set.add(access_hash)
        return True
    
    def add_leak_state(self, leak_seed):
        leak_hash = leak_seed.uint
        if leak_hash in self.leak_set:
            return False
        
        self.leak_list.append(leak_seed)
        self.leak_set.add(leak_hash)
        return True

    def accumulate(self):
        self.coverage_list = []

    def update_coverage(self, cover_list):
        cov_inc = 0
        for cover_state in cover_list:
            if cover_state not in self.coverage_set:
                self.coverage_set.add(cover_state)
                cov_inc += 1
        self.coverage_list.append(cov_inc)
        if len(self.coverage_list) > 10:
            self.coverage_list.pop(0)

        if cov_inc == 0:
            self.leak_list.pop()

        return self.leak_list[-1]
    
    def evalute_coverage(self):
        return sum(self.coverage_list)

class Seed:
    def __init__(self, length):
        self.seed = BitArray(length=length)
        self.seed[:] = random.getrandbits(length)
        self.tmp_random_state = None
        self.config = None
        self.coverage = set()
    
    def parse(self, config):
        raise Exception("the parse has not been implementated!!!")

    def get_field(self, field):
        base = self.field_base[field]
        length = self.field_len[field]
        return self.getbits(base, length)
    
    def getbits(self, base, length):
        return self.seed[base:base+length].uint

    def mutate_begin(self):
        self.tmp_random_state = random.getstate()
        random.setstate(global_random_state)
    
    def mutate_end(self):
        global_random_state = random.getstate()
        random.setstate(self.tmp_random_state)
    
    def mutate_random_field(self, is_full):
        if is_full:
            for type_field in self.field_type:
                self.mutate_field(type_field)
        else:
            for _ in range(len(self.field_type)):
                field = random.choice(self.field_type)
                self.mutate_field(field)
                if random.random() < 0.5:
                    break

    def mutate(self, config, is_full):
        self.mutate_begin()
        while True:
            self.mutate_random_field(is_full)
            config = self.parse(config)
            if self.config is None:
                self.config = config
                break
            elif config != self.config:
                self.config = config
                break
        self.mutate_end()
        
        return self.config
    
    def mutate_field(self, field):
        base = self.field_base[field]
        length = self.field_len[field]
        self.seed[base:base+length] = random.getrandbits(length)

class TriggerSeed(Seed):
    class TriggerFieldEnum(Enum):
        TRIGGER_SEED = auto()
        DELAY_LEN = auto()
        DELAY_FLOAT_RATE = auto()
        DELAY_MEM = auto()
        TRIGGER = auto()
    
    field_len = {
        TriggerFieldEnum.TRIGGER_SEED: 22,
        TriggerFieldEnum.DELAY_LEN: 2,
        TriggerFieldEnum.DELAY_FLOAT_RATE: 2,
        TriggerFieldEnum.DELAY_MEM: 1,
        TriggerFieldEnum.TRIGGER: 5,
    }

    field_type = []

    seed_length = 0
    field_base = {}
    for key, value in field_len.items():
        field_type.append(key)
        field_base[key] = seed_length
        seed_length += value

    def __init__(self, coverage:Coverage):
        super().__init__(self.seed_length)
        self.coverage = coverage
    
    def mutate(self, config, is_full=False):
        self.mutate_begin()
        while True:
            self.mutate_random_field(is_full)
            config = self.parse(config)
            if self.config is None or config != self.config:
                if self.coverage.add_trigger_state(self.seed):
                    self.config = config
                    break
        self.mutate_end()
        
        return self.config
    
    def parse(self, config):
        config = copy.deepcopy(config)

        config['trigger_seed'] = self.get_field(self.TriggerFieldEnum.TRIGGER_SEED)

        config['delay_len'] = self.get_field(self.TriggerFieldEnum.DELAY_LEN) + 4
        config['delay_float_rate'] = self.get_field(self.TriggerFieldEnum.DELAY_FLOAT_RATE) * 0.1 + 0.4
        config['delay_mem'] = True if self.get_field(self.TriggerFieldEnum.DELAY_MEM) == 1 else False

        trigger_field_value = self.get_field(self.TriggerFieldEnum.TRIGGER)
        match(trigger_field_value):
            case 0:
                config['trigger_type'] = TriggerType.ECALL
            case 1:
                config['trigger_type'] = TriggerType.ILLEGAL
            case 2:
                config['trigger_type'] = TriggerType.EBREAK
            case 3:
                config['trigger_type'] = TriggerType.INT
            case 4:
                config['trigger_type'] = TriggerType.FLOAT
            case 5:
                config['trigger_type'] = TriggerType.LOAD
            case 6:
                config['trigger_type'] = TriggerType.STORE
            case 7:
                config['trigger_type'] = TriggerType.AMO
            case 8:
                config['trigger_type'] = TriggerType.JMP
            case 9:
                config['trigger_type'] = TriggerType.AMO_MISALIGN
            case 10:
                config['trigger_type'] = TriggerType.STORE_MISALIGN
            case 11:
                config['trigger_type'] = TriggerType.LOAD_MISALIGN
            case 12|13:
                config['trigger_type'] = TriggerType.AMO_ACCESS_FAULT
            case 14|15:
                config['trigger_type'] = TriggerType.AMO_PAGE_FAULT
            case 16|17:
                config['trigger_type'] = TriggerType.STORE_ACCESS_FAULT
            case 18|19:
                config['trigger_type'] = TriggerType.STORE_PAGE_FAULT
            case 20|21:
                config['trigger_type'] = TriggerType.LOAD_ACCESS_FAULT
            case 22|23:
                config['trigger_type'] = TriggerType.LOAD_PAGE_FAULT
            case 24|25:
                config['trigger_type'] = TriggerType.RETURN
            case 26|27:
                config['trigger_type'] = TriggerType.BRANCH
            case 28|29:
                config['trigger_type'] = TriggerType.JALR
            case 30|31:
                config['trigger_type'] = TriggerType.V4
            case _:
                raise Exception(f"the invalid trigger number {trigger_field_value}")
        return config


class AccessSeed(Seed):
    class AccessFieldEnum(Enum):
        ACCESS_SEED = auto()
        ACCESS_SECRET_LI = auto()
        ACCESS_SECRET_MASK = auto()
        SECRET_MIGRATE = auto()

    field_len = {
        AccessFieldEnum.ACCESS_SEED: 9,
        AccessFieldEnum.ACCESS_SECRET_LI: 1,
        AccessFieldEnum.ACCESS_SECRET_MASK: 4,
        AccessFieldEnum.SECRET_MIGRATE: 2,
    }

    field_type = []

    seed_length = 0
    field_base = {}
    for key, value in field_len.items():
        field_type.append(key)
        field_base[key] = seed_length
        seed_length += value
    
    def __init__(self, coverage:Coverage):
        super().__init__(self.seed_length)
        self.coverage = coverage
    
    def mutate(self, config, is_full=False):
        self.mutate_begin()
        while True:
            self.mutate_random_field(is_full)
            config = self.parse(config)
            if self.config is None or config != self.config:
                if self.coverage.add_access_state(self.seed):
                    self.config = config
                    break
        self.mutate_end()
        
        return self.config
    
    def parse(self, config):
        config = copy.deepcopy(config)
        config['access_seed'] = self.get_field(self.AccessFieldEnum.ACCESS_SEED)

        secret_migrate_field = self.get_field(self.AccessFieldEnum.SECRET_MIGRATE)
        match(secret_migrate_field):
            case 0|1:
                config['secret_migrate_type'] = SecretMigrateType.MEMORY
            case 2:
                config['secret_migrate_type'] = SecretMigrateType.CACHE
            case 3:
                config['secret_migrate_type'] = SecretMigrateType.LOAD_BUFFER

        access_secret_mask_value = self.get_field(self.AccessFieldEnum.ACCESS_SECRET_MASK)
        config['access_secret_mask'] = 64 if access_secret_mask_value > 8 else access_secret_mask_value * 4 + 32
        
        access_secret_li_value = self.get_field(self.AccessFieldEnum.ACCESS_SECRET_LI)
        config['access_secret_li'] = True\
            if config['access_secret_mask'] == 64\
                and config['trigger_type'] != TriggerType.V4 and\
                access_secret_li_value == 1\
            else False
        
        return config


class LeakSeed(Seed):
    class LeakFieldEnum(Enum):
        LEAK_SEED = auto()
        ENCODE_FUZZ_TYPE = auto()
        ENCODE_BLOCK_LEN = auto()
        ENCODE_BLOCK_NUM = auto()
    
    field_len = {
        LeakFieldEnum.LEAK_SEED: 26,
        LeakFieldEnum.ENCODE_FUZZ_TYPE: 2,
        LeakFieldEnum.ENCODE_BLOCK_LEN: 2,
        LeakFieldEnum.ENCODE_BLOCK_NUM: 2
    }

    field_type = []

    seed_length = 0
    field_base = {}
    for key, value in field_len.items():
        field_type.append(key)
        field_base[key] = seed_length
        seed_length += value

    def __init__(self, coverage:Coverage):
        super().__init__(self.seed_length)
        self.coverage = coverage
    
    def mutate(self, config, is_full=False):
        self.mutate_begin()
        while True:
            self.mutate_random_field(is_full)
            config = self.parse(config)
            if self.config is None or config != self.config:
                if self.coverage.add_leak_state(self.seed):
                    self.config = config
                    break
        self.mutate_end()
        
        return self.config

    def update_coverage(self, cover_list):
        self.seed = self.coverage.update_coverage(cover_list)

    def parse(self, config):
        config = copy.deepcopy(config)
        config['leak_seed'] = self.get_field(self.LeakFieldEnum.LEAK_SEED)

        encode_fuzz_type = self.get_field(self.LeakFieldEnum.ENCODE_FUZZ_TYPE)
        match(encode_fuzz_type):
            case 0:
                config['encode_fuzz_type'] = EncodeType.FUZZ_FRONTEND
            case 1:
                config['encode_fuzz_type'] = EncodeType.FUZZ_BACKEND
            case 2|3:
                config['encode_fuzz_type'] = EncodeType.FUZZ_PIPELINE
            case _:
                raise Exception("the encode fuzz type is invalid")

        config['encode_block_len'] = self.get_field(self.LeakFieldEnum.ENCODE_BLOCK_LEN) + 4

        config['encode_block_num'] = self.get_field(self.LeakFieldEnum.ENCODE_BLOCK_NUM) + 2

        return config

class FuzzManager:
    def __init__(self, hjson_filename, output_path, virtual):
        self.output_path = output_path
        self.virtual = virtual
        self.mem_cfg = MemCfg(0x80000000, 0x40000, self.output_path)
        hjson_file = open(hjson_filename)
        config = hjson.load(hjson_file)
        self.trans = TransManager(config, self.output_path, virtual, self.mem_cfg)
        self.ACCESS_TAINT_THRESHOLD = config['access_taint_threshold']
        self.LEAK_REMAIN_THRESHOLD = config['leak_remain_threshold']
        self.LEAK_EXPLODE_THRESHOLD = config['leak_explode_threshold']
        self.LEAK_COSIM_THRESHOLD = config['leak_cosim_threshold']
        self.LEAK_DIST_THRESHOLD = config['leak_dist_threshold']
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
        self.trans.gen_train_swap_list(True, True)

        seed = AccessSeed(self.coverage)
        config = seed.mutate(config, True)
        self.trans.trans_victim.mutate_access(config)

        seed = LeakSeed(self.coverage)
        config = seed.mutate(config, True)
        self.trans.trans_victim.mutate_encode(config)
        
        self.mem_cfg.add_swap_list(self.trans.swap_block_list)
        self.mem_cfg.dump_conf('duo')
    
    def stage_simulate(self, mode, target="duo"):
        self.mem_cfg.dump_conf(target)

        assert mode in ['normal', 'robprofile', 'variant']
        baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.rtl_sim, file_name=f"rtl_sim.sh"
        )
        export_cmd = ShellCommand("export", [])
        gen_asm = ShellCommand("make", [f'{self.rtl_sim_mode}'])
        baker.add_cmd(export_cmd.gen_cmd([f'SIM_MODE={mode}']))
        baker.add_cmd(export_cmd.gen_cmd([f'STARSHIP_TESTCASE={self.output_path}/{self.sub_repo}/swap_mem.cfg']))
        baker.add_cmd(gen_asm.gen_cmd())
        baker.run()

        return f'{self.taint_log}_{mode}/wave/swap_mem.cfg.taint'
    
    def trigger_analysis(self):
        taint_folder = self.stage_simulate('robprofile', 'dut')
        texe_enq_num = 0
        texe_deq_num = 0
        for line in open(f'{taint_folder}.log', 'rt'):
            _, exec_info, _, _ = list(map(str.strip ,line.strip().split(',')))
            if exec_info == "TEXE_START_ENQ":
                texe_enq_num += 1
            if exec_info == "TEXE_START_DEQ":
                texe_deq_num += 1
                
        if texe_enq_num > texe_deq_num:
            is_trigger = True
        else:
            is_trigger = False

        return is_trigger, taint_folder

    def access_analysis(self):
        taint_folder = self.stage_simulate('variant', 'duo')
        with open(f'{taint_folder}.csv', "r") as file:
            taint_log = csv.reader(file)
            _ = next(taint_log)
            time_list = []
            base_list = []
            variant_list = []
            for time, base, variant in taint_log:
                time_list.append(int(time))
                base_list.append(int(base))
                variant_list.append(int(variant))
        
        max_taint = max(base_list)
        is_access = max_taint > self.ACCESS_TAINT_THRESHOLD
        return is_access, taint_folder, max_taint

    def _trigger_reduce(self, is_trigger):
        if is_trigger:
            swap_block_list = self.trans.swap_block_list
            for _ in range(len(swap_block_list)-2):
                for i in range(0, len(swap_block_list)-2):
                    tmp_swap_block_list = copy.copy(swap_block_list)
                    tmp_swap_block_list.pop(i)
                    self.mem_cfg.add_swap_list(tmp_swap_block_list)
                    is_trigger, _ = self.trigger_analysis()
                    if is_trigger:
                        swap_block_list = tmp_swap_block_list
                        break
                else:
                    break
            reduce_list = [swap_mem['swap_id'] for swap_mem in self.trans.swap_block_list if swap_mem not in swap_block_list]
            self.trans.swap_block_list = swap_block_list
            self.mem_cfg.add_swap_list(swap_block_list)
            
            if len(swap_block_list) > 2:
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
            if len(self.trans.swap_block_list) > 2:
                reduce_baker = BuildManager(
                    {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.repo_path, file_name=f"reduce_trigger.sh"
                )
                rm_asm = ShellCommand("rm", [])
                for swap_mem in self.trans.swap_block_list:
                    idx = swap_mem['swap_id']
                    if idx == 0 or idx == 1:
                        continue
                    reduce_baker.add_cmd(rm_asm.gen_cmd([f'{self.output_path}/{self.sub_repo}/*{idx}*']))
                reduce_baker.run()

    
    def get_sub_repo(self, stage_name):
        iter_num_file = os.path.join(self.repo_path, f"{stage_name}_iter_num")
        if not os.path.exists(iter_num_file):
            iter_num = 0
        else:
            with open(iter_num_file, "rt") as file:
                iter_num = 1 + int(file.readline().strip())

        sub_repo = f'{stage_name}_{iter_num}'
        self.update_sub_repo(sub_repo)
        return iter_num, sub_repo
    
    def fuzz_trigger(self, config, old_trigger_repo):
        trigger_iter_num, trigger_sub_repo = self.get_sub_repo('trigger')

        trigger_repo = os.path.join(self.output_path, trigger_sub_repo)
        if old_trigger_repo is None:
            if not os.path.exists(trigger_repo):
                os.makedirs(trigger_repo)
            self.trans.build_frame()
        else:
            os.system(f'cp -r {old_trigger_repo} {trigger_repo}')

        random.seed(config['trigger_seed'])
        self.trans.trans_victim.gen_block(config, EncodeType.FUZZ_DEFAULT, None)
        self.trans._generate_body_block(self.trans.trans_victim)

        TRAIN_GEN_MAX_ITER = 6
        ENCODE_MUTATE_MAX_ITER = 4

        max_train_gen = TRAIN_GEN_MAX_ITER
        trigger_result = FuzzResult.FAIL
        for _ in range(max_train_gen):
            self.trans.gen_train_swap_list(self.train_align, self.train_single)
            self.mem_cfg.add_swap_list(self.trans.swap_block_list)
            is_trigger, taint_folder = self.trigger_analysis()
            self._trigger_reduce(is_trigger)
            if is_trigger:
                trigger_result = FuzzResult.SUCCESS
                break

        self.record_fuzz(trigger_iter_num, trigger_result, None, None, config, 'trigger', taint_folder = taint_folder)
        if trigger_result == FuzzResult.SUCCESS:
            self.store_template(trigger_iter_num, self.repo_path, 'trigger', taint_folder)

        return trigger_repo, trigger_result
    
    def fuzz_access(self, config, trigger_repo):
        access_iter_num, access_sub_repo = self.get_sub_repo('access')

        access_repo = os.path.join(self.output_path, access_sub_repo)
        os.system(f'cp -r {trigger_repo} {access_repo}')

        self.trans.trans_victim.mutate_access(config)
        self.trans._generate_body_block(self.trans.trans_victim)
        is_access, taint_folder, max_taint = self.access_analysis()
        access_result = FuzzResult.SUCCESS if is_access else FuzzResult.FAIL

        self.record_fuzz(access_iter_num, access_result, None, max_taint, config, 'access', taint_folder = taint_folder)
        if access_result == FuzzResult.SUCCESS:
            self.store_template(access_iter_num, self.repo_path, 'access', taint_folder)
        
        return access_repo, access_result
    
    def store_template(self, iter_num, repo_path, stage_name, taint_folder):
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
            file.write(f'virtual:\t{self.virtual}\n')
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
            self.trans.record_fuzz(file)
            file.write('\n')
        
        with open(os.path.join(self.repo_path, f"{stage_name}_iter_num"), "wt") as file:
            file.write(f'{iter_num}\n')
        
        cp_baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.repo_path, file_name=f"store_taint_log.sh"
        )
        gen_asm = ShellCommand("cp", [])
        if os.path.exists(f'{taint_folder}.log'):
            cp_baker.add_cmd(gen_asm.gen_cmd([f'{taint_folder}.log', f'{self.output_path}/{self.sub_repo}']))
        if os.path.exists(f'{taint_folder}.csv'):
            cp_baker.add_cmd(gen_asm.gen_cmd([f'{taint_folder}.csv', f'{self.output_path}/{self.sub_repo}']))
        
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

    def compute_coverage(self, base_list):
        coverage = []
        for i, taint in enumerate(base_list[:-1]):
            cover_state = (taint, base_list[i+1] - taint)
            coverage.append(cover_state)
        return coverage
    
    def leak_analysis(self, strategy):
        taint_folder = self.stage_simulate('variant', 'duo')

        with open(f'{taint_folder}.csv', "r") as file:
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
        dut_vicitm_end = 0
        vnt_sync_time = 0
        vnt_vicitm_end = 0
        dut_texe_begin = 0
        dut_texe_enq_num = 0
        dut_texe_deq_num = 0
        is_trigger = False
        for line in open(f'{taint_folder}.log', 'rt'):
            exec_time, exec_info, _, is_dut = list(map(str.strip ,line.strip().split(',')))
            exec_time = int(exec_time)
            is_dut = True if int(is_dut) == 1 else False
            if exec_info == 'DELAY_END_DEQ' and dut_sync_time == 0 and is_dut:
                dut_sync_time = exec_time + 1
            if exec_info == 'VCTM_END_ENQ' and dut_sync_time != 0 and dut_vicitm_end == 0 and is_dut:
                dut_vicitm_end = exec_time

            if exec_info == 'DELAY_END_DEQ' and vnt_sync_time == 0 and not is_dut:
                vnt_sync_time = exec_time + 1
            if exec_info == 'VCTM_END_ENQ' and vnt_sync_time != 0 and vnt_vicitm_end == 0 and not is_dut:
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
            return FuzzResult.FAIL, None, None, taint_folder, [(0,0)]

        coverage = self.compute_coverage(base_list[dut_texe_begin:dut_vicitm_end])

        base_spread_list = base_list[dut_sync_time:dut_vicitm_end]
        variant_spread_list = variant_list[dut_sync_time:dut_vicitm_end]

        cosim_result, ave_dist, max_taint = self.taint_analysis(base_spread_list, variant_spread_list)

        leak_result = FuzzResult.FAIL
        if strategy in [EncodeType.FUZZ_PIPELINE]:
            if is_divergent:
                leak_result = FuzzResult.SUCCESS
            elif cosim_result > self.LEAK_COSIM_THRESHOLD or\
            ave_dist > self.LEAK_DIST_THRESHOLD or\
            max_taint > self.LEAK_EXPLODE_THRESHOLD:
                leak_result = FuzzResult.MAYBE
        elif strategy in [EncodeType.FUZZ_BACKEND, EncodeType.FUZZ_FRONTEND]:
            if max_taint > self.LEAK_REMAIN_THRESHOLD:
                leak_result = FuzzResult.MAYBE
        
        return leak_result, cosim_result, max_taint, taint_folder, coverage

    def fuzz_leak(self, config, access_repo):
        leak_iter_num, leak_sub_repo = self.get_sub_repo('leak')

        leak_repo = os.path.join(self.output_path, leak_sub_repo)
        os.system(f'cp -r {access_repo} {leak_repo}')

        self.trans.trans_victim.mutate_encode(config)
        self.trans._generate_body_block(self.trans.trans_victim)
        leak_result, cosim_result, max_taint, taint_folder, coverage = self.leak_analysis(config['encode_fuzz_type'])

        self.record_fuzz(leak_iter_num, leak_result, cosim_result, max_taint, config, 'leak', taint_folder = taint_folder)
        if leak_result in [FuzzResult.SUCCESS, FuzzResult.MAYBE]:
            self.store_template(leak_iter_num, self.repo_path, 'leak', taint_folder)
        
        return leak_repo, leak_result, coverage

    def decode_analysis(self):
        taint_folder = self.stage_simulate('robprofile', 'dut')
        
        base_decode_end = 0
        for line in open(f'{taint_folder}.log', 'rt'):
            exec_time, exec_info, _, _ = list(map(str.strip ,line.strip().split(',')))
            exec_time = int(exec_time)
            if exec_info == 'VCTM_END_DEQ':
                base_decode_end = int(exec_time)
        
        taint_folder = self.stage_simulate('robprofile', 'vnt')
        
        variant_decode_end = 0
        for line in open(f'{taint_folder}.log', 'rt'):
            exec_time, exec_info, _, _ = list(map(str.strip ,line.strip().split(',')))
            exec_time = int(exec_time)
            if exec_info == 'VCTM_END_DEQ':
                variant_decode_end = int(exec_time)

        if base_decode_end != variant_decode_end:
            decode_result = FuzzResult.SUCCESS
        else:
            decode_result = FuzzResult.FAIL
        
        return decode_result, taint_folder
    
    def fuzz_decode(self, config, leak_repo):
        decode_iter_num, decode_sub_repo = self.get_sub_repo('decode')

        decode_repo = os.path.join(self.output_path, decode_sub_repo)
        os.system(f'cp -r {leak_repo} {decode_repo}')

        self.trans.trans_decode.gen_block(self.trans.trans_victim, None)
        self.trans._generate_body_block(self.trans.trans_decode)
        self.trans.swap_block_list.insert(-1, self.trans.trans_decode.mem_region)
        self.mem_cfg.add_swap_list(self.trans.swap_block_list)
        decode_result, taint_folder = self.decode_analysis()

        self.record_fuzz(decode_iter_num, decode_result, None, None, config, 'decode', taint_folder = taint_folder)
        if decode_result in [FuzzResult.SUCCESS, FuzzResult.MAYBE]:
            self.store_template(decode_iter_num, self.repo_path, 'decode', taint_folder)
        
        return decode_repo, decode_result, decode_repo

    
    def load_example(self, rtl_sim, rtl_sim_mode, taint_log, repo_path, iter_num):
        self.rtl_sim = rtl_sim
        self.rtl_sim_mode = rtl_sim_mode
        self.taint_log = taint_log
        self.trans.build_frame()
        trigger_seed = TriggerSeed(self.coverage)
        access_seed = AccessSeed(self.coverage)
        leak_seed = LeakSeed(self.coverage)
        config = trigger_seed.parse({})
        config = access_seed.parse(config)
        config = leak_seed.parse(config)
        self.trans.load_template(iter_num, repo_path, "leak_template", EncodeType.FUZZ_DEFAULT, config)
        self.mem_cfg.add_swap_list(self.trans.swap_block_list)
        self.stage_simulate('variant')
    
    def update_sub_repo(self, sub_repo):
        self.sub_repo = sub_repo
        self.mem_cfg.update_sub_repo(sub_repo)
        self.trans.update_sub_repo(sub_repo)
    
    def fuzz(self, rtl_sim, rtl_sim_mode, taint_log, repo_path):
        self.fuzz_log = FuzzLog(repo_path)

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
        leak_seed = LeakSeed(self.coverage)
        config = {}
        access_mutate_flag = 0
        stop_flag = 0
        trigger_repo = None
        access_repo = None
        leak_repo = None

        MAX_TRIGGER_MUTATE_ITER = 40
        MAX_ACCESS_MUTATE_ITER = 10
        LEAK_ACCUMULATE_ITER = 20
        ACCESS_MUTATE_THRES = 2
        STOP_THRES = 2
        LEAK_MUTATE_THRES = 40
        TRIGGER_MUTATE_THRES = 10
        while True:
            iter_num = 0
            last_state = state
            match(state):
                case FuzzFSM.IDLE:
                    if stop_flag == STOP_THRES:
                        stop_flag = 0
                        break
                    else:
                        trigger_seed = TriggerSeed(self.coverage)
                        config = trigger_seed.mutate({}, True)
                        access_seed = AccessSeed(self.coverage)
                        config = access_seed.mutate(config, True)
                        state = FuzzFSM.MUTATE_TRIGGER
                case FuzzFSM.MUTATE_TRIGGER:
                    for iter_num in range(MAX_TRIGGER_MUTATE_ITER):
                        trigger_repo, trigger_result = self.fuzz_trigger(config, trigger_repo)
                        if trigger_result == FuzzResult.SUCCESS:
                            state = FuzzFSM.MUTATE_ACCESS
                            break
                        else:
                            config = trigger_seed.mutate({})
                            config = access_seed.parse(config)
                    else:
                        state = FuzzFSM.IDLE
                case FuzzFSM.MUTATE_ACCESS:
                    for iter_num in range(MAX_ACCESS_MUTATE_ITER):
                        access_repo, access_result = self.fuzz_access(config, trigger_repo)
                        if access_result == FuzzResult.SUCCESS:
                            leak_seed = LeakSeed(self.coverage)
                            state = FuzzFSM.ACCUMULATE
                            break
                        else:
                            config = access_seed.mutate(config)
                    else:
                        config = trigger_seed.mutate({})
                        config = access_seed.mutate(config)
                        state = FuzzFSM.MUTATE_TRIGGER
                case FuzzFSM.ACCUMULATE:
                    if access_mutate_flag == ACCESS_MUTATE_THRES:
                        state = FuzzFSM.MUTATE_ACCESS
                        config = access_seed.mutate(config)
                        access_mutate_flag = 0
                    else:
                        self.coverage.accumulate()
                        config = leak_seed.mutate(config, True)
                        for iter_num in range(LEAK_ACCUMULATE_ITER):
                            leak_repo, leak_result, coverage = self.fuzz_leak(config, access_repo)
                            leak_seed.update_coverage(coverage)
                            self.fuzz_log.log_cover(self.coverage.coverage_list[-1])
                            config = leak_seed.mutate(config)
                        state = FuzzFSM.MUTATE_LEAK
                case FuzzFSM.MUTATE_LEAK:
                    while True:
                        leak_repo, leak_result, coverage = self.fuzz_leak(config, access_repo)
                        leak_seed.update_coverage(coverage)
                        self.fuzz_log.log_cover(self.coverage.coverage_list[-1])
                        cover_contr = self.coverage.evalute_coverage()
                        iter_num += 1
                        if cover_contr < TRIGGER_MUTATE_THRES:
                            state = FuzzFSM.IDLE
                            stop_flag += 1
                            access_mutate_flag = 0
                            break
                        elif cover_contr < LEAK_MUTATE_THRES:
                            state = FuzzFSM.ACCUMULATE
                            access_mutate_flag += 1
                            break
                        else:
                            config = leak_seed.mutate(config, False)
                            stop_flag = 0
                            access_mutate_flag = 0
            self.fuzz_log.log_state(last_state, state, iter_num)

                        




