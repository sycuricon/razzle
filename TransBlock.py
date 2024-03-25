import sys
import os
import random
from SectionUtils import *
sys.path.append(os.path.join(os.getcwd(),'razzle_transient/src'))
from razzle_transient.src.Instruction import *
from razzle_transient.src.MagicDevice import *
from razzle_transient.src.Block import *

class TransBlock:
    def __init__(self, extension, fuzz_param):
        self.name = fuzz_param['name']
        self.entry = self.name + '_entry'
        self.inst_list = []
        self.data_list = []
        self.extension = extension
        self.strategy = fuzz_param['strategy']
        assert self.strategy=='default' or self.strategy=='random', "strategy must be default or random"

    def _load_raw_asm(self,file_name):
        # file_name=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..',file_name)
        with open(file_name,"rt") as file:
            file_list = file.readlines()
        inst_list = [RawInstruction(line.strip()) for line in file_list]
        return inst_list

    def is_default(self):
        return self.strategy == 'default'
    
    def gen_instr(self, graph):
        match self.strategy:
            case 'default':
                self.gen_default(graph)
            case 'random':
                self.gen_random(graph)
            case _:
                raise "strategy must be default or random"
    
    def gen_random(self, graph):
        raise "Error: gen_random not implemented!"
    
    def gen_default(self, graph):
        raise "Error: gen_default not implemented!"

    def gen_asm(self):
        inst_asm_list = []
        inst_asm_list.append(f'{self.name}:\n')
        for item in self.inst_list:
            inst_asm_list.append(item.to_asm()+'\n')
        data_asm_list = []
        data_asm_list.append(f'{self.name}_data:\n')
        for item in self.data_list:
            data_asm_list.append(item.to_asm()+'\n')
        return inst_asm_list, data_asm_list

    def work(self):
        return len(self.extension) > 0

class InitBlock(TransBlock):
    def __init__(self, extension, fuzz_param):
        super().__init__(extension, fuzz_param)
        assert self.strategy == 'default', \
            f'strategy of {self.name} must be default rather than {self.strategy}'

    def gen_default(self, graph):
        self.inst_list.append(RawInstruction(f'{self.entry}:'))
        self.inst_list.extend(self._load_raw_asm("trans/_init.text.S"))
        self.data_list=self._load_raw_asm("trans/_init.data.S")

class TrapBlock(TransBlock):
    def __init__(self, extension, fuzz_param):
        super().__init__(extension, fuzz_param)
        assert self.strategy == 'default', \
            f'strategy of {self.name} must be default rather than {self.strategy}'
    
    def gen_default(self, graph):
        self.inst_list.append(RawInstruction(f'{self.entry}:'))
        self.inst_list.extend(self._load_raw_asm("trans/trap.text.S"))
        self.data_list=self._load_raw_asm("trans/trap.data.S")

class ReturnBlock(TransBlock):
    def __init__(self, extension, fuzz_param):
        super().__init__(extension, fuzz_param)
        assert self.strategy == 'default', \
            f'strategy of {self.name} must be default rather than {self.strategy}'

    def gen_default(self, graph):
        self.inst_list.append(RawInstruction(f'{self.entry}:'))
        self.inst_list.extend(self._load_raw_asm("trans/return.text.S"))
        self.data_list=self._load_raw_asm("trans/return.data.S")

class ExitBlock(TransBlock):
    def __init__(self, extension, fuzz_param):
        super().__init__(extension, fuzz_param)
        assert self.strategy == 'default', \
            f'strategy of {self.name} must be default rather than {self.strategy}'

    def gen_default(self, graph):
        self.inst_list.append(RawInstruction(f'{self.entry}:'))
        self.inst_list.extend(self._load_raw_asm("trans/exit.text.S"))
        self.data_list=self._load_raw_asm("trans/exit.data.S")

