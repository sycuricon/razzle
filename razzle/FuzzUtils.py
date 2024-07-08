import random
from bitstring import BitArray
from enum import *
import os
import time
from TransManager import *

global_random_state = random.getstate()

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
    
    def log_diverage(self):
        self.log_record(f'coverage_diverage')

class TaintComp:
    def __init__(self):
        self.taint_sum = 0
        self.comp_map = {}

    def __setitem__(self, key, value):
        self.comp_map[key] = self.comp_map.get(key, 0) + value
        self.taint_sum += value

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
            for cover_state in cover_list:
                if cover_state not in self.coverage_set:
                    self.coverage_set.add(cover_state)
                    cov_inc += 1

            if is_leak:
                self.coverage_list.append(cov_inc)
                if len(self.coverage_list) > 8:
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
        cov_inc = sum(self.coverage_list)
        iter_inc = len(self.coverage_list)
        local_rate = cov_inc/iter_inc
        global_rate = (self.coverage_sum - cov_inc)/(self.coverage_iter - iter_inc)
        return local_rate/(global_rate + 1)

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
        PRIV_MODE = auto()
        PMP_R = auto()
        PMP_L = auto()
        PTE_R = auto()
        PTE_V = auto()
    
    field_len = {
        TriggerFieldEnum.TRIGGER_SEED: 22,
        TriggerFieldEnum.DELAY_LEN: 2,
        TriggerFieldEnum.DELAY_FLOAT_RATE: 2,
        TriggerFieldEnum.DELAY_MEM: 1,
        TriggerFieldEnum.TRIGGER: 5,
        TriggerFieldEnum.PRIV_MODE: 4,
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

        priv_mode = self.get_field(self.TriggerFieldEnum.PRIV_MODE)
        config['victim_priv'], config['victim_addr'], config['attack_priv'], config['attack_addr'] = \
            ['MpMp', 'MpSv', 'MpUv', 'MpUp', 'SvSv', 'SvUv', 'SvMp', 'UvSv',\
             'UpMp', 'UvMp', 'SvSv', 'SvUv', 'SvMp', 'UvSv', 'UpMp', 'UvMp',][priv_mode]
        
        if config['victim_addr'] == 'p' and config['attack_addr'] == 'p':
            config['pte_r'] = True
            config['pte_v'] = True
            config['pmp_r'] = False
            config['pmp_l'] = True if config['attack_priv'] == 'M'\
                else self.get_field(self.TriggerFieldEnum.PMP_L) == 1
        else:
            config['pte_r'] = self.get_field(self.TriggerFieldEnum.PTE_R) == 1
            config['pte_v'] = self.get_field(self.TriggerFieldEnum.PTE_V) == 1
            config['pmp_r'] = self.get_field(self.TriggerFieldEnum.PMP_R) == 1
            config['pmp_l'] = False
            if config['pte_r'] and config['pte_v'] and config['pmp_r'] and\
                config['victim_priv'] == config['attack_priv']:
                config['pte_r'] = False

        config['trigger_seed'] = self.get_field(self.TriggerFieldEnum.TRIGGER_SEED)

        config['delay_len'] = self.get_field(self.TriggerFieldEnum.DELAY_LEN) + 4
        config['delay_float_rate'] = self.get_field(self.TriggerFieldEnum.DELAY_FLOAT_RATE) * 0.1 + 0.4
        config['delay_mem'] = True if self.get_field(self.TriggerFieldEnum.DELAY_MEM) == 1 else False

        trigger_field_value = self.get_field(self.TriggerFieldEnum.TRIGGER)
        if config['victim_addr'] == 'v':
            match trigger_field_value:
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
        else:
            match trigger_field_value:
                case 0|1:
                    config['trigger_type'] = TriggerType.ECALL
                case 2|3:
                    config['trigger_type'] = TriggerType.ILLEGAL
                case 4|5:
                    config['trigger_type'] = TriggerType.EBREAK
                case 6:
                    config['trigger_type'] = TriggerType.INT
                case 7:
                    config['trigger_type'] = TriggerType.FLOAT
                case 8:
                    config['trigger_type'] = TriggerType.LOAD
                case 9:
                    config['trigger_type'] = TriggerType.STORE
                case 10:
                    config['trigger_type'] = TriggerType.AMO
                case 11:
                    config['trigger_type'] = TriggerType.JMP
                case 12|13:
                    config['trigger_type'] = TriggerType.AMO_ACCESS_FAULT
                case 14|15:
                    config['trigger_type'] = TriggerType.STORE_ACCESS_FAULT
                case 16|17:
                    config['trigger_type'] = TriggerType.LOAD_ACCESS_FAULT
                case 18|19:
                    config['trigger_type'] = TriggerType.AMO_MISALIGN
                case 20|21:
                    config['trigger_type'] = TriggerType.STORE_MISALIGN
                case 22|23:
                    config['trigger_type'] = TriggerType.LOAD_MISALIGN
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
            case 0:
                config['secret_migrate_type'] = SecretMigrateType.MEMORY
            case 1:
                config['secret_migrate_type'] = SecretMigrateType.STORE_BUFFER
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
        self.seed, cov_inc = self.coverage.leak_update_coverage(cover_list)
        return cov_inc

    def parse(self, config):
        config = copy.deepcopy(config)
        config['leak_seed'] = self.get_field(self.LeakFieldEnum.LEAK_SEED)

        encode_fuzz_type = self.get_field(self.LeakFieldEnum.ENCODE_FUZZ_TYPE)
        match(encode_fuzz_type):
            case 0|1:
                config['encode_fuzz_type'] = EncodeType.FUZZ_FRONTEND
            case 2|3:
                config['encode_fuzz_type'] = EncodeType.FUZZ_BACKEND
            # case 2|3:
                # config['encode_fuzz_type'] = EncodeType.FUZZ_PIPELINE
            case _:
                raise Exception("the encode fuzz type is invalid")

        config['encode_block_len'] = self.get_field(self.LeakFieldEnum.ENCODE_BLOCK_LEN) + 4

        config['encode_block_num'] = self.get_field(self.LeakFieldEnum.ENCODE_BLOCK_NUM) + 2

        return config