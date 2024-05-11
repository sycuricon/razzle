from bitstring import BitArray
from TransManager import *
from enum import *
import hjson
import random
import time

class FuzzResult(Enum):
    SUCCESS = auto()
    FAIL = auto()
    CONTROL_MAYBE = auto()
    DATA_MAYBE = auto()

class Seed:
    def __init__(self, length):
        self.seed = BitArray(length=length)
        self.seed[:] = random.randint(0, 2**length-1)
    
    def parse(self):
        raise Exception("the parse has not been implementated!!!")

    def get_field(self, field):
        base = self.field_base[field]
        length = self.field_len[field]
        return self.getbits(base, length)
    
    def getbits(self, base, length):
        return self.seed[base:base+length].uint

    def mutate(self):
        random.seed()
        self.seed[:] = random.randint(0, 2**self.seed.len-1)
    
    def mutate_field(self, field):
        base = self.field_base[field]
        length = self.field_len[field]
        self.seed[base:base+length] = random.randint(0, 2 ** length - 1)

class Stage1Seed(Seed):
    class Stage1FieldEnum(Enum):
        STAGE1_SEED = auto()
        DELAY_LEN = auto()
        DELAY_FLOAT_RATE = auto()
        ACCESS_SECRET_LI = auto()
        ACCESS_SECRET_MASK = auto()
        SECRET_MIGRATE = auto()
        TRIGGER = auto()
    
    field_len = {
        Stage1FieldEnum.STAGE1_SEED: 32,
        Stage1FieldEnum.DELAY_LEN: 2,
        Stage1FieldEnum.DELAY_FLOAT_RATE: 2,
        Stage1FieldEnum.ACCESS_SECRET_LI: 1,
        Stage1FieldEnum.ACCESS_SECRET_MASK: 4,
        Stage1FieldEnum.SECRET_MIGRATE: 2,
        Stage1FieldEnum.TRIGGER: 7
    }

    seed_length = 0
    field_base = {}
    for key, value in field_len.items():
        field_base[key] = seed_length
        seed_length += value

    def __init__(self):
        self.seed = BitArray(length=self.seed_length)
        self.config = {}

    def parse(self):
        self.config['stage1_seed'] = self.get_field(self.Stage1FieldEnum.STAGE1_SEED)

        self.config['delay_len'] = self.get_field(self.Stage1FieldEnum.DELAY_LEN) + 4
        
        self.config['delay_float_rate'] = self.get_field(self.Stage1FieldEnum.DELAY_FLOAT_RATE) * 0.1 + 0.4

        self.config['access_secret_li'] = self.get_field(self.Stage1FieldEnum.ACCESS_SECRET_LI) == 1
        access_secret_mask_value = self.get_field(self.Stage1FieldEnum.ACCESS_SECRET_MASK)
        self.config['access_secret_mask'] = 64 if access_secret_mask_value > 8 or self.config['access_secret_li'] else access_secret_mask_value * 4 + 32

        secret_migrate_field = self.get_field(self.Stage1FieldEnum.SECRET_MIGRATE)
        match(secret_migrate_field):
            case 0|1:
                self.config['secret_migrate_type'] = SecretMigrateType.MEMORY
            case 2:
                self.config['secret_migrate_type'] = SecretMigrateType.CACHE
            case 3:
                self.config['secret_migrate_type'] = SecretMigrateType.LOAD_BUFFER

        trigger_field_value = self.get_field(self.Stage1FieldEnum.TRIGGER)
        trigger_finish = False
        if not self.config['access_secret_li']:
            if trigger_field_value < 32:
                self.config['trigger_type'] = TriggerType.V4
                trigger_finish = True
            else:
                trigger_field_value -= 32
        else:
            trigger_field_value = int(trigger_field_value * 96 / 128)
        if not trigger_finish:
            match(trigger_field_value):
                case 0:
                    self.config['trigger_type'] = TriggerType.ECALL
                case 1:
                    self.config['trigger_type'] = TriggerType.ILLEGAL
                case 2:
                    self.config['trigger_type'] = TriggerType.EBREAK
                case 3|4|5|6:
                    self.config['trigger_type'] = TriggerType.LOAD_ACCESS_FAULT
                case 7|8:
                    self.config['trigger_type'] = TriggerType.LOAD_MISALIGN
                case 9|10|11|12:
                    self.config['trigger_type'] = TriggerType.LOAD_PAGE_FAULT
                case 13|14|15|16:
                    self.config['trigger_type'] = TriggerType.STORE_ACCESS_FAULT
                case 17|18:
                    self.config['trigger_type'] = TriggerType.STORE_MISALIGN
                case 19|20|21|22:
                    self.config['trigger_type'] = TriggerType.STORE_PAGE_FAULT
                case 23|24|25|26:
                    self.config['trigger_type'] = TriggerType.AMO_ACCESS_FAULT
                case 27|28:
                    self.config['trigger_type'] = TriggerType.AMO_MISALIGN
                case 29|30|31|32:
                    self.config['trigger_type'] = TriggerType.AMO_PAGE_FAULT
                case 33|34:
                    self.config['trigger_type'] = TriggerType.INT
                case 35|36:
                    self.config['trigger_type'] = TriggerType.FLOAT
                case 37|38:
                    self.config['trigger_type'] = TriggerType.LOAD
                case 39|40:
                    self.config['trigger_type'] = TriggerType.STORE
                case 41|42:
                    self.config['trigger_type'] = TriggerType.AMO
                case _:
                    if 43 <= trigger_field_value < 47:
                        self.config['trigger_type'] = TriggerType.JMP
                    elif 47 <= trigger_field_value < 61:
                        self.config['trigger_type'] = TriggerType.RETURN
                    elif 61 <= trigger_field_value < 75:
                        self.config['trigger_type'] = TriggerType.BRANCH
                    elif 75 <= trigger_field_value < 96:
                        self.config['trigger_type'] = TriggerType.JALR
                    else:
                        raise Exception(f"the invalid trigger number {trigger_field_value}")
        return self.config
    
    def mutate_access(self):
        self.mutate_field(self.Stage1FieldEnum.ACCESS_SECRET_MASK)
        self.mutate_field(self.Stage1FieldEnum.SECRET_MIGRATE)