class EncodeBlock(TransBlock):
    def __init__(self, extension, fuzz_param):
        super().__init__(extension, fuzz_param)
        self.leak_kind = fuzz_param['leak_kind']
        assert self.leak_kind in ['cache', 'FPUport', 'LSUport'], \
            f"leak_kind must be 'cache', 'FPUport' or 'LSUport', rather than {self.leak_kind}"

    def gen_random(self, graph):
        raise "Error: gen_random not implemented!"
    
    def gen_default(self, graph):
        self.inst_list.append(RawInstruction(f'{self.entry}:'))
        match(self.leak_kind):
            case 'cache':
                self.inst_list.extend(self._load_raw_asm("trans/encode.cache.text.S"))
            case 'FPUport':
                self.inst_list.extend(self._load_raw_asm("trans/encode.FPUport.text.S"))
            case 'LSUport':
                self.inst_list.extend(self._load_raw_asm("trans/encode.LSUport.text.S"))
            case _:
                raise f"leak_kind must be 'cache', 'FPUport' or 'LSUport', rather than {self.leak_kind}"
        self.inst_list.append(RawInstruction(f"j {graph['return'].entry}"))

class DecodeBlock(TransBlock):
    def __init__(self, extension, fuzz_param):
        super().__init__(extension, fuzz_param)
        assert self.strategy == 'default', \
            f'strategy of {self.name} must be default rather than {self.strategy}'

    def gen_default(self, graph):
        encode_block = graph['encode']

        self.inst_list.append(RawInstruction(f'{self.entry}:'))
        match(encode_block.leak_kind):
            case 'cache':
                self.inst_list.extend(self._load_raw_asm("trans/decode.cache.text.S"))
            case 'FPUport'|'LSUport':
                self.inst_list.append(RawInstruction('ret'))
            case _:
                raise f"leak_kind must be 'cache', 'FPUport' or 'LSUport', rather than {encode_block.leak_kind}"

class DecodeCallBlock(TransBlock):
    def __init__(self, extension, fuzz_param):
        super().__init__(extension, fuzz_param)
        assert self.strategy == 'default', \
            f'strategy of {self.name} must be default rather than {self.strategy}'

    def gen_default(self, graph):
        self.inst_list.append(RawInstruction(f'{self.entry}:'))
        self.inst_list.extend(self._load_raw_asm("trans/decode_call.text.S"))
    
