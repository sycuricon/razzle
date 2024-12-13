import random
from bitstring import BitArray
from enum import *
import os
import time
from TransManager import *
import math

global_random_state = 0

class FuzzResult(Enum):
    SUCCESS = auto()
    FAIL = auto()
    MAYBE = auto()

class FuzzLog:
    def __init__(self, repo_path):
        self.log_filename = os.path.join(repo_path, 'fuzz.log')
        self.begin_time = time.time()

    def log_record(self, string):
        end_time = time.time()
        with open(self.log_filename, "at") as file:
            file.write(f'{end_time - self.begin_time}\t')
            file.write(string)
            file.write('\n')

    def log_state(self, last_state, next_state, iter_num):
        self.log_record(f'state_switch [{last_state}] -{iter_num}-> [{next_state}]')
    
    def log_cover(self, iter_num, cover_inc):
        self.log_record(f'inc_coverage ({iter_num}) {cover_inc}')
    
    def log_rate(self, rate):
        self.log_record(f'coverage_rate {rate}')

    def log_rand_seed(self, rand_seed):
        self.log_record(f'rand_seed {rand_seed}')
        global global_random_state
        global_random_state = random.getstate()
    
    def log_diverage(self):
        self.log_record(f'coverage_diverage')

class TaintComp:
    def __init__(self):
        self.taint_sum = 0
        self.comp_map = {}

    def __setitem__(self, key, value):
        self.comp_map[key] = value
        self.taint_sum += value

    def __getitem__(self, key):
        return self.comp_map[key]

class Coverage:
    def __init__(self, LEAK_EVALUTE_LEN=8):
        self.state_list = []
        self.trigger_set = set()
        self.coverage_set = set()
        self.coverage_list = []

        self.access_list = None
        self.access_set = None
        self.leak_list = None
        self.leak_set = None
        self.LEAK_EVALUTE_LEN = LEAK_EVALUTE_LEN if LEAK_EVALUTE_LEN > 8 else 8

        self.acc_state = True

        self.coverage_sum = 0
        self.coverage_iter = 0

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
    
    def update_coverage(self, cover_list, is_leak=True):
        cov_inc = 0

        if cover_list is not None:
            origin_num = len(self.coverage_set)
            for cover_state in cover_list:
                self.coverage_set.add(cover_state)
            cov_inc = len(self.coverage_set) - origin_num

            if is_leak:
                self.coverage_list.append(cov_inc)
                if len(self.coverage_list) > self.LEAK_EVALUTE_LEN:
                    self.coverage_list.pop(0)
                self.coverage_sum += cov_inc
                self.coverage_iter += 1

        return cov_inc

    def leak_update_coverage(self, cover_list):
        cov_inc = self.update_coverage(cover_list)

        if cov_inc == 0 and len(self.leak_list) > 1:
            self.leak_list.pop()

        return self.leak_list[-1], cov_inc
    
    def evalute_coverage(self):
        if len(self.coverage_list) < self.LEAK_EVALUTE_LEN:
            return 2.0
        cov_inc = sum(self.coverage_list)
        iter_inc = len(self.coverage_list)
        local_rate = cov_inc/iter_inc
        global_rate = (self.coverage_sum - cov_inc + 1)/(self.coverage_iter - iter_inc + 1)
        return local_rate/(global_rate + 0.1)