class Stage2Seed(Seed):
    class Stage2FieldEnum(Enum):
        STAGE2_SEED = auto()
        ENCODE_FUZZ_TYPE = auto()
        ENCODE_BLOCK_LEN = auto()
        ENCODE_BLOCK_NUM = auto()
    
    field_len = {
        Stage2FieldEnum.STAGE2_SEED: 27,
        Stage2FieldEnum.ENCODE_FUZZ_TYPE: 1,
        Stage2FieldEnum.ENCODE_BLOCK_LEN: 2,
        Stage2FieldEnum.ENCODE_BLOCK_NUM: 2
    }

    seed_length = 0
    field_base = {}
    for key, value in field_len.items():
        field_base[key] = seed_length
        seed_length += value

    def __init__(self):
        self.seed = BitArray(length=self.seed_length)
        self.config = {}

    def parse(self):
        self.config['stage2_seed'] = self.get_field(self.Stage2FieldEnum.STAGE2_SEED)

        self.config['encode_fuzz_type'] = 'fuzz_data' if self.get_field(
            self.Stage2FieldEnum.ENCODE_FUZZ_TYPE
        ) == 1 else 'fuzz_control'

        self.config['encode_block_len'] = self.get_field(self.Stage2FieldEnum.ENCODE_BLOCK_LEN) + 4

        self.config['encode_block_num'] = self.get_field(self.Stage2FieldEnum.ENCODE_BLOCK_NUM) + 2

        return self.config

