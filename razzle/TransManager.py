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
        self.trans_body = self.trans_exit = TransExitManager(self.config['trans_body'], self.extension, self.victim_privilege, self.virtual, self.output_path, self.trans_frame)
        self.trans_frame.gen_block()
        self.trans_body.gen_block()
        self.trans_body_array = [self.trans_body]
        self.depth = 0
    
    def _generate_swap_list(self):
        return [i for i in range(len(self.trans_body_array) - 1, -1, -1)]

    def _gen_victim(self):
        trans_body = TransVictimManager(self.config['trans_body'], self.extension,\
                                self.victim_privilege, self.virtual, self.output_path, self.trans_frame, self.depth)
        trans_body.gen_block()
        self.victim = trans_body
        return trans_body

    def _gen_tte(self, victim_target):
        trans_body = TransTTEManager(self.config['trans_body'], self.extension,\
                self.victim_privilege, self.virtual, self.output_path, self.trans_frame, self.depth, victim_target)
        trans_body.gen_block()
        self.tte = trans_body
        return trans_body
    
    def _gen_train(self, train_target):
        trans_body = TransTrainManager(self.config['trans_body'], self.extension,\
                self.victim_privilege, self.virtual, self.output_path, self.trans_frame, self.depth, train_target)
        trans_body.gen_block()
        self.train = trans_body
        return trans_body

    def _mutate_train(self, train_target):
        if(random.choice([True, False])):
            return self._gen_train(train_target.trans_victim)
        else:
            return train_target
    
    def update_symbol_table(self):
        self.trans_body.add_symbol_table(os.path.join(self.output_path, 'Testbench.symbol'))

    def mem_mutate_iter(self):
        if len(self.trans_body_array) == 10:
            self.mutate_iter_state = MutateState.END
        match(self.mutate_iter_state):
            case MutateState.IDLE:
                self.mutate_iter_state = MutateState.VICTIM
                self.trans_body = self._gen_victim()
            case MutateState.VICTIM:
                self.mutate_iter_state = random.choice([MutateState.TRAIN, MutateState.TTE, MutateState.END])
                match(self.mutate_iter_state):
                    case MutateState.TRAIN:
                        self.trans_body = self._gen_train(self.victim)
                        self.train_depth = 1
                    case MutateState.TTE:
                        self.trans_body = self._gen_tte(self.victim)
                    case _:
                        return False
            case MutateState.TRAIN:
                if self.train_depth == 3:
                    self.mutate_iter_state = MutateState.VICTIM
                else:
                    self.mutate_iter_state = random.choice([MutateState.TRAIN, MutateState.VICTIM])
                match(self.mutate_iter_state):
                    case MutateState.TRAIN:
                        self.trans_body = self._mutate_train(self.train)
                        self.train_depth += 1
                    case _:
                        self.train_depth = 0
                        return False
            case MutateState.TTE:
                self.mutate_iter_state = random.choice([MutateState.TRAIN, MutateState.VICTIM])
                match(self.mutate_iter_state):
                    case MutateState.TRAIN:
                        self.trans_body = self._gen_train(self.tte)
                        self.train_depth = 1
                    case _:
                        return False
            case _:
                return False
            
        self.trans_body_array.append(self.trans_body)
        self.depth += 1
        return True

    def mem_mutate_halt(self):
        return self.mutate_iter_state == MutateState.END

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
