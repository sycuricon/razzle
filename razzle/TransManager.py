import os
import random
from SectionManager import *
from SectionUtils import *
from TransBlockUtils import *
from TransVictimBlock import *
from TransTTEBlock import *
from TransTrainBlock import *
from TransFrameBlock import *

from enum import Enum

class MutateState(Enum):
    IDLE = 0
    VICTIM = 1
    END = 2
    TRAIN = 3
    TTE = 4

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

        self.mutate_iter_state = MutateState.IDLE
        self.trans_frame = TransFrameManager(self.config['trans_frame'], self.extension, self.victim_privilege, self.virtual, self.output_path)
        self.trans_exit = TransExitManager(self.config['trans_body'], self.extension, self.victim_privilege, self.virtual, self.output_path, self.trans_frame)
        self.trans_body = self.trans_exit
        self.trans_frame.gen_block()
        self.trans_exit.gen_block()
        self.trans_victim = None
        self.trans_tte = None
        self.victim_train = {}
        self.trans_tte = {}
        self.depth = 0

    def _gen_train_swap_list(self, train_dict):
        train_type = [TrainType.BRANCH_NOT_TAKEN, TrainType.JALR, TrainType.CALL, TrainType.RETURN, TrainType.JMP]
        train_prob = [0.15, 0.1, 0.15, 0.15, 0.05]
        match self.trans_victim.trigger_type:
            case TriggerType.BRANCH:
                train_prob[0] += 0.4
            case TriggerType.JALR | TriggerType.JMP:
                train_prob[1] += 0.4
            case TriggerType.RETURN:
                train_prob[2] += 0.2
                train_prob[3] += 0.2
        train_type = random_choice(train_prob, train_type)
        match(train_type):
            case TrainType.BRANCH_NOT_TAKEN:
                not_taken_swap_idx = train_dict[TrainType.BRANCH_NOT_TAKEN].swap_idx
                taken_swap_idx = train_dict[TrainType.BRANCH_TAKEN].swap_idx
                branch_not_taken_1 = [not_taken_swap_idx]
                branch_not_taken_2 = [not_taken_swap_idx, not_taken_swap_idx]
                branch_taken_1 = [taken_swap_idx]
                branch_taken_2 = [taken_swap_idx, taken_swap_idx]
                branch_balance = random.choice([not_taken_swap_idx, taken_swap_idx], [taken_swap_idx, not_taken_swap_idx])
                return random.choice([branch_not_taken_1, branch_not_taken_2, branch_taken_1, branch_taken_2, branch_balance])
            case _:
                return [train_dict[train_type].swap_idx]
    
    def _gen_tte_swap_list(self):
        swap_list = [self.trans_tte.swap_idx]
        if TriggerType.need_train(self.trans_tte.trigger_type):
            for _ in range(0, 3):
                if random.random() < 0.25:
                    break
                swap_list[0:0] = self._gen_train_swap_list(self.trans_tte)
        return swap_list
    
    def _generate_swap_list(self):
        swap_list = [self.trans_victim.swap_idx, self.trans_exit.swap_idx]
        if TriggerType.need_train(self.trans_victim.trigger_type):
            adjust_weight = 0.6
            for _ in range(0, 4):
                if random.random() < 0.2:
                    break
                if random.random() < adjust_weight:
                    swap_list[0:0] = self._gen_tte_swap_list()
                    adjust_weight = 0
                else:
                    swap_list[0:0] = self._gen_train_swap_list()
                    adjust_weight -= 0.2
        return swap_list 
    
    def update_symbol_table(self):
        self.trans_body.add_symbol_table(os.path.join(self.output_path, 'Testbench.symbol'))
    
    def register_swap_idx(self, swap_idx):
        self.trans_body.register_swap_idx(swap_idx)

    def mem_mutate_iter(self):
        self.depth = 0
        self.trans_victim = TransVictimManager(self.config['trans_body'], self.extension,\
            self.victim_privilege, self.virtual, self.output_path, self.trans_frame, self.depth)
        self.trans_body = self.trans_victim
        self.trans_body.gen_block()
        yield self.trans_body
        self.depth += 1

        self.trans_tte = TransTTEManager(self.config['trans_body'], self.extension,\
                self.victim_privilege, self.virtual, self.output_path, self.trans_frame, self.depth, self.trans_victim)
        self.trans_body = self.trans_tte
        self.trans_body.gen_block()
        yield self.trans_body
        self.depth += 1

        for train_target in [self.trans_victim, self.trans_tte]:
            for train_type in [TrainType(i) for i in range(TrainType.LEN)]:
                self.trans_body = TransTrainManager(self.config['trans_body'], self.extension,\
                    self.victim_privilege, self.virtual, self.output_path, self.trans_frame,\
                    self.depth, train_target, train_type)
                if type(train_target) == TransTTEManager:
                    self.trans_tte[train_type] = self.trans_body
                else:
                    self.trans_victim[train_type] = self.trans_body
                self.trans_body.gen_block()
                yield self.trans_body
                self.depth += 1
        
        raise StopIteration

    def _generate_sections(self):
        if self.mutate_iter_state == MutateState.IDLE:
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