class FuzzManager:
    def __init__(self, hjson_filename, output_path, virtual):
        self.output_path = output_path
        self.virtual = virtual
        self.mem_cfg = MemCfg(0x80000000, 0x40000, self.output_path)
        hjson_file = open(hjson_filename)
        config = hjson.load(hjson_file)
        self.trans = TransManager(config, self.output_path, virtual, self.mem_cfg)
        self.ACCESS_TAINT_THRESHOLD = config['access_taint_threshold']
        self.LEAK_DATA_TAINT_THRESHOLD = config['leak_data_taint_threshold']
        self.LEAK_CONTROL_TAINT_COSIM_THRESHOLD = config['leak_control_taint_cosim_threshold']
        self.LEAK_CONTROL_TAINT_DIST_THRESHOLD = config['leak_control_taint_dist_threshold']
        self.DECODE_CONTROL_TAINT_COSIM_THRESHOLD = config['decode_control_taint_cosim_threshold']
        self.DECODE_CONTROL_TAINT_DIST_THRESHOLD = config['decode_control_taint_dist_threshold']
        self.TAINT_EXPLODE_THRESHOLD = config['taint_explode_threshold']

    def generate(self):
        self.update_sub_repo('gen')
        os.mkdir(os.path.join(self.output_path, 'gen'))

        self.trans.build_frame()
        self.trans.trans_victim.gen_block('default', None)
        self.trans._generate_body_block(self.trans.trans_victim)
        
        self.mem_cfg.add_swap_list(self.trans.swap_block_list)
        self.mem_cfg.dump_conf()
    
    def stage_simulate(self, mode, target="both"):
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
        is_trigger = False
        for line in open(f'{taint_folder}.log', 'rt'):
            _, exec_info, _, _ = list(map(str.strip ,line.strip().split(',')))
            if exec_info == "TEXE_START_ENQ":
                is_trigger = True
                break

        return is_trigger, taint_folder

    def stage1_access_analysis(self):
        taint_folder = self.stage_simulate('variant', 'both')
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
    
    def fuzz_stage1(self, stage1_seed):
        stage1_config = stage1_seed.parse()
        random.seed(stage1_config['stage1_seed'])
        self.trans.trans_victim.gen_block(stage1_config, 'default', None)
        self.trans._generate_body_block(self.trans.trans_victim)

        TRAIN_GEN_MAX_ITER = 6
        ENCODE_MUTATE_MAX_ITER = 3

        max_train_gen = TRAIN_GEN_MAX_ITER
        for _ in range(max_train_gen):
            self.trans.gen_train_swap_list()
            self.mem_cfg.add_swap_list(self.trans.swap_block_list)
            is_trigger, taint_folder = self.stage1_trigger_analysis()
            if not is_trigger:
                continue
            else:
                self._trigger_reduce()
                break

        if not is_trigger:
            return FuzzResult.FAIL, taint_folder

        is_access, taint_folder = self.stage1_access_analysis()
        if is_access:
            return FuzzResult.SUCCESS, taint_folder
        else:
            for _ in range(ENCODE_MUTATE_MAX_ITER):
                stage1_seed.mutate_access()
                config = stage1_seed.parse()
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
            cp_baker.add_cmd(gen_asm.gen_cmd([f'{taint_folder}.log', f'{self.output_path}/{self.sub_repo}']))
        if os.path.exists(f'{taint_folder}.csv'):
            cp_baker.add_cmd(gen_asm.gen_cmd([f'{taint_folder}.csv', f'{template_repo_path}']))
            cp_baker.add_cmd(gen_asm.gen_cmd([f'{taint_folder}.csv', f'{self.output_path}/{self.sub_repo}']))
        rm_asm = ShellCommand("rm", [])
        cp_baker.add_cmd(rm_asm.gen_cmd([f'{self.output_path}/{self.sub_repo}/*.elf']))
        cp_baker.add_cmd(rm_asm.gen_cmd([f'{self.output_path}/{self.sub_repo}/*.symbol']))
        cp_baker.add_cmd(rm_asm.gen_cmd([f'{self.output_path}/{self.sub_repo}/Testbench*.bin']))
        cp_baker.run()

    def record_fuzz(self, iter_num, result,  cosim_result, max_taint, config, stage_num):
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
    
    def stage2_leak_analysis(self, strategy):
        taint_folder = self.stage_simulate('variant', 'both')

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
        is_trigger = False
        for line in open(f'{taint_folder}.log', 'rt'):
            exec_time, exec_info, _, _ = list(map(str.strip ,line.strip().split(',')))
            exec_time = int(exec_time)
            if exec_info == 'DELAY_END_DEQ' and sync_time == 0:
                sync_time = int(exec_time) + 1
            if exec_info == 'VCTM_END_DEQ':
                vicitm_end = int(exec_time)
            if exec_info == "TEXE_START_ENQ":
                is_trigger = True

        if not is_trigger:
            return FuzzResult.FAIL, None, None, taint_folder

        base_spread_list = base_list[sync_time:vicitm_end]
        variant_spread_list = variant_list[sync_time:vicitm_end]

        cosim_result, ave_dist, max_taint = self.taint_analysis(base_spread_list, variant_spread_list)

        if strategy == 'fuzz_control':
            if cosim_result > self.LEAK_CONTROL_TAINT_COSIM_THRESHOLD or\
                ave_dist > self.LEAK_CONTROL_TAINT_DIST_THRESHOLD:
                stage2_result = FuzzResult.SUCCESS
            elif max_taint < self.ACCESS_TAINT_THRESHOLD:
                stage2_result = FuzzResult.FAIL
            else:
                stage2_result = FuzzResult.CONTROL_MAYBE
        else:
            if max_taint > self.TAINT_EXPLODE_THRESHOLD:
                stage2_result = FuzzResult.SUCCESS
            elif max_taint >  self.LEAK_DATA_TAINT_THRESHOLD:
                stage2_result = FuzzResult.DATA_MAYBE
            else:
                stage2_result = FuzzResult.FAIL
        
        return stage2_result, cosim_result, max_taint, taint_folder

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
    
    def fuzz_stage2(self, stage2_seed):
        config = stage2_seed.parse()
        random.seed(config['stage2_seed'])
        self.trans.trans_victim.mutate_encode(config)
        self.trans._generate_body_block(self.trans.trans_victim)
        return self.stage2_leak_analysis(config['encode_fuzz_type'])
    
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
        self.trans.load_template(iter_num, repo_path, "leak_template", 'default', config)
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

        stage1_seed = Stage1Seed()
        trigger_sub_repo = None
        last_trigger_sub_repo = None

        FUZZ_MAX_ITER = 200
        STAGE2_FUZZ_MAX_ITER = 20
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
            self.record_fuzz(stage1_iter_num, stage1_result, None, None, stage1_seed.config, stage_num = 1)
            if stage1_result == FuzzResult.FAIL:
                continue
            else:
                self.store_template(stage1_iter_num, self.repo_path, trigger_folder, taint_folder)

            continue
            
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

                stage2_seed.mutate()
                stage2_result, cosim_result, max_taint, stage2_taint_folder = self.fuzz_stage2(stage2_seed)
                final_config = {**stage1_seed.config, **stage2_seed.config}
                if stage2_result == FuzzResult.FAIL or stage2_result == FuzzResult.SUCCESS:
                    self.record_fuzz(stage2_iter_num, stage2_result, cosim_result, max_taint, final_config, stage_num = 2)
                    if stage2_result == FuzzResult.SUCCESS:
                        self.store_template(stage2_iter_num, self.repo_path, leak_folder, stage2_taint_folder)
                    continue

                stage3_result, _, _, stage3_taint_folder = self.fuzz_stage3()
                if stage3_result == FuzzResult.SUCCESS:
                    self.mem_cfg.dump_conf('both')
                    self.store_template(stage2_iter_num, self.repo_path, leak_folder, stage2_taint_folder)
                self.trans.swap_block_list.pop(-2)
                self.mem_cfg.mem_regions['data_decode'] = []
                self.mem_cfg.add_swap_list(self.trans.swap_block_list)
                self.record_fuzz(stage2_iter_num, stage3_result,  cosim_result, max_taint, final_config, stage_num = 2)
            