class DelayBlock(TransBlock):
    def __init__(self, extension, fuzz_param):
        super().__init__(extension, fuzz_param)
        self.float_rate = fuzz_param['float_rate']
        self.delay_len = fuzz_param['delay_len']

    def _gen_dep_list(self):
        self.GPR_list = [reg for reg in reg_range if reg not in ['A0','A1','ZERO','T0','T1']]
        self.FLOAT_list = float_range
        dep_list = []
        for i in range(random.randint(self.delay_len-1, self.delay_len+1)):
            if random.random() < self.float_rate:
                dep_list.append(random.choice(self.FLOAT_list))
            else:
                dep_list.append(random.choice(self.GPR_list))
        dep_list.append(random.choice(self.GPR_list))
        return dep_list
    
    def _gen_inst_list(self, dep_list):

        for i, src in enumerate(dep_list[0:-1]):
            dest = dep_list[i+1]
            if src in self.GPR_list and dest in self.FLOAT_list:
                self.inst_list.append(Instruction(f'fcvt.s.lu   {dest.lower()}, {src.lower()}'))
            elif src in self.FLOAT_list and dest in self.GPR_list:
                self.inst_list.append(Instruction(f'fcvt.lu.s   {dest.lower()}, {src.lower()}'))
            elif src in self.FLOAT_list and dest in self.FLOAT_list:
                while True:
                    instr = Instruction()
                    instr.set_extension_constraint([extension for extension in [\
                        'RV_D', 'RV64_D',\
                        'RV_F', 'RV64_F',\
                        'RV32_C_F', 'RV_C_D'\
                    ] if extension in self.extension])
                    instr.set_category_constraint(['FLOAT'])

                    def c_dest(name, frd):
                        return use_frd(name) and use_frs1(name) and frd == dest
                    instr.add_constraint(c_dest, ['NAME','FRD'])
                    instr.solve()

                    freg_list = [freg for freg in ['FRS1','FRS2','FRS3'] if instr.has(freg)]
                    for freg in freg_list:
                        if freg == src:
                            break
                    else:
                        instr[random.choice(freg_list)] = src

                    if instr.has('FRD'):
                        self.inst_list.append(instr)
                        break

            elif src in self.GPR_list and dest in self.GPR_list:
                while True:
                    instr = Instruction()
                    instr.set_extension_constraint([extension for extension in [\
                        'RV_M', 'RV64_M'
                    ] if extension in self.extension])
                    instr.set_category_constraint(['ARITHMETIC'])

                    def c_dest(name, rd):
                        return use_rs1(name) and rd == dest
                    instr.add_constraint(c_dest,['NAME', 'RD'])
                    instr.solve()

                    if instr.has('RS1') and instr['RS1'] != src:
                        if instr.has('RS2'):
                            if random.random() < 0.5:
                                instr['RS1'] = src
                            else:
                                instr['RS2'] = src
                        else:
                            instr['RS1'] = src

                    if instr.has('RS1') and instr['RS1'] not in self.GPR_list:
                        instr['RS1'] = random.choice(self.GPR_list)
                    if instr.has('RS2') and instr['RS2'] not in self.GPR_list:
                        instr['RS2'] = random.choice(self.GPR_list)

                    if instr.has('RD'):
                        self.inst_list.append(instr)
                        break
        
    
    def _gen_init_inst(self, dep_list):
        float_init_list = set()
        float_inited_list = set()
        GPR_init_list = set()
        GPR_inited_list = set()
        for dest_reg,inst in zip(dep_list, self.inst_list):
            # print(inst)

            if inst.has('FRS1'):
                if inst['FRS1'] not in float_inited_list:
                    float_init_list.add(inst['FRS1'])
            if inst.has('FRS2'):
                if inst['FRS2'] not in float_inited_list:
                    float_init_list.add(inst['FRS2'])
            if inst.has('FRS3'):
                if inst['FRS3'] not in float_inited_list:
                    float_init_list.add(inst['FRS3'])
            if inst.has('RS1'):
                if inst['RS1'] not in GPR_inited_list:
                    GPR_init_list.add(inst['RS1'])
            if inst.has('RS2'):
                if inst['RS2'] not in GPR_inited_list:
                    GPR_init_list.add(inst['RS2'])

            if dest_reg[0] == 'F':
                float_inited_list.add(dest_reg)
            else:
                GPR_inited_list.add(dest_reg)
        
        tmp_inst_list = []
        tmp_inst_list.append(RawInstruction(f'{self.entry}:'))
        tmp_inst_list.append(RawInstruction(f'la t1, delay_data_table'))
        self.data_list.append(RawInstruction('delay_data_table:'))
        for i,freg in enumerate(float_init_list):
            self.data_list.append(RawInstruction(f'.dword {random.randint(0, 2**64)}'))
            tmp_inst_list.append(RawInstruction(f'ld t0, {i*8}(t1)'))
            tmp_inst_list.append(RawInstruction(f'fcvt.s.lu   {freg.lower()}, t0'))
        for i,reg in enumerate(GPR_init_list):
            self.data_list.append(RawInstruction(f'.dword {random.randint(0, 2**64)}'))
            tmp_inst_list.append(RawInstruction(f'ld {reg.lower()}, {(i+len(float_init_list))*8}(t1)'))
        
        nop_line = 8 + 8 - (len(tmp_inst_list)) % 8
        for i in range(nop_line):
            tmp_inst_list.append(RawInstruction('nop'))

        tmp_inst_list.append(RawInstruction('INFO_DELAY_START'))
        self.inst_list = tmp_inst_list + self.inst_list
        self.inst_list.append(RawInstruction('INFO_DELAY_END'))

    def gen_random(self, graph):
        dep_list = self._gen_dep_list()
        self._gen_inst_list(dep_list)
        self._gen_init_inst(dep_list)
        dump_reg = inst_simlutor(self.inst_list, self.data_list)
        self.result_reg = dep_list[-1]
        self.result_imm = dump_reg[self.result_reg]

    def gen_default(self, graph):
        self.inst_list.append(RawInstruction(f'{self.entry}:'))
        self.inst_list.extend(self._load_raw_asm("trans/delay.text.S"))
        self.data_list=self._load_raw_asm("trans/delay.data.S")
        self.result_reg = 't0'.upper()
        self.result_imm = 0

