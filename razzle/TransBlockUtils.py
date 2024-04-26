import os
import random
import sys
from BuildManager import *
from SectionUtils import *
from SectionManager import *

from payload.Instruction import *
from payload.MagicDevice import *
from payload.Block import *

class BaseBlock:
    def __init__(self, name, extension, mutate):
        self.name = name
        self.extension = extension
        self.mutate = mutate
        
        self.inst_list = []
        self.previous = []
        self.succeed = []

        self.previous_inited = set()
        self.need_inited = set()
        self.succeed_inited = set()

    def _gen_int_arithmetic(self):
        extension = [extension_i for extension_i in [
            'RV64_C', 'RV64_M', 'RV64_I', 'RV_M', 'RV_I', 'RV_C'] if extension_i in self.extension]
        instr = rand_instr(instr_extension=extension, instr_category=['ARITHMETIC'])
        def instr_c_name(name):
            return name not in ['LA']
        instr.add_constraint(instr_c_name,['NAME'])
        instr.solve()
        return [instr]
    
    def _gen_load_address(self):
        instr_la = Instruction()
        instr_la.set_label_constraint(['random_data_block_page_base'])
        instr_la.set_name_constraint(['LA'])
        instr_la.solve()
        return instr_la
    
    def _gen_load_store(self):
        extension = [extension_i for extension_i in [
            'RV_I', 'RV64_I', 'RV_D', 'RV64_D', 'RV_F', 'RV64_F',
            'RV_C', 'RV32_C', 'RV64_C', 'RV32_C_F', 'RV_C_D'] if extension_i in self.extension]
        instr_la = self._gen_load_address()

        rd = instr_la['RD']
        def instr_c_reg(reg):
            return reg == rd
        instr = rand_instr(instr_extension=extension, instr_category=[
            'LOAD', 'STORE', 'FLOAT_LOAD', 'FLOAT_STORE'], imm_range=range(-0x800, 0x7ff))
        instr.add_constraint(instr_c_reg, ['RS1'])
        instr.solve()
        instr['IMM'] = down_align(instr['IMM'], 8)

        return [instr_la, instr]

    def _gen_atomic(self):
        extension = [extension_i for extension_i in ['RV_A', 'RV64_A'] if extension_i in self.extension]
        instr_la = self._gen_load_address()
        
        instr_off = Instruction()
        instr_off.set_name_constraint(['ADDI'])
        offset = random.randint(-0x800, 0x7ff)
        offset = down_align(offset, 8)
        instr_off.set_imm_constraint(range(offset, offset+1))
        rd = instr_la['RD']
        def c_rd_rd1(r1, r2):
            return r1 == rd and r2 == rd
        instr_off.add_constraint(c_rd_rd1, ['RD', 'RS1'])
        instr_off.solve()

        def reg_c(rs1):
            return rs1 == rd
        instr_amo = rand_instr(instr_extension=extension, instr_category=['AMO'])
        instr_amo.add_constraint(reg_c, ['RS1'])
        instr_amo.solve()

        return [instr_la, instr_off, instr_amo]
    
    def _gen_float_arithmetic(self):
        extension = [extension for extension in [
            'RV_D', 'RV64_D',
            'RV_F', 'RV64_F',
            'RV32_C_F', 'RV_C_D'
        ] if extension in self.extension]

        instr = rand_instr(instr_extension=extension,instr_category=['FLOAT'])
        instr.solve()

        return [instr]

    def _gen_csr(self):
        extension = [extension for extension in [
            'RV_ZICSR'] if extension in self.extension]

        instr = rand_instr(instr_extension=extension,
                           instr_category=['CSR'])
        instr.solve()

        return [instr]
    
    def _gen_system(self):
        extension = [extension for extension in [
            'RV_I', 'RV64_I'] if extension in self.extension]
        instr = rand_instr(instr_extension=extension,
                           instr_category=['SYSTEM', 'SYNCH'])
        instr.solve()
        return [instr]

    def compute_succeed_inited(self):
        if not self.mutate:
            return
        dest = ['RD', 'FRD']
        src  = ['RS1', 'RS2', 'FRS1', 'FRS2', 'FRS3']
        for inst in self.inst_list:
            for field in src:
                if inst.has(field):
                    reg = inst[field]
                    if reg not in self.succeed_inited:
                        self.need_inited.add(reg)
                    self.succeed_inited.add(reg)
            
            for field in dest:
                if inst.has(field):
                    self.succeed_inited.add(inst[field])
            

    def compute_need_inited(self):
        iter_valid = False

        previous_inited = set()
        if len(self.previous) != 0:
            previous_inited = self.previous[0].succeed_inited
            for block in self.previous[1:]:
                previous_inited.intersection_update(block.succeed_inited)

        if len(self.previous_inited) < len(previous_inited):
            iter_valid = True
            self.previous_inited = previous_inited
            self.succeed_inited.update(previous_inited)
            if self.mutate:
                self.need_inited.difference_update(self.previous_inited)
        
        return iter_valid

    def add_previous(self, node):
        self.previous.append(node)
        node.succeed.append(self)
    
    def add_succeed(self, node):
        self.succeed.append(node)
        node.previous.append(self)

    def gen_asm(self):
        str_list = []
        str_list.append(f'{self.name}:\n')
        for inst in self.inst_list:
            str_list.append(inst.to_asm()+'\n')
        return str_list
    
    def get_inst_len(self):
        return len(self.inst_list)

