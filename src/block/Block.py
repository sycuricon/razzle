from MagicDevice import *
import Config

def use_rs1(name):
    return 'RS1' in all_instructions[name]['variables']

def use_rs2(name):
    return 'RS2' in all_instructions[name]['variables']

def use_frd(name):
    return 'FRD' in all_instructions[name]['variables']

def use_frs1(name):
    return 'FRS1' in all_instructions[name]['variables']

def use_frs2(name):
    return 'FRS2' in all_instructions[name]['variables']

def use_frs3(name):
    return 'FRS3' in all_instructions[name]['variables']


def rand_instr(instr_name=None, instr_extension=None, instr_category=None, imm_range=None):
    instr = Instruction()

    if instr_name is not None:
        instr.set_name_constraint(instr_name)

    if instr_extension is not None:
        instr.set_extension_constraint(instr_extension)

    if instr_category is not None:
        instr.set_category_constraint(instr_category)

    if imm_range is not None:
        instr.set_imm_constraint(imm_range)

    return instr


class RiscvInstrBlock:
    def __init__(self, name, extension):
        self.name = name
        self.instr_list = []
        self.out_instr = None
        self.extension = extension

    def gen_instr(self):
        print("Error: gen_instr not implemented!")
        exit(0)

    def work(self):
        return len(self.extension) > 0


class IntArithmeticBlock(RiscvInstrBlock):
    def __init__(self, name, extension):
        super().__init__(name, extension)
        self.extension = [extension_i for extension_i in [
            'RV64_C', 'RV64_M', 'RV64_I', 'RV_M', 'RV_I', 'RV_C'] if extension_i in self.extension]

    def gen_instr(self):

        reg_c = []
        reg_magic = list(get_magic_reg('MAGIC_RDM_WORD')) + \
            list(get_magic_reg('MAGIC_RANDOM'))
        for _ in range(random.randint(8, 12)):
            instr = rand_instr(instr_extension=self.extension,
                               instr_category=['ARITHMETIC'])

            def instr_c_reg(name, src1, src2):
                return src1 in reg_c or (src1 in reg_magic) \
                    or (use_rs2(name) and (src2 in reg_c or (src2 in reg_magic)))

            if not (len(reg_c) == 0 and len(reg_magic) == 0):
                instr.add_constraint(instr_c_reg, ['NAME', 'RS1', 'RS2'])
            instr.solve()
            if Config.DETAIL:
                instr.comment = f"magic_reg = {list(reg_magic)}, reg_c = {list(reg_c)}"
            self.instr_list.append(instr)
            if instr.has('RD'):
                reg_c.append(instr['RD'])
            if len(reg_c) > 4:
                reg_c.pop(0)


# la rd0, <base>
# ld rd1, offset(rd0)
# or
# st rd1 offset(rd0)
# ld rd1 offset(rd0)
class LoadStoreBlock(RiscvInstrBlock):
    def __init__(self, name, extension, base_addr, offrange):
        super().__init__(name, extension)
        self.base_addr = base_addr
        self.offrange = offrange
        self.extension = [extension_i for extension_i in [
            'RV_I', 'RV64_I', 'RV_D', 'RV64_D', 'RV_F', 'RV64_F',
            'RV_C', 'RV32_C', 'RV64_C', 'RV32_C_F', 'RV_C_D'] if extension_i in self.extension]

    def gen_instr(self):
        instr_la = load_from_magic_device(
            type='DATA_ADDR', label=self.base_addr)
        instr_la.protect = True
        self.instr_list.append(instr_la)

        rd = instr_la['RD']

        def instr_c_reg(reg):
            return reg == rd

        instr = rand_instr(instr_extension=self.extension, instr_category=[
            'LOAD', 'STORE', 'FLOAT_LOAD', 'FLOAT_STORE'], imm_range=range(0x0, self.offrange))
        instr.add_constraint(instr_c_reg, ['RS1'])

        instr.solve()

        instr.protect = True
        self.instr_list.append(instr)
        if instr['CATEGORY'] in ['STORE', 'FLOAT_STORE']:
            new_imm = instr['IMM']
            instr = rand_instr(instr_category=['LOAD', 'FLOAT_LOAD'])

            new_extension = self.extension
            for extension in ['RV_C', 'RV32_C', 'RV64_C', 'RV32_C_F', 'RV_C_D']:
                if extension in new_extension:
                    new_extension.remove(extension)
            if len(new_extension) > 0:
                instr.add_constraint(instr_c_reg, ['RS1'])
                instr.set_extension_constraint(new_extension)
                instr.set_imm_constraint(range(new_imm, new_imm + 1))
                instr.solve()
                instr.protect = True
                self.instr_list.append(instr)


