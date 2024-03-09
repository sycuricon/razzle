from SectionManager import *
from SectionUtils import *
import sys
import os
sys.path.append(os.path.join(os.getcwd(),'razzle_transient/src'))
from razzle_transient.src.TransBlock import *

class FuzzSection(Section):
    def __init__(self,name,flag):
        super().__init__(name,flag)
        self.inst_list=[]

    def add_inst_list(self,list):
        self.inst_list.extend(list)
        self.inst_list.append('\n')

    def _generate_body(self,is_variant):
        return self.inst_list

class TransManager(SectionManager):
    def __init__(self,config):
        super().__init__(config)
        self.transblock={}
        self.extension=['RV_I','RV64_I','RV_ZICSR','RV_F','RV_D','RV64_F','RV64_D','RV_A','RV64_A','RV_M','RV64_M']
        self.train_loop=config['train_loop']
        self.victim_loop=config['victim_loop']
    
    def _generate_sections(self):
        trap_block=TrapBlock('trap',self.extension,True)
        self.transblock['trap']=trap_block
        trap_block.gen_default()

        _init_block=InitSecretBlock('_init',self.extension,True)
        self.transblock['_init']=_init_block
        _init_block.gen_default()

        poc_block=PocBlock('poc',self.extension,True)
        self.transblock['poc']=poc_block
        poc_block.gen_default()

        exit_block=ExitBlock('exit',self.extension,True)
        self.transblock['exit']=exit_block
        exit_block.gen_default()

        delay_block=DelayBlock('delay',self.extension,True)
        self.transblock['delay']=delay_block
        delay_block.gen_default()

        func_begin_block=FunctionBeginBlock('func_begin',self.extension,True,delay_block.result_reg)
        self.transblock['func_begin']=func_begin_block
        func_begin_block.gen_default()

        func_end_block=FunctionEndBlock('func_end',self.extension,True)
        self.transblock['func_end']=func_end_block
        func_end_block.gen_default()

        predict_kind = 'call'
        
        predict_block=PredictBlock('predict',self.extension,True,delay_block.get_result_reg(),predict_kind,func_end_block.name)
        self.transblock['predict']=predict_block
        predict_block.gen_default()

        victim_block=VictimBlock('victim',self.extension,True,func_end_block.name)
        self.transblock['victim']=victim_block
        victim_block.gen_default()

        imm_param={'predict':predict_block.imm,'delay':delay_block.result_imm}
        train_block=TrainBlock('train',self.extension,True,self.train_loop,self.victim_loop,predict_kind,\
                               func_end_block.name,victim_block.name,imm_param)
        self.transblock['train']=train_block
        train_block.gen_default()

        poc_func_block=PocFuncBlock('poc_func',self.extension,True)
        self.transblock['poc_func']=poc_func_block
        poc_func_block.gen_default()

        text_section=self.section['.text']=FuzzSection('.text',Flag.U|Flag.X|Flag.R)
        data_section=self.section['.data']=FuzzSection('.data',Flag.U|Flag.W|Flag.R)
        trap_section=self.section['.trap']=FuzzSection('.trap',Flag.X|Flag.R|Flag.W)
        poc_section=self.section['.poc']=FuzzSection('.poc',Flag.U|Flag.X|Flag.R)

        inst_list, data_list = trap_block.gen_asm()
        trap_section.add_inst_list(inst_list)
        trap_section.add_inst_list(data_list)
        trap_section.add_global_label([trap_block.name, "trap_handle"])

        inst_list, data_list = poc_func_block.gen_asm()
        poc_section.add_inst_list(inst_list)
        poc_section.add_inst_list(data_list)

        block_list=[_init_block, train_block, poc_block, exit_block, \
                    func_begin_block, delay_block, predict_block, victim_block, func_end_block]
        for block in block_list:
            print(block.name)
            inst_list, data_list = block.gen_asm()
            text_section.add_inst_list(inst_list)
            data_section.add_inst_list(data_list)
        text_section.add_global_label([_init_block.name])

    def _distribute_address(self):
        self.section['.trap'].get_bound(self.memory_bound[0][0],self.memory_bound[0][0],0x1000)
        self.section['.text'].get_bound(self.virtual_memory_bound[0][0]+0x1000,self.memory_bound[0][0]+0x1000,0x1000)
        self.section['.data'].get_bound(self.virtual_memory_bound[0][0]+0x2000,self.memory_bound[0][0]+0x2000,0x1000)
        self.section['.poc'].get_bound(self.virtual_memory_bound[1][0],self.memory_bound[1][0],0x1000)
    
    def _write_headers(self,f,is_variant):
        header_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'razzle_transient', 'env', 'trans')
        filenames = os.listdir(header_dir)
        output_dirname = os.path.dirname(f.name)
        for file in filenames:
            if file.endswith('.h'):
                f.write(f'#include"{file}"\n')
                os.system(f"cp {header_dir}/{file} {output_dirname}/")
                

