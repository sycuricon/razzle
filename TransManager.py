from SectionManager import *
from SectionUtils import *
import sys
import os
from TransBlock import *

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
        self.extension=['RV_I','RV64_I','RV_ZICSR','RV_F','RV64_F',\
                        'RV_D','RV64_D','RV_A','RV64_A','RV_M','RV64_M']
        self.block_param=config['block_param']
    
    def _generate_sections(self):
        block_index = [('_init',InitBlock),('mtrap',MTrapBlock),('strap',STrapBlock),\
            ('exit',ExitBlock),('return',ReturnBlock),\
            ('delay',DelayBlock),('predict',PredictBlock),('run_time',RunTimeBlock),\
            ('encode',EncodeBlock),('decode_call',DecodeCallBlock),('decode',DecodeBlock)\
        ]

        self.graph = {}
        for index, block_construct in block_index:
            block = block_construct(self.extension, self.block_param[index+'_param'])
            self.graph[index] = block

        for index, block_construct in block_index:
            self.graph[index].gen_instr(self.graph)

        text_section=self.section['.text']=FuzzSection('.text',Flag.U|Flag.X|Flag.R)
        data_section=self.section['.data']=FuzzSection('.data',Flag.U|Flag.W|Flag.R)
        mtrap_section=self.section['.mtrap']=FuzzSection('.mtrap',Flag.X|Flag.R|Flag.W)
        strap_section=self.section['.strap']=FuzzSection('.strap',Flag.X|Flag.R|Flag.W)
        poc_section=self.section['.poc']=FuzzSection('.poc',Flag.U|Flag.X|Flag.R)

        inst_list, data_list = self.graph['mtrap'].gen_asm()
        mtrap_section.add_inst_list(inst_list)
        mtrap_section.add_inst_list(data_list)
        mtrap_section.add_global_label([self.graph['mtrap'].entry])

        inst_list, data_list = self.graph['strap'].gen_asm()
        strap_section.add_inst_list(inst_list)
        strap_section.add_inst_list(data_list)
        strap_section.add_global_label([self.graph['strap'].entry])

        inst_list, data_list = self.graph['decode'].gen_asm()
        poc_section.add_inst_list(inst_list)
        poc_section.add_inst_list(data_list)

        block_list = ['_init', 'run_time', 'decode_call', 'exit', 'delay', 'predict']
        if self.graph['predict'].predict_kind == 'branch_not_taken':
            block_list.extend(['return', 'encode'])
        else:
            block_list.extend(['encode', 'return'])

        for block_index in block_list:
            block = self.graph[block_index]
            inst_list, data_list = block.gen_asm()
            text_section.add_inst_list(inst_list)
            data_section.add_inst_list(data_list)
        text_section.add_global_label([self.graph['_init'].entry])

    def _distribute_address(self):
        offset = 0
        length = Page.size
        self.section['.mtrap'].get_bound(self.memory_bound[0][0] + offset, self.memory_bound[0][0] + offset, length)
        
        offset += length
        length = Page.size
        self.section['.strap'].get_bound(self.virtual_memory_bound[0][0] + offset, self.memory_bound[0][0] + offset , length)

        offset += length
        length = Page.size
        self.section['.text'].get_bound(self.virtual_memory_bound[0][0] + offset, self.memory_bound[0][0] + offset , length)

        offset += length
        length = Page.size
        self.section['.data'].get_bound(self.virtual_memory_bound[0][0] + offset, self.memory_bound[0][0] + offset , length)

        offset = 0
        length = Page.size
        self.section['.poc'].get_bound(self.virtual_memory_bound[1][0] + offset, self.memory_bound[1][0] + offset, length)
    
    def _write_headers(self,f,is_variant):
        header_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trans')
        filenames = os.listdir(header_dir)
        output_dirname = os.path.dirname(f.name)
        for file in filenames:
            if file.endswith('.h'):
                f.write(f'#include"{file}"\n')
                os.system(f"cp {header_dir}/{file} {output_dirname}/")
                