class PteBlock(RiscvInstrBlock):
    def __init__(self, name, extension, vm, page_range):
        super().__init__(name, extension)
        self.page_range = page_range
        self.extension = [extension_i for extension_i in [
            'RV_I', 'RV64_I', 'RV_D', 'RV64_D', 'RV_F', 'RV64_F',
            'RV_C', 'RV32_C', 'RV64_C', 'RV32_C_F', 'RV_C_D'] if extension_i in self.extension] if vm else []

    def gen_instr(self):
        target = random.randint(self.page_range.start,
                                self.page_range.stop) << 12
        instr_li = rand_instr(
            instr_name="LI", imm_range=range(target, target + 1))
        instr_li.solve()
        instr_ld = rand_instr(instr_category=[
                              'LOAD', 'FLOAT_LOAD', 'STORE', 'FLOAT_STORE'], instr_extension=self.extension, imm_range=range(0, 0x1000))

        def c_rs1(rs1): return rs1 == instr_li['RD']
        instr_ld.add_constraint(c_rs1, ['RS1'])
        instr_ld.solve()
        self.instr_list.append(instr_li)
        self.instr_list.append(instr_ld)


class AmoBlock(RiscvInstrBlock):
    def __init__(self, name, extension, base_addr):
        super().__init__(name, extension)
        self.base_addr = base_addr
        self.extension = [extension_i for extension_i in [
            'RV_A', 'RV64_A'] if extension_i in self.extension]

    def gen_instr(self):
        offset = random.randint(-2048, 2047)
        if random.randint(0, 1) == 1:
            offset = offset // 4 * 4

        instr_la = load_from_magic_device(
            type='DATA_ADDR', label=self.base_addr)
        instr_la.protect = True
        self.instr_list.append(instr_la)
        rd = instr_la['RD']

        instr_add = rand_instr(instr_name=['ADDI'])

        def c_rd_rd1(r1, r2):
            return r1 == rd and r2 == rd

        instr_add.add_constraint(c_rd_rd1, ['RD', 'RS1'])
        instr_add.set_imm_constraint(range(offset, offset + 1))
        instr_add.solve()
        self.instr_list.append(instr_add)

        def reg_c(rs1):
            return rs1 == rd

        def reg_c_rd(instr_rd):
            return instr_rd != rd

        if random.randint(0, 1) == 0:  # lr & sc protect need update
            instr = rand_instr(instr_extension=self.extension,
                               instr_category=["AMO_LOAD"])
            instr.add_constraint(reg_c, ['RS1'])
            instr.add_constraint(reg_c_rd, ['RD'])
            instr.solve()
            lr_name = instr['NAME']
            self.instr_list.append(instr)

            instr = rand_instr(
                instr_name=['SC.W' if lr_name == 'LR.W' else 'SC.D'])
            instr.add_constraint(reg_c, ['RS1'])
            instr.solve()
            self.instr_list.append(instr)
        else:
            for _ in range(3):
                instr = rand_instr(instr_category=['AMO'])
                instr.add_constraint(reg_c, ['RS1'])
                instr.add_constraint(reg_c_rd, ['RD'])
                instr.solve()
                self.instr_list.append(instr)
        self.instr_list[-1].protect = True


# li rd0, <frm>
# fsrm rd1, rd0
# fsflags rd, zero
# finst
# frflags rd2
# fclass rd3