class PredictBlock(TransBlock):
    def __init__(self, extension, fuzz_param):
        super().__init__(extension, fuzz_param)
        self.predict_kind = fuzz_param['predict_kind']

    def gen_random(self, graph):
        raise "Error: gen_random not implemented!"
    
    def gen_default(self, graph):
        # self.inst_list.append(RawInstruction(f'xor {self.result_reg.lower()}, {self.result_reg.lower()}, {self.result_reg.lower()}'))
        
        self.dep_reg = graph['delay'].result_reg
        self.dep_val = graph['delay'].result_imm
        encode_block = graph['encode']
        return_block = graph['return']
        delay_block = graph['delay']
        
        match(self.predict_kind):
            case 'call':
                self.inst_list.append(RawInstruction(f'{self.entry}:'))
                delay_link_inst = Instruction(f'add t0, {self.dep_reg.lower()}, a0')
                self.inst_list.append(delay_link_inst)
                call_inst = Instruction()
                call_inst.set_name_constraint(['JALR'])
                call_inst.set_category_constraint(['JUMP'])
                call_inst.set_extension_constraint(['RV_I'])
                def c_call(rd, rs1):
                    return rd == 'RA' and rs1 == 'T0'
                call_inst.add_constraint(c_call,['RD','RS1'],True)
                call_inst.solve()

                self.off_imm = call_inst['IMM']
                self.inst_list.append(call_inst)
            case 'return':
                self.inst_list.append(RawInstruction(f'{self.entry}:'))
                delay_link_inst = Instruction(f'add ra, {self.dep_reg}, a0')
                self.inst_list.append(delay_link_inst)
                ret_inst = Instruction()
                ret_inst.set_name_constraint(['JALR'])
                ret_inst.set_category_constraint(['JUMP'])
                ret_inst.set_extension_constraint(['RV_I'])
                ret_inst.set_imm_constraint(range(0,1))
                def c_ret(rd, rs1):
                    return rd == 'ZERO' and rs1 == 'RA'
                ret_inst.add_constraint(c_ret,['RD','RS1'],True)
                ret_inst.solve()

                self.off_imm = ret_inst['IMM']
                self.inst_list.append(ret_inst)
            case 'branch_taken'|'branch_not_taken':
                self.inst_list.append(RawInstruction(f'{self.entry}:'))
                ret_inst = Instruction()
                ret_inst.set_category_constraint(['BRANCH'])
                ret_inst.set_extension_constraint(['RV_I'])
                if self.predict_kind=='branch_taken':
                    ret_inst.set_label_constraint([return_block.entry])
                else:
                    ret_inst.set_label_constraint([encode_block.entry])
                def c_param(NAME,RS1,RS2):
                    return ((NAME in ['BLT','BGE'] and Unsigned2Signed(self.dep_val) != -2 ** (64 - 1) and Unsigned2Signed(self.dep_val) != 2 ** (64 - 1) - 1) \
                        or (NAME in ['BLTU','BGEU'] and self.dep_val != 0 and self.dep_val != 2 ** 64 - 1)\
                        or (NAME in ['BEQ','BNE'])) and RS1=='A0' and RS2==self.dep_reg
                ret_inst.add_constraint(c_param,['NAME','RS1','RS2'])
                ret_inst.solve()
            
                self.branch_kind=ret_inst['NAME']
                self.inst_list.append(ret_inst)
            case _:
                raise "Error: predict_kind not implemented!"

