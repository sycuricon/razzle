from Instruction import *
from MagicDevice import *

class TransBlock:
    def __init__(self, name, extension, default):
        self.name = name
        self.inst_list = []
        self.data_list = []
        self.extension = extension
        self.default = default

    def _load_raw_asm(self,file_name):
        file_name=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..',file_name)
        with open(file_name,"rt") as file:
            file_list = file.readlines()
        inst_list = [RawInstruction(line.strip()) for line in file_list]
        return inst_list

    def is_default(self):
        return self.default
    
    def need_store(self):
        if self.default:
            return {'t0', 't1'}
        else:
            rd_list = set()
            for inst in self.inst_list:
                if inst.has('RD'):
                    rd_list.add(inst['RD'])
            return rd_list
    
    def gen_instr(self):
        print("Error: gen_instr not implemented!")
        exit(0)
    
    def gen_default(self):
        print("Error: gen_default not implemented!")
        exit(0)

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

class TrapBlock(TransBlock):
    def __init__(self, name, extension, default):
        assert(default == True)
        super().__init__(name, extension, default)
    
    def gen_default(self):
        self.inst_list=self._load_raw_asm("env/trans/trap.text.S")
        self.data_list=self._load_raw_asm("env/trans/trap.data.S")

class FunctionBeginBlock(TransBlock):
    def __init__(self, name, extension, default):
        assert(default == True)
        super().__init__(name, extension, default)
        self.store_reg={'ra','fp'}
    
    def register_store(self,reg_name):
        self.store_reg |= reg_name

    def gen_default(self):
        store_reg=list(self.store_reg)
        store_reg.sort()
        self.inst_list.append(RawInstruction(f'addi sp, sp, {-len(store_reg)*8}'))
        for i,reg in enumerate(store_reg):
            self.inst_list.append(RawInstruction(f'sd {reg}, {i*8}(sp)'))
        self.inst_list.append(RawInstruction(f'addi fp, sp, {len(store_reg)*8}'))

class FunctionEndBlock(TransBlock):
    def __init__(self, name, extension, default):
        assert(default == True)
        super().__init__(name, extension, default)
        self.load_reg={'ra','fp'}
    
    def register_load(self,reg_name):
        self.load_reg |= reg_name

    def gen_default(self):
        load_reg=list(self.load_reg)
        load_reg.sort()
        for i,reg in enumerate(load_reg):
            self.inst_list.append(RawInstruction(f'ld {reg}, {i*8}(sp)'))
        self.inst_list.append(RawInstruction(f'addi sp, sp, {len(load_reg)*8}'))
        self.inst_list.append(RawInstruction('ret'))

class ExitBlock(TransBlock):
    def __init__(self, name, extension, default):
        assert(default == True)
        super().__init__(name, extension, default)

    def gen_default(self):
        self.inst_list=self._load_raw_asm("env/trans/exit.text.S")
        self.data_list=self._load_raw_asm("env/trans/exit.data.S")

class PocFuncBlock(TransBlock):
    def __init__(self, name, extension, default):
        assert(default == True)
        super().__init__(name, extension, default)

    def gen_default(self):
        self.inst_list=self._load_raw_asm("env/trans/poc_func.text.S")
    
class DelayBlock(TransBlock):
    def __init__(self, name, extension, default):
        super().__init__(name, extension, default)

    def gen_instr(self):
        print("Error: gen_instr not implemented!")
        exit(0)
    
    def gen_default(self):
        self.inst_list=self._load_raw_asm("env/trans/delay.text.S")
        self.data_list=self._load_raw_asm("env/trans/delay.data.S")
        self.result_reg = 't0'.upper()
        self.result_imm = 0
    
    def get_result_reg(self):
        return self.result_reg

class PocBlock(TransBlock):
    def __init__(self, name, extension, default):
        assert(default == True)
        super().__init__(name, extension, default)

    def gen_default(self):
        self.inst_list=self._load_raw_asm("env/trans/poc.text.S")
    
class VictimBlock(TransBlock):
    def __init__(self, name, extension, default, predict_block):
        super().__init__(name, extension, default)
        self.predict_block=predict_block

    def gen_instr(self):
        print("Error: gen_instr not implemented!")
        exit(0)
    
    def gen_default(self):
        self.inst_list=self._load_raw_asm("env/trans/victim.text.S")
        self.inst_list.append(RawInstruction(f'j {self.predict_block}'))

class InitSecretBlock(TransBlock):
    def __init__(self, name, extension, default):
        assert(default == True)
        super().__init__(name, extension, default)

    def gen_default(self):
        self.inst_list=self._load_raw_asm("env/trans/init_secret.text.S")
        self.data_list=self._load_raw_asm("env/trans/init_secret.data.S")

class PredictBlock(TransBlock):
    def __init__(self, name, extension, default, result_reg, predict_kind, correct_block):
        super().__init__(name, extension, default)
        self.result_reg = result_reg
        self.predict_kind = predict_kind
        self.correct_block = correct_block
        self.imm = 0

    def gen_instr(self):
        print("Error: gen_instr not implemented!")
        exit(0)
    
    def gen_default(self):
        match(self.predict_kind):
            case 'call':
                delay_link_inst = Instruction(f'add t0, {self.result_reg}, a0')
                self.inst_list.append(delay_link_inst)
                call_inst = Instruction()
                call_inst.set_name_constraint(['JALR'])
                call_inst.set_category_constraint(['JUMP'])
                call_inst.set_extension_constraint(['RV_I'])
                def c_call(rd, rs1):
                    return rd == 'RA' and rs1 == 'T0'
                call_inst.add_constraint(c_call,['RD','RS1'],True)
                call_inst.solve()

                self.imm = call_inst['IMM']
                self.inst_list.append(call_inst)
            case 'return':
                delay_link_inst = Instruction(f'add ra, {self.result_reg}, a0')
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

                self.imm = ret_inst['IMM']
                self.inst_list.append(ret_inst)
            case 'branch':
                self.data_list.append(RawInstruction('predict_imm:'))
            case _:
                print("Error: predict_kind not implemented!")
                exit(0)

class TrainBlock(TransBlock):
    def __init__(self, name, extension, default, predict_kind, correct_block, false_block, imm_param):
        super().__init__(name, extension, default)
        self.predict_kind = predict_kind
        self.correct_block = correct_block
        self.false_block = false_block
        self.imm_param = imm_param
        
    def gen_instr(self):
        print("Error: gen_instr not implemented!")
        exit(0)
    
    def gen_default(self):
        match(self.predict_kind):
            case 'call' | 'return':
                false_predict_param = f"{self.false_block} - {self.imm_param['delay']} - {self.imm_param['predict']}"
                false_offset_param = 0
                true_predict_param = f"{self.correct_block} - {self.imm_param['delay']} - {self.imm_param['predict']}"
                true_offset_param = 0
                self.data_list.append(RawInstruction('param_table:'))
                for i in range(4):
                    self.data_list.append(RawInstruction(f'.dword {false_predict_param}'))
                    self.data_list.append(RawInstruction(f'.dword {false_offset_param}'))
                self.data_list.append(RawInstruction(f'.dword {true_predict_param}'))
                self.data_list.append(RawInstruction(f'.dword {true_offset_param}'))
                self.inst_list=self._load_raw_asm("env/trans/train.text.S")
            case _:
                print("Error: predict_kind not implemented!")
                exit(0)
        
    

    