class FloatArithmeticBlock(RiscvInstrBlock):
    def __init__(self, name, extension):
        super().__init__(name, extension)
        self.extension = [extension for extension in [
            'RV_D', 'RV64_D',
            'RV_F', 'RV64_F',
            'RV32_C_F', 'RV_C_D'
        ] if extension in self.extension]

    def gen_instr(self):
        instr = load_from_magic_device(type='INTEGER')
        self.instr_list.append(instr)
        rd = instr['RD']

        def instr_c_reg(reg):
            return reg == rd

        instr = rand_instr(instr_name=["FSRM"])
        instr.add_constraint(instr_c_reg, ['RS1'])
        instr.solve()
        self.instr_list.append(instr)

        def instr_c_reg(reg):
            return reg == 'ZERO'

        instr = rand_instr(instr_name=["FSFLAGS"])
        instr.add_constraint(instr_c_reg, ['RS1'])
        instr.solve()
        self.instr_list.append(instr)

        reg_c = []
        reg_magic = list(get_magic_reg('MAGIC_RDM_FLOAT')) + \
            list(get_magic_reg('MAGIC_RDM_DOUBLE'))
        for i in range(random.randint(8, 12)):
            instr = rand_instr(instr_extension=self.extension,
                               instr_category=['FLOAT'])

            def instr_c_reg(name, fsrc1, fsrc2):
                return fsrc1 in reg_c or (fsrc1 in reg_magic) or (
                    use_rs2(name) and (fsrc2 in reg_c or (fsrc2 in reg_magic)))

            if not (len(reg_c) == 0 and len(reg_magic) == 0):
                instr.add_constraint(
                    instr_c_reg, ['NAME', 'FRS1', 'FRS2'])
            instr.solve()
            if Config.DETAIL:
                instr.comment = f"magic_reg = {list(reg_magic)}, reg_c = {list(reg_c)}"

            if instr.has('FRD'):
                reg_c.append(instr['FRD'])
            self.instr_list.append(instr)
            if len(reg_c) > 4:
                reg_c.pop(0)

        instr = rand_instr(instr_name=["FRFLAGS"])
        instr.solve()
        self.instr_list.append(instr)

        frd = reg_c

        def instr_c_reg(reg):
            return reg in frd

        instr = rand_instr(instr_name=["FCLASS.S", "FCLASS.D"])
        if len(frd) != 0:
            instr.add_constraint(instr_c_reg, ['FRS1'])
        instr.solve()
        self.instr_list.append(instr)


class CsrBlock(RiscvInstrBlock):
    def __init__(self, name, extension, mode):
        super().__init__(name, extension)
        self.mode = mode
        self.extension = [extension for extension in [
            'RV_ZICSR'] if extension in self.extension]

    def gen_instr(self):
        # TODO: move this list into Configuration
        csr_ban = ['MTVEC', 'STVEC', 'MIE', 'SIE', 'SATP']
        if self.mode == 'M':
            csr_ban.append('MEDELEG')

        def instr_c_reg(reg):
            return reg not in csr_ban

        def c_name(name):
            return name not in ['FRRM', 'FSRM', 'FRFLAGS', 'FSFLAGS']

        instr = rand_instr(instr_extension=self.extension,
                           instr_category=['CSR'])
        instr.add_constraint(instr_c_reg, ['CSR'])
        instr.add_constraint(c_name, ['NAME'])
        instr.solve()
        self.instr_list.append(instr)
        # if Config.RUN_ON_SPIKE == True and instr.csr == 'MISA' and ('RV64C' in utils.riscv_instr_extension_t or 'RV32C' in utils.riscv_instr_extension_t):
        #    self.instr_list.append(riscv_instr_base("csrrsi t0, misa, 4"))


class SystemOperationBlock(RiscvInstrBlock):
    def __init__(self, name, extension):
        super().__init__(name, extension)
        self.extension = [extension for extension in [
            'RV_I', 'RV64_I'] if extension in self.extension]
        if Config.ENABLE_ROCC:
            self.extension.append('ROCC')

    def gen_instr(self):
        instr = rand_instr(instr_extension=self.extension,
                           instr_category=['SYSTEM', 'SYNCH'])
        instr.solve()
        self.instr_list.append(instr)


class ZkBlock(RiscvInstrBlock):
    def __init__(self, name, extension):
        super().__init__(name, extension)
        self.extension = [extension for extension in [
            'RV_ZK', 'RV64_ZBKB', 'RV_ZBKX', 'RV_ZBKB', 'RV32_ZPN', 'RV_ZBKC',
            'RV32_ZK', 'RV64_ZK'] if extension in self.extension]

    def gen_instr(self):
        reg_c = []
        reg_magic = list(get_magic_reg('MAGIC_RDM_WORD')) + \
            list(get_magic_reg('MAGIC_RANDOM'))
        for _ in range(random.randint(8, 12)):
            instr = rand_instr(instr_extension=self.extension)

            def instr_c_reg(name, src1, src2):
                return src1 in reg_c or (src1 in reg_magic) or (
                    use_rs2(name) and (src2 in reg_c or (src2 in reg_magic)))

            if not (len(reg_c) == 0 and len(reg_magic) == 0):
                instr.add_constraint(
                    instr_c_reg, ['NAME', 'RS1', 'RS2'])
            instr.solve()
            if Config.DETAIL:
                instr.comment = f"magic_reg = {list(reg_magic)}, reg_c = {list(reg_c)}"
            self.instr_list.append(instr)
            reg_c.append(instr['RD'])
            if len(reg_c) > 4:
                reg_c.pop(0)