class RunTimeBlock(TransBlock):
    def __init__(self, extension, fuzz_param):
        super().__init__(extension, fuzz_param)
        self.train_loop = fuzz_param['train_loop']
        self.victim_loop = fuzz_param['victim_loop']
        # self.predict_kind = predict_kind
        # self.correct_block = correct_block
        # self.false_block = false_block
        # self.imm_param = imm_param
        # imm_param={'predict':predict_block.imm,\
        #            'delay':delay_block.result_imm,\
        #            'delay_reg':delay_block.result_reg,\
        #            'branch_kind':predict_block.branch_kind}
    
    def _gen_predict_param(self, graph):
        predict_block = graph['predict']
        encode_block = graph['encode']
        return_block = graph['return']
        delay_block = graph['delay']

        match(predict_block.predict_kind):
            case 'call' | 'return':
                train_param = f"{encode_block.entry} - {delay_block.result_imm} - {predict_block.off_imm}"
                victim_param = f"{return_block.entry} - {delay_block.result_imm} - {predict_block.off_imm}"
            case 'branch_taken'|'branch_not_taken':
                delay_imm = delay_block.result_imm
                match(predict_block.branch_kind):
                    case 'BEQ':
                        train_param = delay_imm + 1 if delay_imm == 0 else delay_imm - 1
                        victim_param = delay_imm
                    case 'BNE':
                        train_param = delay_imm
                        victim_param = delay_imm + 1 if delay_imm == 0 else delay_imm - 1
                    case 'BLT':
                        delay_imm = Unsigned2Signed(delay_imm)
                        assert(delay_imm!=-2 ** (64 - 1) and delay_imm!=2 ** (64 - 1) - 1)
                        train_param = random.randint(delay_imm, 2 ** (64 - 1))
                        victim_param = random.randint(-2 ** (64 - 1), delay_imm)
                    case 'BGE':
                        delay_imm = Unsigned2Signed(delay_imm)
                        assert(delay_imm!=-2 ** (64 - 1) and delay_imm!=2 ** (64 - 1) - 1)
                        train_param = random.randint(-2 ** (64 - 1), delay_imm)
                        victim_param = random.randint(delay_imm, 2 ** (64 - 1))
                    case 'BLTU':
                        assert(delay_imm!=0 and delay_imm!=2**64-1)
                        train_param = random.randint(delay_imm, 2 ** 64)
                        victim_param = random.randint(0, delay_imm)
                    case 'BGEU':
                        assert(delay_imm!=0 and delay_imm!=2**64-1)
                        train_param = random.randint(0, delay_imm)
                        victim_param = random.randint(delay_imm, 2 ** 64)
                    case _:
                        raise f"Error: branch_kind {predict_block.branch_kind} not implemented!"

                if predict_block.predict_kind == 'branch_not_taken':
                    train_param, victim_param = victim_param, train_param
            case _:
                raise "Error: predict_kind not implemented!"
        return victim_param, train_param
    
    def _gen_data_list(self, victim_predict_param, victim_offset_param, train_predict_param, train_offset_param, graph):
        delay_block = graph['delay']

        self.data_list.append(RawInstruction('train_param_table:'))
        for i in range(self.train_loop):
            self.data_list.append(RawInstruction(f'train_predict_param_{i}:'))
            self.data_list.append(RawInstruction(f'.dword {train_predict_param}'))
            self.data_list.append(RawInstruction(f'train_offset_param_{i}:'))
            self.data_list.append(RawInstruction(f'.dword {train_offset_param}'))
            self.data_list.append(RawInstruction(f'train_delay_value_{i}:'))
            self.data_list.append(RawInstruction(f".dword {delay_block.result_imm}"))
        self.data_list.append(RawInstruction('victim_param_table:'))
        for i in range(self.victim_loop):
            self.data_list.append(RawInstruction(f'victim_predict_param_{i}:'))
            self.data_list.append(RawInstruction(f'.dword {victim_predict_param}'))
            self.data_list.append(RawInstruction(f'victim_offset_param_{i}:'))
            self.data_list.append(RawInstruction(f'.dword {victim_offset_param}'))

    def _gen_inst_list(self, graph):
        delay_block = graph['delay']
        predict_block = graph['predict']

        self.inst_list.append(RawInstruction(f'{self.entry}:'))
        for i in range(self.train_loop):
            table_width = 3
            self.inst_list.append(RawInstruction(f'la t0, train_{i}_end'))
            self.inst_list.append(RawInstruction('la t1, store_ra'))
            self.inst_list.append(RawInstruction('sd t0, 0(t1)'))
            self.inst_list.append(RawInstruction('la t0, train_param_table'))
            self.inst_list.append(RawInstruction(f'ld a0, {i*8*table_width}(t0)'))
            self.inst_list.append(RawInstruction(f'ld a1, {i*8*table_width+8}(t0)'))
            self.inst_list.append(RawInstruction(f"ld {delay_block.result_reg.lower()}, {i*8*table_width+16}(t0)"))
            self.inst_list.append(RawInstruction('INFO_TRAIN_START'))
            self.inst_list.append(RawInstruction(f'j {predict_block.entry}'))
            self.inst_list.append(RawInstruction(f'train_{i}_end:'))
            self.inst_list.append(RawInstruction('INFO_TRAIN_END'))
        
        for i in range(self.victim_loop):
            table_width = 2
            self.inst_list.append(RawInstruction(f'la t0, victim_{i}_end'))
            self.inst_list.append(RawInstruction('la t1, store_ra'))
            self.inst_list.append(RawInstruction('sd t0, 0(t1)'))
            self.inst_list.append(RawInstruction('la t0, victim_param_table'))
            self.inst_list.append(RawInstruction(f'ld a0, {i*8*table_width}(t0)'))
            self.inst_list.append(RawInstruction(f'ld a1, {i*8*table_width+8}(t0)'))
            self.inst_list.append(RawInstruction('INFO_VCTM_START'))
            self.inst_list.append(RawInstruction(f'j {delay_block.entry}'))
            self.inst_list.append(RawInstruction(f'victim_{i}_end:'))
            self.inst_list.append(RawInstruction('INFO_VCTM_END'))

    def gen_random(self, graph):
        raise "Error: gen_random not implemented!"
    
    def gen_default(self, graph):
        victim_predict_param, train_predict_param = self._gen_predict_param(graph)
        train_offset_param = 0
        victim_offset_param = "secret + LEAK_TARGET - trapoline"

        self._gen_data_list(victim_predict_param, victim_offset_param, train_predict_param, train_offset_param, graph)
        self._gen_inst_list(graph)
        
def inst_simlutor(inst_list, data_list):
    file_name = 'inst_sim/Testcase.S'
    with open(file_name, 'wt') as file:
        file.write('#include"../trans/boom_conf.h"\n')
        file.write('#include"../trans/encoding.h"\n')
        file.write('#include"../trans/parafuzz.h"\n')
        file.write('#include"../trans/util.h"\n')
        file.write('.section .text\n')
        file.write(f'li t0, 0x8000000a00007800\n')
        file.write('csrw mstatus, t0\n')
        for inst in inst_list:
            file.write(inst.to_asm())
            file.write('\n')
        file.write('.section .data\n')
        for data in data_list:
            file.write(data.to_asm())
            file.write('\n')
    os.system('make -C inst_sim sim')
    with open("inst_sim/dump","rt") as file:
        reg_lines = file.readlines()
        dump_reg = {}
        for reg_line in reg_lines:
            key,value = reg_line.strip().split()
            dump_reg[key]=int(value,base=16)
        # print(dump_reg)
    return dump_reg



    
    

    



