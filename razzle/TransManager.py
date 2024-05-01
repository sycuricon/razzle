import os
import random
from SectionManager import *
from SectionUtils import *
from TransBlockUtils import *
from TransVictimBlock import *
from TransTTEBlock import *
from TransTrainBlock import *
from TransFrameBlock import *

from enum import *

class TransManager(SectionManager):
    def __init__(self, config, victim_privilege, virtual, output_path, do_debug):
        self.section = {}
        self.dut_file_list = []
        self.extension = [
            "RV_I",
            "RV64_I",
            "RV_ZICSR",
            "RV_F",
            "RV64_F",
            "RV_D",
            "RV64_D",
            "RV_A",
            "RV64_A",
            "RV_M",
            "RV64_M",
            "RV_C",
            "RV64_C",
            "RV_C_D",
        ]
        self.victim_privilege = victim_privilege
        self.virtual = virtual
        self.output_path = output_path
        self.config = config
        self.do_debug = do_debug

        self.swap_block_list = []
        self.swap_id = 0
        self.swap_map = {}

        self.trans_frame = TransFrameManager(self.config['trans_frame'], self.extension, self.victim_privilege, self.virtual, self.output_path)
        self.trans_exit = TransExitManager(self.config['trans_body'], self.extension, self.victim_privilege, self.virtual, self.output_path, self.trans_frame)
        self._distr_swap_id(self.trans_exit)
        self.trans_body = self.trans_exit
        self.trans_frame.gen_block()
        self.trans_exit.gen_block()
        self.trans_victim = None
        self.trans_tte = None
        self.victim_train = {}
        self.tte_train = {}

    def _distr_swap_id(self, trans_swap):
        trans_swap.register_swap_idx(self.swap_id)
        self.swap_map[self.swap_id] = trans_swap
        self.swap_id += 1
    
    def move_data_section(self):
        data_train_section, data_tte_section, data_tte_train_section, data_victim_section = self.trans_frame.move_data_section()
        self.data_train_section = data_train_section
        self.data_tte_section = data_tte_section
        self.data_tte_train_section = data_tte_train_section
        self.data_victim_section = data_victim_section
    
    def record_fuzz(self, file):
        for swap_block in self.swap_block_list:
            trans_body = self.swap_map[swap_block['swap_id']]
            trans_body.record_fuzz(file)
        file.write('\n')

    def _gen_train_swap_list(self, train_target, train_dict):
        train_prob = {
            TrainType.BRANCH_NOT_TAKEN: 0.15,
            TrainType.JALR: 0.1,
            TrainType.CALL: 0.15,
            TrainType.RETURN: 0.15,
            TrainType.JMP: 0.05
        }
        match train_target.trigger_type:
            case TriggerType.BRANCH:
                train_prob[TrainType.BRANCH_NOT_TAKEN] += 0.4
            case TriggerType.JALR | TriggerType.JMP:
                train_prob[TrainType.JALR] += 0.4
            case TriggerType.RETURN:
                train_prob[TrainType.CALL] += 0.2
                train_prob[TrainType.RETURN] += 0.2
        train_type = random_choice(train_prob)
        match(train_type):
            case TrainType.BRANCH_NOT_TAKEN:
                not_taken_swap_idx = train_dict[TrainType.BRANCH_NOT_TAKEN].mem_region
                taken_swap_idx = train_dict[TrainType.BRANCH_TAKEN].mem_region
                branch_not_taken_1 = [not_taken_swap_idx]
                branch_not_taken_2 = [not_taken_swap_idx, not_taken_swap_idx]
                branch_taken_1 = [taken_swap_idx]
                branch_taken_2 = [taken_swap_idx, taken_swap_idx]
                branch_balance = random.choice([[not_taken_swap_idx, taken_swap_idx], [taken_swap_idx, not_taken_swap_idx]])
                return random.choice([branch_not_taken_1, branch_not_taken_2, branch_taken_1, branch_taken_2, branch_balance])
            case _:
                return [train_dict[train_type].mem_region]
    
    def _gen_tte_swap_list(self):
        swap_list = [self.trans_tte.mem_region]
        if self.trans_tte.need_train():
            for _ in range(0, 3):
                if random.random() < 0.25:
                    break
                swap_list[0:0] = self._gen_train_swap_list(self.trans_tte, self.tte_train)
        return swap_list
    
    def generate_swap_list(self, stage):
        swap_block_list = [self.trans_victim.mem_region, self.trans_exit.mem_region]
        if self.trans_victim.need_train():
            for _ in range(0, 4):
                if random.random() < 0.2:
                    break
                swap_block_list[0:0] = self._gen_train_swap_list(self.trans_victim, self.victim_train)
        self.swap_block_list = swap_block_list
        return swap_block_list 
    
    def update_symbol_table(self, symbol_table):
        self.trans_body.add_symbol_table(symbol_table)
    
    def gen_victim(self, strategy):
        if self.trans_victim is None:
            self.trans_victim = TransVictimManager(self.config['trans_body'], self.extension,\
                self.victim_privilege, self.virtual, self.output_path, self.data_victim_section, strategy)
            self._distr_swap_id(self.trans_victim)
        self.trans_body = self.trans_victim
        self.trans_body.gen_block()

    def gen_victim_train(self):
        if not self.trans_victim.need_train():
            return

        self.data_train_section.clear()

        train_target = self.trans_victim
        if len(self.victim_train) == 0:
            for train_type in [member for member in TrainType]:
                self.trans_body = TransTrainManager(self.config['trans_body'], self.extension,\
                    self.victim_privilege, self.virtual, self.output_path, self.data_train_section,\
                    train_target, train_type)
                self._distr_swap_id(self.trans_body)
                self.victim_train[train_type] = self.trans_body
                self.trans_body.gen_block()
                yield
        else:
            for trans_body in self.victim_train.values():
                self.trans_body = trans_body
                self.trans_body.gen_block()
                yield
    
    def need_train(self):
        return self.trans_victim.need_train()
    
    def store_trigger(self, iter_num, repo_path):
        trigger_repo_path = os.path.join(repo_path, "trigger_template")

        self.swap_list = []
        for swap_block in self.swap_block_list:
            self.swap_list.append(swap_block['swap_id'])

        if not os.path.exists(trigger_repo_path):
            os.makedirs(trigger_repo_path)

        new_template = os.path.join(trigger_repo_path, str(iter_num))
        if not os.path.exists(new_template):
            os.makedirs(new_template)
        for i,swap_id in enumerate(self.swap_list[:-2]):
            train_fold = os.path.join(new_template, f'train_{i}')
            if not os.path.exists(train_fold):
                os.makedirs(train_fold)
            trans_body = self.swap_map[swap_id]
            trans_body.dump_trigger_block(train_fold)
        
        train_fold = os.path.join(new_template, f'trigger')
        if not os.path.exists(train_fold):
            os.makedirs(train_fold)
        trans_body = self.swap_map[self.swap_list[-2]]
        trans_body.dump_trigger_block(train_fold)

        # this baker is repeated, and it not necessary
        cp_baker = BuildManager(
                {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, repo_path, file_name=f"store_taint_log.sh"
            )
        gen_asm = ShellCommand("cp", [])
        cp_baker.add_cmd(gen_asm.gen_cmd([f'{repo_path}/*.log', f'{new_template}']))
        cp_baker.add_cmd(gen_asm.gen_cmd([f'{repo_path}/*.csv', f'{new_template}']))
        cp_baker.run()

    def store_leak(self, iter_num, repo_path):
        leak_repo_path = os.path.join(repo_path, "leak_template")

        if not os.path.exists(leak_repo_path):
            os.makedirs(leak_repo_path)

        new_template = os.path.join(leak_repo_path, str(iter_num))
        if not os.path.exists(new_template):
            os.makedirs(new_template)
        for i,swap_id in enumerate(self.swap_list[:-2]):
            train_fold = os.path.join(new_template, f'train_{i}')
            if not os.path.exists(train_fold):
                os.makedirs(train_fold)
            trans_body = self.swap_map[swap_id]
            trans_body.dump_trigger_block(train_fold)
        
        train_fold = os.path.join(new_template, f'trigger')
        if not os.path.exists(train_fold):
            os.makedirs(train_fold)
        trans_body = self.swap_map[self.swap_list[-2]]
        trans_body.dump_leak_block(train_fold)

        # this baker is repeated, and it not necessary
        cp_baker = BuildManager(
                {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, repo_path, file_name=f"store_taint_log.sh"
            )
        gen_asm = ShellCommand("cp", [])
        cp_baker.add_cmd(gen_asm.gen_cmd([f'{repo_path}/*.log', f'{new_template}']))
        cp_baker.add_cmd(gen_asm.gen_cmd([f'{repo_path}/*.csv', f'{new_template}']))
        cp_baker.run()

    def mutate_victim(self):
        self.trans_victim.mutate()
        self.trans_body = self.trans_victim

    def mutate_tte(self):
        self.trans_tte.mutate()
        self.trans_body = self.victim_tte
    
    def get_swap_idx(self):
        return self.trans_body.swap_idx

    def _generate_sections(self):
        self.trans_frame._generate_sections()
        self.trans_body._generate_sections()

    def _distribute_address(self):
        self.trans_frame._distribute_address()
        self.trans_body._distribute_address()
        self.section = {**self.trans_frame.section, **self.trans_body.section}

    def _write_headers(self, f):
        f.write(f'#include "parafuzz.h"\n')
        f.write(f'#include "fuzzing.h"\n')
        if self.virtual:
            f.write('#define __VIRTUAL__\n')
        if self.do_debug:
            f.write('#define __TRAP_DEBUG__\n')
        f.write('\n')

    def _write_sections(self, f):
        self.trans_frame._write_sections(f)
        self.trans_body._write_sections(f)