class MagicLoadBlock(RiscvInstrBlock):
    def __init__(self, name, extension):
        super().__init__(name, extension)
        self.extension = [extension_i for extension_i in [
            'RV_I', 'RV64_I', 'RV_D', 'RV64_D',
            'RV_F', 'RV64_F'] if extension_i in self.extension]

    def work(self):
        return True

    def gen_instr(self):
        for _ in range(random.randint(6, 8)):
            self.instr_list.append(
                load_from_magic_device(extension=self.extension))


class MagicJumpBlock(RiscvInstrBlock):
    def __init__(self, name, extension):
        super().__init__(name, extension)
        self.extension = [extension_i for extension_i in [
            'RV_I', 'RV64_I'] if extension_i in self.extension]

    def work(self):
        return Config.MAGIC_JUMP_CNT < Config.MAGIC_JUMP_LIMIT and random.randint(0, 7) == 0

    def gen_instr(self):
        instr = load_from_magic_device(type='TEXT_ADDR', label='NONE')

        def instr_c_rs1(rs1):
            return rs1 == instr['RD']

        instr_j = rand_instr(
            instr_name=['JALR'], instr_extension=self.extension, instr_category=['JUMP'])
        instr_j.add_constraint(
            instr_c_rs1, ['RS1'])
        instr_j.set_label_constraint(['NONE'])
        instr_j.solve()

        instr = rand_instr(instr_name=['MAGIC_JUMP'])

        def c_jump(rs2):
            return rs2 == instr_j['RD']

        instr.add_constraint(c_jump, ['RS2'])
        instr.solve()
        self.instr_list.append(instr)
        # self.instr_list.append(instr)
        # self.instr_list.append(instr_j)
        Config.MAGIC_JUMP_CNT += 1


def new_branch_to(extension, target):
    extension = [extension_i for extension_i in [
        'RV_I', 'RV64_I', 'RV_C', 'RV32_C', 'RV64_C'] if extension_i in extension]
    instr = rand_instr(
        instr_extension=extension, instr_category=['BRANCH'])
    instr.set_label_constraint([target])
    instr.solve()
    return [instr]


# la rd0, target
# jalr rd1, rd0, target
# or
# jal
def new_jump_to(target):
    instr_l = load_from_magic_device(type='TEXT_ADDR', label=target)
    instr_j = rand_instr(
        instr_extension=['RV_I', 'RV64_I'], instr_category=['JUMP'])

    def instr_c_rs1(name, rs1):
        if name == 'JALR':
            return rs1 == instr_l['RD']
        else:
            return name == 'JAL'

    instr_j.add_constraint(instr_c_rs1, ['NAME', 'RS1'])
    instr_j.set_label_constraint([target])
    instr_j.set_imm_constraint(range(0, 1))
    instr_j.solve()

    if instr_j['NAME'] == 'JAL':
        return [instr_j]
    else:
        return [instr_l, instr_j]

# for i in range(1000000):
#    b = None
#    k = random.randint(0, 8)
#    if (k == 0):
#        b = IntArithmeticBlock(f'Int_{i}', t_extension)
#    if (k == 1):
#        b = LoadStoreBlock(f'LS_{i}', t_extension, 'TEXT_ADDR', 2048)
#    if (k == 2):
#        b = AmoBlock(f'AMO_{i}', t_extension, 'TEXT_ADDR')
#    if (k == 3):
#        b = FloatArithmeticBlock(f'FLOAT_{i}', t_extension)
#    if (k == 4):
#        b = CsrBlock(f'CSR_{i}', t_extension, 'M')
#    if (k == 5):
#        b = SystemOperationBlock(f'CSR_{i}', t_extension)
#    if (k == 6):
#        b = ZkBlock(f'ZK_{i}', t_extension)
#    if (k == 7):
#        b = MagicLoadBlock(f'MAGIC_L{i}', t_extension)
#    if (k == 8):
#        b = MagicJumpBlock(f'MAGIC_J{i}', t_extension)
#    b.gen_instr()
#    print(b.name)
#    for instr in b.instr_list:
#        print(f'  {instr.to_asm()}  # {instr.comment}')
#    print('')