class RandomBlock(BaseBlock):
    def __init__(self, name, extension):
        super().__init__(name, extension, True)
        self.gen_func = [
            BaseBlock._gen_atomic,
            BaseBlock._gen_float_arithmetic,
            BaseBlock._gen_float_arithmetic,
            BaseBlock._gen_int_arithmetic,
            BaseBlock._gen_int_arithmetic,
            BaseBlock._gen_load_store,
        ]

    def gen_instr(self):
        for _ in range(random.randint(3,6)):
            gen_func = random.choice(self.gen_func)
            self.inst_list.extend(gen_func(self))
            if len(self.inst_list) >= 6:
                break

class TransBlock:
    def __init__(self, name, extension, output_path):
        self.name = name
        self.entry = self.name + "_entry"
        self.inst_block_list = []
        self.data_list = []
        self.extension = extension
        self.baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]},
            os.path.join(output_path, self.name),
        )

    def _load_inst_file(self, file_name, mutate = False):
        file_list_format = self._load_file_asm(file_name)
        self._load_inst_str(file_list_format, mutate)
    
    def _load_data_file(self, file_name):
        file_list_format = self._load_file_asm(file_name)
        self._load_data_str(file_list_format)

    def _load_file_asm(self, file_name):
        with open(file_name, "rt") as file:
            file_list = file.readlines()
        
        file_list_format = []
        for line in file_list:
            line = line.strip()
            if line == '':
                continue
            if line.startswith('//'):
                continue
            file_list_format.append(line)
        
        return file_list_format

    def _load_inst_str(self, str_list, mutate=False):
        if str_list[0].endswith(':'):
            block = BaseBlock(str_list[0][0:-1], self.extension, mutate)
            str_list.pop(0)
        else:
            block = BaseBlock(self.entry, self.extension, mutate)

        for line in str_list:
            if line.endswith(':'):
                self._add_inst_block(block)
                block = BaseBlock(line[0:-1], self.extension, mutate)
                continue
            
            if block.mutate:
                block.inst_list.append(Instruction(line))
            else:
                block.inst_list.append(RawInstruction(line))

        self._add_inst_block(block)
    
    def _load_data_str(self, str_list):
        for line in str_list:
            self.data_list.append(RawInstruction(line))
    
    def _add_inst_block(self, block):
        if len(self.inst_block_list) != 0:
            self.inst_block_list[-1].add_succeed(block)
        self.inst_block_list.append(block)
    
    def _add_inst_block_list(self, block_list):
        if len(self.inst_block_list) != 0:
            self.inst_block_list[-1].add_succeed(block_list[0])
        self.inst_block_list.extend(block_list)
    
    def _compute_need_inited(self):
        for block in self.inst_block_list:
            block.compute_succeed_inited()
        
        iter_valid = True
        while iter_valid:
            iter_valid = False
            for block in self.inst_block_list:
                iter_valid = iter_valid or block.compute_need_inited() 

        self.need_inited = set()
        for block in self.inst_block_list:
            self.need_inited.update(block.need_inited)
        self.succeed_inited = self.inst_block_list[-1].succeed_inited
    
    def _inited_posted_process(self, previous_inited):
        self.need_inited = self.need_inited - previous_inited
        self.succeed_inited.update(previous_inited)
    
    def _get_inst_len(self):
        inst_len = 0
        for block in self.inst_block_list:
            inst_len += block.get_inst_len()
        return inst_len
    
    def gen_instr(self):
        pass

    def instr_mutate(self):
        pass
    
    def _gen_random(self, block_cnt=3):
        block_list = []
        for i in range(block_cnt):
            block = RandomBlock(f'{self.name}_{i}', self.extension, self.transient)
            block.gen_instr()
            block_list.append(block)

        start_p = 0
        while(start_p + 2 < block_cnt - 1):
            end_p = random.randint(start_p + 2, block_cnt -2)
            block_list[start_p].inst_list.extend(new_branch_to(self.extension,block_list[end_p].name))
            block_list[end_p].inst_list.extend(new_jump_to(block_list[start_p + 1].name))
            block_list[end_p -1].inst_list.extend(new_jump_to(block_list[end_p + 1].name))

            block_list[start_p].add_succeed(block_list[end_p])
            block_list[start_p].add_succeed(block_list[start_p + 1])
            block_list[end_p].add_succeed(block_list[start_p + 1])
            for i in range(start_p + 1, end_p - 1):
                block_list[i].add_succeed(block_list[i+1])
            block_list[end_p - 1].add_succeed(block_list[end_p + 1])

            start_p = end_p + 1

        for i in range(start_p, len(block_list)-1):
            block_list[i].add_succeed(block_list[i+1])

        return block_list

    def gen_asm(self):
        inst_asm_list = []
        inst_asm_list.append(f"{self.name}:\n")
        for block in self.inst_block_list:
            inst_asm_list.extend(block.gen_asm())
            inst_asm_list.append('\n')

        data_asm_list = []
        data_asm_list.append(f"{self.name}_data:\n")
        for item in self.data_list:
            data_asm_list.append(item.to_asm() + "\n")
        return inst_asm_list, data_asm_list

    def work(self):
        return len(self.extension) > 0

