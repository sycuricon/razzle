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

    def update_coverage(self, cover_list):
        cov_inc = 0
        for cover_state in cover_list:
            if cover_state in self.coverage_set:
                cov_inc += 1
        self.coverage_list.pop(0)
        self.coverage_list.append(cov_inc)

        if cov_inc == 0:
            self.leak_list.pop()

        return self.leak_list[-1]

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
            if self.config is None:
                self.config = config
                break
            elif config != self.config:
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
            if self.config is None:
                self.config = config
                break
            elif config != self.config:
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
            if self.config is None:
                self.config = config
                break
            elif config != self.config:
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
    
    def stage1_trigger_analysis(self):
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

    def stage1_access_analysis(self):
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
        
        is_access = max(base_list) > self.ACCESS_TAINT_THRESHOLD
        return is_access, taint_folder

    def _trigger_reduce(self):
        swap_block_list = self.trans.swap_block_list
        for _ in range(len(swap_block_list)-2):
            for i in range(0, len(swap_block_list)-2):
                tmp_swap_block_list = copy.copy(swap_block_list)
                tmp_swap_block_list.pop(i)
                self.mem_cfg.add_swap_list(tmp_swap_block_list)
                is_trigger, _ = self.stage1_trigger_analysis()
                if is_trigger:
                    swap_block_list = tmp_swap_block_list
                    break
            else:
                break
        self.trans.swap_block_list = swap_block_list
        self.mem_cfg.add_swap_list(swap_block_list)
    
    def fuzz_stage1(self, stage1_seed, access_judge=True):
        stage1_config = stage1_seed.config
        random.seed(stage1_config['stage1_trigger_seed'])
        self.trans.trans_victim.gen_block(stage1_config, EncodeType.FUZZ_DEFAULT, None)
        self.trans._generate_body_block(self.trans.trans_victim)

        TRAIN_GEN_MAX_ITER = 6
        ENCODE_MUTATE_MAX_ITER = 4

        max_train_gen = TRAIN_GEN_MAX_ITER
        for _ in range(max_train_gen):
            self.trans.gen_train_swap_list(self.train_align, self.train_single)
            self.mem_cfg.add_swap_list(self.trans.swap_block_list)
            is_trigger, taint_folder = self.stage1_trigger_analysis()
            if not is_trigger:
                continue
            else:
                self._trigger_reduce()
                break

        if not is_trigger:
            return FuzzResult.FAIL, taint_folder
        
        if not access_judge:
            return FuzzResult.SUCCESS, taint_folder

        is_access, taint_folder = self.stage1_access_analysis()
        if is_access:
            return FuzzResult.SUCCESS, taint_folder
        else:
            for _ in range(ENCODE_MUTATE_MAX_ITER):
                config = stage1_seed.mutate_access()
                self.trans.trans_victim.mutate_access(config)
                self.trans._generate_body_block(self.trans.trans_victim)
                is_access, taint_folder = self.stage1_access_analysis()
                if is_access:
                    return FuzzResult.SUCCESS, taint_folder
                
        return FuzzResult.FAIL, taint_folder
    
    def store_template(self, iter_num, repo_path, folder, taint_folder):
        template_repo_path = os.path.join(repo_path, folder)
        if not os.path.exists(template_repo_path):
            os.mkdir(template_repo_path)

        template_repo_path = os.path.join(repo_path, folder, str(iter_num))
        if not os.path.exists(template_repo_path):
            os.mkdir(template_repo_path)

        cp_baker = BuildManager(
                {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, repo_path, file_name=f"store_taint_log.sh"
            )
        gen_asm = ShellCommand("cp", [])
        cp_baker.add_cmd(gen_asm.gen_cmd([f'{self.output_path}/{self.sub_repo}/swap_mem.cfg'\
            , f'{template_repo_path}']))
        if os.path.exists(f'{taint_folder}.log'):
            cp_baker.add_cmd(gen_asm.gen_cmd([f'{taint_folder}.log', f'{template_repo_path}']))
        if os.path.exists(f'{taint_folder}.csv'):
            cp_baker.add_cmd(gen_asm.gen_cmd([f'{taint_folder}.csv', f'{template_repo_path}']))
        cp_baker.run()

    def record_fuzz(self, iter_num, result, cosim_result, max_taint, config, stage_num, taint_folder):
        with open(os.path.join(self.repo_path, f'stage{stage_num}_iter_record'), "at") as file:
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
        
        with open(os.path.join(self.repo_path, f"stage{stage_num}_iter_num"), "wt") as file:
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
        idx = 0.0
        list_len = len(base_list) - 1
        interval = list_len/101
        diff_rate_byte_array = []
        for _ in range(100):
            idx = min(idx, list_len)
            new_idx = min(idx + interval, list_len)
            sample_base_diff = base_list[int(new_idx)] - base_list[int(idx)]
            diff_rate_byte_array.append(struct.pack('<i', sample_base_diff))
            idx = new_idx
        
        coverage_hash = hash(b''.join(diff_rate_byte_array))
        return coverage_hash
    
    def stage2_leak_analysis(self, strategy):
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
        
        sync_time = 0
        vicitm_end = 0
        texe_begin = 0
        texe_enq_num = 0
        texe_deq_num = 0
        is_trigger = False
        for line in open(f'{taint_folder}.log', 'rt'):
            exec_time, exec_info, _, _ = list(map(str.strip ,line.strip().split(',')))
            exec_time = int(exec_time)
            if exec_info == 'DELAY_END_DEQ' and sync_time == 0:
                sync_time = int(exec_time) + 1
            if exec_info == 'VCTM_END_ENQ' and sync_time != 0 and vicitm_end == 0:
                vicitm_end = int(exec_time)
            if exec_info == "TEXE_START_ENQ" and texe_begin == 0:
                texe_begin = int(exec_time)
            if exec_info == "TEXE_START_ENQ":
                texe_enq_num += 1
            if exec_info == "TEXE_START_DEQ":
                texe_deq_num += 1
        
        is_trigger = texe_enq_num > texe_deq_num

        if not is_trigger:
            return FuzzResult.FAIL, None, None, taint_folder, 0

        coverage = self.compute_coverage(base_list[texe_begin:vicitm_end])

        base_spread_list = base_list[sync_time:vicitm_end]
        variant_spread_list = variant_list[sync_time:vicitm_end]

        cosim_result, ave_dist, max_taint = self.taint_analysis(base_spread_list, variant_spread_list)

        stage2_result = FuzzResult.FAIL
        if cosim_result > self.LEAK_COSIM_THRESHOLD or\
            ave_dist > self.LEAK_DIST_THRESHOLD or\
            max_taint > self.LEAK_EXPLODE_THRESHOLD:
            stage2_result = FuzzResult.SUCCESS
        elif strategy in [EncodeType.FUZZ_BACKEND, EncodeType.FUZZ_FRONTEND]:
            if max_taint > self.LEAK_REMAIN_THRESHOLD:
                stage2_result = FuzzResult.MAYBE
        
        return stage2_result, cosim_result, max_taint, taint_folder, coverage

    def stage3_decode_analysis(self):
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
            stage3_result = FuzzResult.SUCCESS
        else:
            stage3_result = FuzzResult.FAIL
        
        return stage3_result, None, None, taint_folder
    
    def fuzz_stage2(self, stage2_config):
        random.seed(stage2_config['stage2_seed'])
        self.trans.trans_victim.mutate_encode(stage2_config)
        self.trans._generate_body_block(self.trans.trans_victim)
        return self.stage2_leak_analysis(stage2_config['encode_fuzz_type'])
    
    def fuzz_stage3(self):
        self.trans.trans_decode.gen_block(self.trans.trans_victim, None)
        self.trans._generate_body_block(self.trans.trans_decode)
        self.trans.swap_block_list.insert(-1, self.trans.trans_decode.mem_region)
        self.mem_cfg.add_swap_list(self.trans.swap_block_list)
        return self.stage3_decode_analysis()
    
    def load_example(self, rtl_sim, rtl_sim_mode, taint_log, repo_path, iter_num):
        self.rtl_sim = rtl_sim
        self.rtl_sim_mode = rtl_sim_mode
        self.taint_log = taint_log
        self.trans.build_frame()
        stage1_seed = Stage1Seed()
        stage2_seed = Stage2Seed()
        stage1_config = stage1_seed.parse()
        stage2_config = stage2_seed.parse()
        config = {**stage1_config, **stage2_config}
        self.trans.load_template(iter_num, repo_path, "leak_template", EncodeType.FUZZ_DEFAULT, config)
        self.mem_cfg.add_swap_list(self.trans.swap_block_list)
        self.stage_simulate('variant')
    
    def update_sub_repo(self, sub_repo):
        self.sub_repo = sub_repo
        self.mem_cfg.update_sub_repo(sub_repo)
        self.trans.update_sub_repo(sub_repo)
    
    def fuzz(self, rtl_sim, rtl_sim_mode, taint_log, repo_path):
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

        stage1_iter_num_file = os.path.join(self.repo_path, "stage1_iter_num")
        if not os.path.exists(stage1_iter_num_file):
            stage1_begin_iter_num = 0
        else:
            with open(stage1_iter_num_file, "rt") as file:
                stage1_begin_iter_num = 1 + int(file.readline().strip())
        trigger_folder = 'trigger_template'
        leak_folder = 'leak_template'

        stage1_seed = Stage1Seed(self.coverage)
        trigger_sub_repo = None
        last_trigger_sub_repo = None

        FUZZ_MAX_ITER = 200
        STAGE2_FUZZ_MAX_ITER = 40
        for stage1_iter_num in range(stage1_begin_iter_num, stage1_begin_iter_num+FUZZ_MAX_ITER):
            last_trigger_sub_repo = trigger_sub_repo
            trigger_sub_repo = f'trigger_{stage1_iter_num}'
            self.update_sub_repo(trigger_sub_repo)
            trigger_repo = os.path.join(self.output_path, trigger_sub_repo)
            if stage1_iter_num == stage1_begin_iter_num:
                if not os.path.exists(trigger_repo):
                    os.makedirs(trigger_repo)
                self.trans.build_frame()
            else:
                os.system(f'cp -r {os.path.join(self.output_path, last_trigger_sub_repo)} {os.path.join(self.output_path, trigger_repo)}')

            stage1_seed.mutate()
            stage1_result, taint_folder = self.fuzz_stage1(stage1_seed)
            self.record_fuzz(stage1_iter_num, stage1_result, None, None, stage1_seed.config, stage_num = 1, taint_folder = taint_folder)
            if stage1_result == FuzzResult.FAIL:
                continue
            else:
                self.store_template(stage1_iter_num, self.repo_path, trigger_folder, taint_folder)

            stage2_seed = Stage2Seed(self.coverage)
            stage2_iter_num_file = os.path.join(self.repo_path, "stage2_iter_num")
            if not os.path.exists(stage2_iter_num_file):
                stage2_begin_iter_num = 0
            else:
                with open(stage2_iter_num_file, "rt") as file:
                    stage2_begin_iter_num = 1 + int(file.readline().strip())

            stage2_iter_end = stage2_begin_iter_num + STAGE2_FUZZ_MAX_ITER
            stage2_iter_num = stage2_begin_iter_num
            while stage2_iter_num < stage2_iter_end:
                leak_sub_repo = f'leak_{stage2_iter_num}'
                self.update_sub_repo(leak_sub_repo)
                os.system(f'cp -r {trigger_repo} {os.path.join(self.output_path, leak_sub_repo)}')

                stage2_config = stage2_seed.mutate()
                stage2_result, cosim_result, max_taint, stage2_taint_folder, coverage = self.fuzz_stage2(stage2_config)
                stage2_seed.update_coverage(coverage)

                final_config = {**stage1_seed.config, **stage2_seed.config}
                self.record_fuzz(stage2_iter_num, stage2_result, cosim_result, max_taint, final_config, stage_num = 2, taint_folder=stage2_taint_folder)
                if stage2_result in [FuzzResult.SUCCESS, FuzzResult.MAYBE]:
                    self.store_template(stage2_iter_num, self.repo_path, leak_folder, stage2_taint_folder)
                    stage2_iter_end += STAGE2_FUZZ_MAX_ITER//2
                
                stage2_iter_num += 1

    def trigger_test(self, rtl_sim, rtl_sim_mode, taint_log, repo_path):
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

        stage1_iter_num_file = os.path.join(self.repo_path, "stage1_iter_num")
        if not os.path.exists(stage1_iter_num_file):
            stage1_begin_iter_num = 0
        else:
            with open(stage1_iter_num_file, "rt") as file:
                stage1_begin_iter_num = 1 + int(file.readline().strip())
        trigger_folder = 'trigger_template'

        stage1_seed = Stage1Seed()
        trigger_sub_repo = None
        last_trigger_sub_repo = None

        time_begin = datetime.datetime.now()

        FUZZ_MAX_ITER = 4000
        for stage1_iter_num in range(stage1_begin_iter_num, stage1_begin_iter_num+FUZZ_MAX_ITER):
            
            time_end = datetime.datetime.now()
            diff = (time_end - time_begin).seconds
            if diff > 3600:
                break   
            
            last_trigger_sub_repo = trigger_sub_repo
            trigger_sub_repo = f'trigger_{stage1_iter_num}'
            self.update_sub_repo(trigger_sub_repo)
            trigger_repo = os.path.join(self.output_path, trigger_sub_repo)
            if stage1_iter_num == stage1_begin_iter_num:
                if not os.path.exists(trigger_repo):
                    os.makedirs(trigger_repo)
                self.trans.build_frame()
            else:
                os.system(f'cp -r {os.path.join(self.output_path, last_trigger_sub_repo)} {os.path.join(self.output_path, trigger_repo)}')

            stage1_seed.mutate()
            stage1_result, taint_folder = self.fuzz_stage1(stage1_seed, access_judge=False)
            self.record_fuzz(stage1_iter_num, stage1_result, None, None, stage1_seed.config, stage_num = 1, taint_folder=taint_folder)
            if stage1_result == FuzzResult.FAIL:
                continue
            else:
                self.store_template(stage1_iter_num, self.repo_path, trigger_folder, taint_folder)

    def front_end_test(self, rtl_sim, rtl_sim_mode, taint_log, repo_path):
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

        stage1_iter_num_file = os.path.join(self.repo_path, "stage1_iter_num")
        if not os.path.exists(stage1_iter_num_file):
            stage1_begin_iter_num = 0
        else:
            with open(stage1_iter_num_file, "rt") as file:
                stage1_begin_iter_num = 1 + int(file.readline().strip())
        trigger_folder = 'trigger_template'
        leak_folder = 'leak_template'

        stage1_seed = Stage1Seed()
        trigger_sub_repo = None
        last_trigger_sub_repo = None

        time_begin = datetime.datetime.now()

        FUZZ_MAX_ITER = 40000
        STAGE2_FUZZ_MAX_ITER = 20
        for stage1_iter_num in range(stage1_begin_iter_num, stage1_begin_iter_num+FUZZ_MAX_ITER):
            
            time_end = datetime.datetime.now()
            diff = (time_end - time_begin).seconds
            if diff > 3600 * 4:
                break   
            
            last_trigger_sub_repo = trigger_sub_repo
            trigger_sub_repo = f'trigger_{stage1_iter_num}'
            self.update_sub_repo(trigger_sub_repo)
            trigger_repo = os.path.join(self.output_path, trigger_sub_repo)
            if stage1_iter_num == stage1_begin_iter_num:
                if not os.path.exists(trigger_repo):
                    os.makedirs(trigger_repo)
                self.trans.build_frame()
            else:
                os.system(f'cp -r {os.path.join(self.output_path, last_trigger_sub_repo)} {os.path.join(self.output_path, trigger_repo)}')

            stage1_seed.mutate()
            stage1_result, taint_folder = self.fuzz_stage1(stage1_seed, access_judge=False)
            self.record_fuzz(stage1_iter_num, stage1_result, None, None, stage1_seed.config, stage_num = 1, taint_folder=taint_folder)
            if stage1_result == FuzzResult.FAIL:
                continue
            else:
                self.store_template(stage1_iter_num, self.repo_path, trigger_folder, taint_folder)
            
            stage2_seed = Stage2Seed()
            stage2_iter_num_file = os.path.join(self.repo_path, "stage2_iter_num")
            if not os.path.exists(stage2_iter_num_file):
                stage2_begin_iter_num = 0
            else:
                with open(stage2_iter_num_file, "rt") as file:
                    stage2_begin_iter_num = 1 + int(file.readline().strip())

            for stage2_iter_num in range(stage2_begin_iter_num, stage2_begin_iter_num + STAGE2_FUZZ_MAX_ITER):
                leak_sub_repo = f'leak_{stage2_iter_num}'
                self.update_sub_repo(leak_sub_repo)
                os.system(f'cp -r {trigger_repo} {os.path.join(self.output_path, leak_sub_repo)}')
                
                config = stage1_seed.mutate_access()
                self.trans.trans_victim.mutate_access(config)

                config = stage2_seed.mutate()
                random.seed(config['stage2_seed'])
                self.trans.trans_victim.mutate_encode(config)
                self.trans._generate_body_block(self.trans.trans_victim)

                stage_result, _, _, taint_folder = self.fuzz_stage3()
                if stage_result == FuzzResult.SUCCESS:
                    self.mem_cfg.dump_conf('duo')
                    self.store_template(stage2_iter_num, self.repo_path, leak_folder, taint_folder)

                self.trans.swap_block_list.pop(-2)
                self.mem_cfg.mem_regions['data_decode'] = []
                self.mem_cfg.add_swap_list(self.trans.swap_block_list)
                final_config = {**stage1_seed.config, **stage2_seed.config}
                self.record_fuzz(stage2_iter_num, stage_result,  None, None, final_config, stage_num = 2, taint_folder=taint_folder)

            


