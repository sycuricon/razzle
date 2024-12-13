from FuzzBody import *
from FuzzUtils import *
import threading
import matplotlib.pyplot as plt
import numpy as np

class FuzzMachine:
    def __init__(self, hjson_filename, output_path, prefix, core="BOOM", rand_seed=0):
        self.hjson_filename = hjson_filename
        self.build_path = output_path
        assert core in ['BOOM', 'XiangShan']
        self.core = core
        self.prefix_domain = f'{self.core}_{prefix}'
        self.build_path = os.path.join(self.build_path, f'{self.prefix_domain}')
        self.output_path = os.path.join(self.build_path, 'fuzz_code')
        self.repo_path = os.path.join(self.build_path, 'template_repo')
        self.analysis_path = os.path.join(self.build_path, 'analysis_result')
        self.script_path = os.path.join(self.build_path, 'script_workspace')
        for folder in [self.build_path, self.output_path, self.repo_path, self.analysis_path, self.script_path]:
            if not os.path.exists(folder):
                os.makedirs(folder)

        hjson_file = open(hjson_filename)
        fuzz_config = hjson.load(hjson_file)
        self.TRIGGER_RARE = fuzz_config['trigger_rate']
        self.ACCESS_RATE = fuzz_config['access_rate']
        
        self.origin_fuzz_body = FuzzBody(fuzz_config, self.output_path, self.prefix_domain, self.core, self.script_path)
        self.start_time = time.time()

        self.rand_seed = rand_seed
        random.seed(self.rand_seed)
    
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

            if record.get('is_divergent', False):
                record_tuple['coverage'] = []
            elif os.path.exists(f'{testcase_path}.taint.cov'):
                coverage = self.origin_fuzz_body.compute_coverage(testcase_path)
                record_tuple['coverage'] = coverage
            else:
                record_tuple['coverage'] = []

            if record.get('is_divergent', False):
                record_tuple['comp'] = TaintComp()
                # can be comment begin
                if 'divergent_label' not in record:
                    if os.path.exists(f'{testcase_path}.taint.log'):
                        dut_label_list = []
                        vnt_label_list = []
                        for line in open(f'{testcase_path}.taint.log', 'rt'):
                            exec_time, exec_info, _, is_dut = list(map(str.strip ,line.strip().split(',')))
                            exec_time = int(exec_time)
                            is_dut = True if int(is_dut) == 1 else False
                            
                            if exec_info != 'SIM_EXIT_ENQ':
                                if is_dut:
                                    dut_label_list.append((exec_info, exec_time))
                                else:
                                    vnt_label_list.append((exec_info, exec_time))
                                        
                        divergent_label = None
                        is_divergent = False
                        cmp_len = min(len(dut_label_list), len(vnt_label_list))
                        for (dut_label, dut_time), (vnt_label, vnt_time) in zip(dut_label_list[:cmp_len], vnt_label_list[:cmp_len]):
                            if dut_label != vnt_label or dut_time != vnt_time:
                                is_divergent = True
                                divergent_label = dut_label
                                break
                        if is_divergent == False and len(dut_label_list) != len(vnt_label_list):
                            is_divergent = True
                            if len(dut_label_list) > len(vnt_label_list):
                                divergent_label = dut_label_list[cmp_len]
                            else:
                                divergent_label = vnt_label_list[cmp_len]
                        assert divergent_label is not None, testcase_path
                        record['divergent_label'] = divergent_label
                # can be comment end
            elif os.path.exists(f'{testcase_path}.taint.live'):
                comp = self.origin_fuzz_body.compute_comp(testcase_path)
                if stage_name == 'leak':
                    taint_name = f'{self.prefix_domain}_post_thread_{iter_num%thread_num}'
                    post_testcase_path = os.path.join(self.output_path, f'{stage_name}_{iter_num}', taint_name)
                    if os.path.exists(f'{post_testcase_path}.taint.live'):
                        post_comp = self.origin_fuzz_body.compute_comp(post_testcase_path)
                        for key, value in post_comp.comp_map.items():
                            if key in comp.comp_map:
                                comp[key] = comp[key] - value
                                if comp[key] <= 0:
                                    comp.comp_map.pop(key)
                    

                record_tuple['comp'] = comp
            else:
                record_tuple['comp'] = TaintComp()
            record_tuple_list.append(record_tuple)
        return record_tuple_list
    
    def _trigger_record_analysis(self, trigger_record):
        trigger_dict = {}
        trigger_len = 0
        for record in trigger_record:
            record = record['config']
            trigger_type = record['trans']['victim']['block_info']['trigger_block']['type']
            if len(record['trans']['train']) == 0:
                train_type = TrainType.NONE
            else:
                try:
                    train_type = record['trans']['train'][0]['block_info']['train_block']['type']
                except KeyError:
                    train_type = TrainType.NONE
            result = eval(record['result'])
            if trigger_type not in trigger_dict:
                trigger_dict[trigger_type] = {}
            trigger_type_dict = trigger_dict[trigger_type]
            if train_type not in trigger_type_dict:
                trigger_type_dict[train_type] = {'summary':0, 'success':0, 'list':[], 'line_num':0, 'valid_num':0}
            trigger_type_dict[train_type]['summary'] += 1
            if result == FuzzResult.SUCCESS:
                trigger_type_dict[train_type]['success'] += 1
                trigger_type_dict[train_type]['list'].append(int(record['iter_num']))

                line_num = 0
                valid_num = 0
                dirname = os.path.join(self.output_path, f"trigger_{int(record['iter_num'])}")
                for filename in os.listdir(dirname):
                    if filename.endswith('.S') and '1' not in filename and '2' not in filename and '3' not in filename:
                        filename = os.path.join(dirname, filename)
                        for line in open(filename):
                            line = line.strip()
                            if line.startswith('return_block_entry') or line.startswith('nop_ret_block_entry'):
                                break
                            if line != '' and line[0] != '.' and line[0] != '#' and line[-1] != ':':
                                if line != 'nop' and line != 'c.nop':
                                    valid_num += 1
                                line_num += 1 
                trigger_type_dict[train_type]['line_num'] += line_num
                trigger_type_dict[train_type]['valid_num'] += valid_num
        
        trigger_num = []
        trigger_label = []
        analysis_file_name = os.path.join(self.analysis_path, 'trigger_analysis_result.md')
        with open(analysis_file_name, "wt") as file:
            file.write('|trigger_type|train_type|summary|success|rate|line_num|valid_num|case_num|\n')
            file.write('|----|----|----|----|-----|----|----|----|\n')
            for trigger_type, trigger_content in trigger_dict.items():
                for train_type, train_content in trigger_content.items():
                    trigger_type = f'{trigger_type}'.split('.')[-1].lower()
                    train_type = f'{train_type}'.split('.')[-1].lower()
                    summary = train_content['summary']
                    success = train_content['success']
                    test_list = train_content['list']
                    rate = success/summary
                    line_num = train_content['line_num']
                    valid_num = train_content['valid_num']
                    case_num = len(test_list)
                    if success > 0:
                        file.write(f'|{trigger_type}|{train_type}|{summary}|{success}|{rate}|{line_num}|{valid_num}|{case_num}|\n')
                        file.write(f'{test_list}\n')
                        trigger_num.append(summary)
                        trigger_label.append(f'{train_type}.{trigger_type}')
        trigger_num = np.array(trigger_num)
        plt.pie(trigger_num, labels=trigger_label, textprops={'fontsize':8})
        plt.savefig(os.path.join(self.analysis_path, f'trigger_rate.png'))
        plt.clf()

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
            testcase['train_priv'] = record['threat']['train_priv']
            testcase['train_addr'] = record['threat']['train_addr']
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

        analysis_file_name = os.path.join(self.analysis_path, 'access_analysis_result.md')
        with open(analysis_file_name, "wt") as file:
            file.write('|train_type|pmp_r|pmp_l|pte_r|pte_v|threat|li_offset|addr|\n')
            file.write('|----|----|----|----|----|----|----|----|\n')
            for testcase, testcase_idx in zip(access_success,access_testcase):
                file.write(f"|{testcase['train_type']}|{testcase['pmp_r']}|{testcase['pmp_l']}|{testcase['pte_r']}|{testcase['pte_v']}|{testcase['train_priv']}{testcase['train_addr']}{testcase['attack_priv']}{testcase['attack_addr']}|{testcase['li_offset']}|{testcase['addr']}|\n")
                file.write(f'{testcase_idx}\n')

    def _leak_record_analysis(self, leak_record):
        leak_success = []
        leak_index = []
        liveness_record = {}
        for record in leak_record:
            result = eval(record['config']['result'])
            if result == FuzzResult.FAIL or result is None:
                continue
            if 'comp' not in record:
                continue

            idx = record['config']['iter_num']
            if record['config']['is_divergent'] == True:
                comp_simple = ['divergent']
            elif EncodeType.FUZZ_PIPELINE == eval(record['config']['trans']['adjust']['block_info']['encode_block']['strategy']):
                continue
            else:
                record = record['comp']
                comp_simple = set()
                comp = record.comp_map
                for name, value in comp.items():
                    name = list(name.split('.'))
                    match self.core:
                        case 'BOOM':
                            if name[-1].startswith('unnamed$$'):
                                name.pop()
                            name = '.'.join(name[5:-1])
                        case 'XiangShan':
                            if name[-1].startswith('unnamed$$'):
                                name.pop()
                            name = '.'.join(name[7:-1])
                        case _:
                            raise Exception("invalid core type")
                    comp_simple.add(name)
                    liveness_record[name] = liveness_record.get(name, 0) + 1
                comp_simple = list(comp_simple)
                comp_simple.sort()
            try:
                leak_idx = leak_success.index(comp_simple)
                leak_index[leak_idx].append(idx)
            except ValueError:
                leak_success.append(comp_simple)
                leak_index.append([idx])
        
        analysis_file_name = os.path.join(self.analysis_path, 'leak_analysis_result.md')
        with open(analysis_file_name, "wt") as file:
            for comp, idx in zip(leak_success, leak_index):
                file.write(f'{idx}\n{comp}\n')
        analysis_file_name = os.path.join(self.analysis_path, 'liveness_analysis_result.md')
        with open(analysis_file_name, "wt") as file:
            for comp, value in liveness_record.items():
                file.write(f'{comp}\t{value}\n')

    def _part_coverage_record_analysis(self, leak_record, stage_name):
        cov_contr = [0]
        time_list = [0]

        coverage = Coverage()
        for record in leak_record:
            if 'coverage' not in record:
                record['coverage_contr'] = 0
                record['comp'] = TaintComp()
                cov_contr.append(cov_contr[-1])
                time_list.append(time_list[-1])
            else:
                coverage_contr = coverage.update_coverage(record['coverage'])
                record['coverage_contr'] = coverage_contr
                cov_contr.append(cov_contr[-1] + coverage_contr)
                time_list.append(record['config']['time']/3600)
        leak_record.sort(key=lambda x:x['coverage_contr'], reverse=True)

        analysis_file_name = os.path.join(self.analysis_path, f'{stage_name}_coverage_analysis_result.md')
        with open(analysis_file_name, "wt") as file:
            file.write(f"|iter_num|coverage_contr|taint_sum|strategy|\n")
            file.write(f"|--------|--------------|---------|--------|\n")
            for record in leak_record:
                if 'config' not in record:
                    continue
                strategy = eval(record['config']['trans']['adjust']['block_info']['encode_block']['strategy'])
                file.write(f"{record['config']['iter_num']} {record['coverage_contr']} {record['comp'].taint_sum} {strategy} {record['config']['trans']['victim']['block_info']['trigger_block']['type']}\n")
    
        plt.subplot(2, 1, 1)
        plt.plot(cov_contr, label=stage_name)
        plt.subplot(2, 1, 2)
        plt.plot(time_list, cov_contr, label=stage_name)

        curve_file_name = os.path.join(self.analysis_path, f'{stage_name}_curve')
        with open(curve_file_name, "wt") as file:
            for i, cov in enumerate(cov_contr):
                file.write(f'{i} {cov}\n')
    
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
            else:
                ctrl_leak_record.append({})
                data_leak_record.append({})
                full_leak_record.append(record)
        
        self._part_coverage_record_analysis(full_leak_record, 'full')
        self._part_coverage_record_analysis(data_leak_record, 'data')
        self._part_coverage_record_analysis(ctrl_leak_record, 'ctrl')

        plt.legend()
        plt.savefig(os.path.join(self.analysis_path, f'coverage.png'))

        trigger_contr = {}
        coverage_contr = {}
        for record in full_leak_record:
            coverage = record['coverage']
            for comp, hash_value in coverage:
                if comp not in coverage_contr:
                    coverage_contr[comp] = {hash_value}
                else:
                    coverage_contr[comp].add(hash_value)

            trigger_type = record['config']['trans']['victim']['block_info']['trigger_block']['type']
            trigger_contr[trigger_type] = trigger_contr.get(trigger_type, set())
            trigger_contr[trigger_type].update(coverage)

        with open(os.path.join(self.analysis_path, f'coverage_contr.md'), 'wt') as file:
            cover_sum = 0
            for comp, value_list in coverage_contr.items():
                cover_len = len(value_list)
                file.write(f'{comp}\n{cover_len}\n{value_list}\n')
                cover_sum += cover_len
            file.write(f'cover_sum: {cover_sum}\n')
    
            for trigger_type, contr in trigger_contr.items():
                file.write(f'{trigger_type} {len(contr)}\n')

    def _overhead_record_analysis(self):
        overhead_cycle = 0
        victim_cycle = 0
        leak_len = 0
        for dirname in os.listdir(self.output_path):
            if 'leak' not in dirname:
                continue
            leak_len += 1
            dirname = os.path.join(self.output_path, dirname)
            for filename in os.listdir(dirname):
                if '.log' not in filename and 'leak' not in filename:
                    continue
                filename = os.path.join(dirname, filename)
                train_begin = 0
                train_end = 0
                victim_begin = 0
                victim_end = 0
                for line in open(filename):
                    cycle, label, port, is_dut = line.strip().split(', ')
                    cycle = int(cycle)
                    is_dut = int(is_dut)
                    if is_dut == 0:
                        continue
                    match label:
                        # case 'TRAIN_START_ENQ':
                        #     if train_begin == 0:
                        #         train_begin = cycle
                        case 'DELAY_START_ENQ':
                            if train_end == 0:
                                train_end = cycle
                                victim_begin = cycle
                        case 'VCTM_END_DEQ'|'TEXE_START_DEQ':
                            if victim_end == 0:
                                victim_end = cycle
                overhead_cycle += train_end - train_begin
                victim_cycle += victim_end - victim_begin
                break
        
        summary_cycle = overhead_cycle + victim_cycle
        analysis_file_name = os.path.join(self.analysis_path, 'overhead_analysis_result.md')
        with open(analysis_file_name, "wt") as file:
            file.write(f'overhead_cycle:\t{overhead_cycle}\tave:\t{overhead_cycle/leak_len}\n')
            file.write(f'victim_cycle:\t{victim_cycle}\tave:\t{victim_cycle/leak_len}\n')
            file.write(f'summary_cycle:\t{summary_cycle}\tave:\t{summary_cycle/leak_len}\n')
            file.write(f'overhead_rate:\t{overhead_cycle/summary_cycle}')

    def _statistic_record_analysis(self, leak_record):
        combination = {'spectre':{}, 'meltdown':{}, 'both':{}}

        for i,record in enumerate(leak_record):
            config = record['config']
            comp = record['comp']
            if eval(config['result']) == FuzzResult.FAIL:
                continue
            trigger_type = config['trans']['victim']['block_info']['trigger_block']['type'].split('.')[-1].lower()
            if 'access' in trigger_type:
                trigger_type = 'access_fault'
            elif 'page' in trigger_type:
                trigger_type = 'page_fault'
            elif 'misalign' in trigger_type:
                trigger_type = 'misalign'
            
            access_address = config['trans']['victim']['block_info']['access_secret_block']['address']
            access_type = True
            if access_address in [0x80004001, 0x4001, 0xfffffffffff04001]:
                access_type = False
            
            train_priv = config['threat']['train_priv']
            train_addr = config['threat']['train_addr']
            attack_priv = config['threat']['attack_priv']
            attack_addr = config['threat']['attack_addr']
            pmp_r = config['trans']['protect']['block_info']['secret_protect_block']['pmp_r']
            pmp_l = config['trans']['protect']['block_info']['secret_protect_block']['pmp_l']
            pte_r = config['trans']['protect']['block_info']['secret_protect_block']['pte_r']
            pte_v = config['trans']['protect']['block_info']['secret_protect_block']['pte_v']
            has_privilege = True
            if attack_priv == 'M' and pmp_r == False and pmp_l == True or\
                attack_priv in ['U', 'S'] and pmp_r == False or\
                attack_addr == 'v' and (train_addr == 'p' or attack_priv == train_priv) and (pte_v == False or pte_r == False) or\
                attack_addr == 'v' and train_addr == 'v' and attack_priv != train_priv:
                has_privilege = False
            
            encode_comp = set()
            if 'is_divergent' in config and config['is_divergent']:
                if config['divergent_label'] == 'DELAY_END_DEQ'\
                    and config['trans']['victim']['block_info']['delay_block']['delay_mem'] == True\
                    and 'BaseBlockType.LOAD_STORE' in config['trans']['victim']['block_info']['encode_block']['encode_type']:
                    encode_comp.add('ls-ct')
                elif config['divergent_label'] == 'DELAY_END_DEQ'\
                    and config['trans']['victim']['block_info']['warm_up_block']['warm_up'] == True\
                    and 'BaseBlockType.FLOAT' in config['trans']['victim']['block_info']['encode_block']['encode_type']:
                    encode_comp.add('fp-ct')
                elif config['divergent_label'] != 'DELAY_END_DEQ'\
                    and config['trans']['victim']['block_info']['warm_up_block']['warm_up'] == False\
                    and 'BaseBlockType.LOAD' not in config['trans']['victim']['block_info']['encode_block']['encode_type']\
                    and 'BaseBlockType.FLOAT' not in config['trans']['victim']['block_info']['encode_block']['encode_type']:
                    encode_comp.add('delay-fetch')
            else:
                for key in comp.comp_map.keys():
                    key = key.lower()
                    for comp_name in [\
                        'tage','bim','ubtb','btb','ras','loop',\
                        'icache','dcache','tlb','ftb'
                    ]:
                        if comp_name in key:
                            encode_comp.add(comp_name)
                            break
            
            class_dict = combination['meltdown']
            if has_privilege:
                if access_type:
                    class_dict = combination['both']
                else:
                    class_dict = combination['spectre']
            class_dict[trigger_type] = class_dict.get(trigger_type, {})
            class_dict = class_dict[trigger_type]
            for comp in encode_comp:
                class_dict[comp] = class_dict.get(comp, [])
                class_dict[comp].append(config['iter_num'])

        with open(os.path.join(self.analysis_path, "statistic.md"), 'wt') as file:
            for large_class, large_class_value in combination.items():
                for trigger_type, trigger_value in large_class_value.items():
                    for encode_type, encode_iter in trigger_value.items():
                        file.write(f'{large_class} {trigger_type} {encode_type}\n')
                        file.write(f'{encode_iter}\n')

    def fuzz_analysis(self, thread_num):
        thread_num = int(thread_num)
        trigger_record = self._load_stage_record('trigger', None)
        self._trigger_record_analysis(trigger_record)
        
        access_record = self._load_stage_record('access', None)
        self._access_record_analysis(access_record)
        
        leak_record = self._load_stage_record('leak', thread_num)
        self._leak_record_analysis(leak_record)
        self._coverage_record_analysis(leak_record)
        self._statistic_record_analysis(leak_record)
        self._overhead_record_analysis()
    
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
            file.write(hjson.dumps(self.origin_fuzz_body.record_fuzz()))
    
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
        divergent_label = fuzz_body.divergent_label

        with open(os.path.join(self.repo_path, f'{stage_name}_iter_record'), "at") as file:
            record = fuzz_body.record_fuzz()
            record['iter_num'] = iter_num
            record['time'] = time.time() - self.start_time
            record['result'] = f'{result}'
            if cosim_result is not None:
                record['cosim_result'] = cosim_result
            if max_taint is not None:
                record['max_taint'] = max_taint
            if is_divergent is not None:
                record['is_divergent'] = is_divergent
            if divergent_label is not None:
                record['divergent_label'] = divergent_label
            # print(record)
            file.write(hjson.dumps(record))
        
        with open(os.path.join(self.repo_path, f"{stage_name}_iter_num"), "wt") as file:
            file.write(f'{iter_num}\n')
        
        cp_baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, self.script_path, self.repo_path, file_name=f"store_taint_log.sh"
        )
        gen_asm = ShellCommand("cp", [])
        suffix_taint = ['.taint.log', '.taint.csv', '.taint.live', '.taint.cov']
        for suffix in suffix_taint:
            file_name = f'{taint_folder}{suffix}'
            if os.path.exists(file_name):
                cp_baker.add_cmd(gen_asm.gen_cmd([file_name, f'{self.output_path}/{fuzz_body.sub_repo}']))
        if stage_name == 'leak' and result == FuzzResult.SUCCESS:
            post_taint_folder = taint_folder[::-1].replace('leak'[::-1], 'post'[::-1], 1)[::-1]
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

    def fuzz(self, rtl_sim, rtl_sim_mode, taint_log, fuzz_mode, thread_num):
        self.fuzz_log = FuzzLog(self.repo_path)
        self.thread_num = thread_num

        self.rtl_sim = rtl_sim
        assert rtl_sim_mode in ['vcs', 'vlt'], "the rtl_sim_mode must be in vcs and vlt"
        self.rtl_sim_mode = rtl_sim_mode
        assert fuzz_mode in ['trigger', 'access', 'leak'], "the fuzz mode must be in trigger, access and leak"
        self.fuzz_mode = fuzz_mode
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
                    self.fuzz_log.log_rand_seed(self.rand_seed)
                    config = self.trigger_seed.mutate({}, True)
                    config = self.access_seed.mutate(config, True)
                    state = FuzzFSM.MUTATE_TRIGGER
                case FuzzFSM.MUTATE_TRIGGER:
                    for iter_num in range(MAX_TRIGGER_MUTATE_ITER):
                        trigger_result, trigger_fuzz_body = self.fuzz_trigger(config, self.origin_fuzz_body)
                        self.trigger_seed.update_sample(trigger_result)
                        if self.fuzz_mode in ['access', 'leak']:
                            if trigger_result == FuzzResult.SUCCESS:
                                state = FuzzFSM.MUTATE_ACCESS
                                break
                            else:
                                config = self.trigger_seed.mutate({})
                                config = self.access_seed.parse(config)
                        else:
                            config = self.trigger_seed.mutate({})
                            config = self.access_seed.parse(config)
                    else:
                        config = self.trigger_seed.mutate({}, True)
                        config = self.access_seed.mutate(config, True)
                case FuzzFSM.MUTATE_ACCESS:
                    for iter_num in range(MAX_ACCESS_MUTATE_ITER):
                        access_result, access_fuzz_body = self.fuzz_access(config, trigger_fuzz_body)
                        self.access_seed.update_sample(access_result)
                        if self.fuzz_mode in ['leak']:
                            if access_result == FuzzResult.SUCCESS:
                                state = FuzzFSM.ACCUMULATE
                                break
                            else:
                                config = self.access_seed.mutate(config)
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