class TransBaseManager(SectionManager):
    def __init__(self, config, extension, victim_privilege, virtual, output_path):
        super().__init__(config)
        self.extension = extension
        self.victim_privilege = victim_privilege
        self.virtual = virtual
        self.output_path = output_path
    
    def gen_block(self):
        raise "gen_block has not been implemented!!!"
    
    def _set_section(self, text_section, data_section, block_list):
        for block in block_list:
            inst_list, data_list = block.gen_asm()
            text_section.add_inst_list(inst_list)
            data_section.add_inst_list(data_list)
    
    def _distribute_address(self):
        offset = 0
        length = Page.size
        self.section[".text_swap"].get_bound(
            self.virtual_memory_bound[0][0] + offset, self.memory_bound[0][0] + offset, length
        )
    
    def add_symbol_table(self, symbol_table_file):
        self.symbol_table = get_symbol_file(symbol_table_file)
    
    def register_swap_idx(self, swap_idx):
        self.swap_idx = swap_idx

class FuzzSection(Section):
    def __init__(self, name, flag):
        super().__init__(name, flag)
        self.inst_list = []

    def add_inst_list(self, list):
        self.inst_list.extend(list)
        self.inst_list.append("\n")

    def _generate_body(self):
        return self.inst_list

def inst_simlutor(baker, inst_block_list_list, data_list_list):
    if not os.path.exists(baker.output_path):
        os.makedirs(baker.output_path)

    file_name = os.path.join(baker.output_path, "tmp.S")
    with open(file_name, "wt") as file:
        file.write('#include "boom_conf.h"\n')
        file.write('#include "encoding.h"\n')
        file.write('#include "parafuzz.h"\n')
        file.write(".section .text\n")
        file.write(f"li t0, 0x8000000a00007800\n")
        file.write("csrw mstatus, t0\n")
        for inst_block_list in inst_block_list_list:
            for block in inst_block_list:
                file.writelines(block.gen_asm())
                file.write("\n")
        file.write(".section .data\n")
        for data_list in data_list_list:
            for data in data_list:
                file.write(data.to_asm())
                file.write("\n")

    gen_elf = ShellCommand(
        "riscv64-unknown-elf-gcc",
        [
            "-march=rv64gc_zicsr",
            "-mabi=lp64f",
            "-mcmodel=medany",
            "-nostdlib",
            "-nostartfiles",
            "-I$RAZZLE_ROOT/template",
            "-I$RAZZLE_ROOT/template/trans",
            "-T$RAZZLE_ROOT/template/tmp/link.ld",
        ],
    )
    baker.add_cmd(gen_elf.save_cmd([file_name, "-o", "$OUTPUT_PATH/tmp"]))

    inst_cnt = ShellCommand(
        "riscv64-unknown-elf-objdump",
        ["-d", "$OUTPUT_PATH/tmp", "| grep -cE '^[[:space:]]+'"],
    )
    baker.add_cmd(inst_cnt.save_output("INST_CNT"))

    gen_dump = ShellCommand(
        "spike-solve", ["$OUTPUT_PATH/tmp", "$INST_CNT", "$OUTPUT_PATH/dump"]
    )
    baker.add_cmd(gen_dump.save_cmd())
    baker.run()

    with open(os.path.join(baker.output_path, "dump"), "rt") as file:
        reg_lines = file.readlines()
        dump_reg = {}
        for reg_line in reg_lines:
            key, value = reg_line.strip().split()
            dump_reg[key] = int(value, base=16)
        # print(dump_reg)
    return dump_reg