class Seed:
    class StatTable:
        def __init__(self):
            self.table = {}
        
        def statistic_rate(self, success, sample):
            func = lambda x : math.sqrt(math.log2(x)/x)
            return func((success + 4)) * func((sample + 4))
        
        def register_entry(self, key):
            self.table[key] = {'success':0, 'sample':0, 'rate':self.statistic_rate(0, 0)}
        
        def update_sample(self, key, result):
            self.table[key]['sample'] += 1
            self.table[key]['success'] += 1 if result == FuzzResult.SUCCESS else 0
            self.table[key]['rate'] = self.statistic_rate(self.table[key]['success'], self.table[key]['sample'])

        def mutate_return(self, key_bound):
            key_rate = {}
            rate_summary = 0
            for key in key_bound:
                rate = self.table[key]['rate']
                key_rate[key] = rate
                rate_summary += rate
            for key, value in key_rate.items():
                key_rate[key] = value/rate_summary
            return random_choice(key_rate)

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
        global global_random_state 
        random.setstate(global_random_state)
    
    def mutate_end(self):
        global global_random_state 
        global_random_state= random.getstate()
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
        PRIV_MODE = auto()
        TRIGGER = auto()
        WARM_UP = auto()
        PMP_R = auto()
        PMP_L = auto()
        PTE_R = auto()
        PTE_V = auto()
    
    field_len = {
        TriggerFieldEnum.TRIGGER_SEED: 22,
        TriggerFieldEnum.DELAY_LEN: 2,
        TriggerFieldEnum.DELAY_FLOAT_RATE: 2,
        TriggerFieldEnum.DELAY_MEM: 1,
        TriggerFieldEnum.PRIV_MODE: 4,
        TriggerFieldEnum.TRIGGER: 5,
        TriggerFieldEnum.WARM_UP: 1,
        TriggerFieldEnum.PMP_R: 1,
        TriggerFieldEnum.PMP_L: 1,
        TriggerFieldEnum.PTE_R: 1,
        TriggerFieldEnum.PTE_V: 1
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

        self.stat_table = Seed.StatTable()
        for trigger_type in TriggerType:
            self.stat_table.register_entry(trigger_type)
    
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
    
    def mutate_field(self, field):
        if field == TriggerSeed.TriggerFieldEnum.TRIGGER:
            trigger_type = [value for value in TriggerType]
            trigger_type = self.stat_table.mutate_return(trigger_type)
            base = self.field_base[field]
            length = self.field_len[field]
            self.seed[base:base+length] = trigger_type.value - 1
        else:
            super().mutate_field(field)

    def update_sample(self, result):
        self.stat_table.update_sample(self.config['trigger_type'], result)
    
    def parse(self, config):
        config = copy.deepcopy(config)
        
        priv_mode = self.get_field(self.TriggerFieldEnum.PRIV_MODE)
        config['train_priv'], config['train_addr'], config['attack_priv'], config['attack_addr'] = \
            [   'UpUp', 'UpSp', 'UpMp', 'SpUp', 'SpMp',\
                'MpUp', 'MpSp', 'MpMp', 'UvUv', 'UvSv', 'UvMp',\
                'SvUv', 'SvSv', 'SvMp', 'MpUv', 'MpSv',\
            ][priv_mode]
        
        if config['attack_addr'] == 'p':
            config['pte_r'] = True
            config['pte_v'] = True
            config['pmp_r'] = self.get_field(self.TriggerFieldEnum.PMP_R) == 1
            config['pmp_l'] = True if config['attack_priv'] == 'M'\
                else self.get_field(self.TriggerFieldEnum.PMP_L) == 1
        else:
            config['pte_r'] = self.get_field(self.TriggerFieldEnum.PTE_R) == 1
            config['pte_v'] = self.get_field(self.TriggerFieldEnum.PTE_V) == 1
            config['pmp_r'] = self.get_field(self.TriggerFieldEnum.PMP_R) == 1
            config['pmp_l'] = False

        config['trigger_seed'] = self.get_field(self.TriggerFieldEnum.TRIGGER_SEED)

        config['delay_len'] = self.get_field(self.TriggerFieldEnum.DELAY_LEN) + 4
        config['delay_float_rate'] = self.get_field(self.TriggerFieldEnum.DELAY_FLOAT_RATE) * 0.1 + 0.4
        config['delay_mem'] = True if self.get_field(self.TriggerFieldEnum.DELAY_MEM) == 1 else False

        config['trigger_type'] = TriggerType(self.get_field(self.TriggerFieldEnum.TRIGGER) + 1)
        if config['attack_addr'] != 'v':
            match config['trigger_type']:
                case TriggerType.LOAD_PAGE_FAULT:
                    config['trigger_type'] = TriggerType.LOAD_ACCESS_FAULT
                case TriggerType.STORE_PAGE_FAULT:
                    config['trigger_type'] = TriggerType.STORE_ACCESS_FAULT
                case TriggerType.AMO_PAGE_FAULT:
                    config['trigger_type'] = TriggerType.AMO_ACCESS_FAULT
                case _:
                    pass
        
        config['warm_up'] = self.get_field(self.TriggerFieldEnum.WARM_UP) == 1

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

        self.stat_table = Seed.StatTable()
        for secret_migrate_type in SecretMigrateType:
            self.stat_table.register_entry(secret_migrate_type)
    
    def mutate_field(self, field):
        if field == AccessSeed.AccessFieldEnum.SECRET_MIGRATE:
            secret_migrate_type = [value for value in SecretMigrateType]
            secret_migrate_type = self.stat_table.mutate_return(secret_migrate_type)
            base = self.field_base[field]
            length = self.field_len[field]
            self.seed[base:base+length] = secret_migrate_type.value - 1
        else:
            super().mutate_field(field)

    def update_sample(self, result):
        self.stat_table.update_sample(self.config['secret_migrate_type'], result)
    
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

        config['secret_migrate_type'] = SecretMigrateType(self.get_field(self.AccessFieldEnum.SECRET_MIGRATE) + 1)

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
        LeakFieldEnum.ENCODE_FUZZ_TYPE: 3,
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
        self.seed, cov_inc = self.coverage.leak_update_coverage(cover_list)
        return cov_inc

    def parse(self, config):
        config = copy.deepcopy(config)
        config['leak_seed'] = self.get_field(self.LeakFieldEnum.LEAK_SEED)

        encode_fuzz_type = self.get_field(self.LeakFieldEnum.ENCODE_FUZZ_TYPE)
        match(encode_fuzz_type):
            case 0|1|2:
                config['encode_fuzz_type'] = EncodeType.FUZZ_FRONTEND
            case 3|4|5:
                config['encode_fuzz_type'] = EncodeType.FUZZ_BACKEND
            case 6|7:
                config['encode_fuzz_type'] = EncodeType.FUZZ_PIPELINE
            case _:
                raise Exception("the encode fuzz type is invalid")

        config['encode_block_len'] = self.get_field(self.LeakFieldEnum.ENCODE_BLOCK_LEN) + 4

        config['encode_block_num'] = self.get_field(self.LeakFieldEnum.ENCODE_BLOCK_NUM) + 2

        return config