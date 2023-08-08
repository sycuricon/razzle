from Instruction import *

magic_device_type = {
    'MAGIC_RANDOM',
    'MAGIC_RDM_WORD',
    'MAGIC_RDM_FLOAT',
    'MAGIC_RDM_DOUBLE',
    'MAGIC_RDM_TEXT_ADDR',
    'MAGIC_RDM_DATA_ADDR',
    'MAGIC_MEPC_NEXT',
    'MAGIC_SEPC_NEXT',
    'MAGIC_RDM_PTE',
    'MAX_MAGIC_SPACE'
}

magic_reg = {key: set() for key in magic_device_type}


def magic_device_reg_set_dirty(instr):
    rd = None
    if instr.has('RD'):
        rd = instr['RD']
    if instr.has('FRD'):
        rd = instr['FRD']
    if rd is None:
        return
    for value in magic_reg.values():
        if rd in value:
            value.remove(rd)


def get_magic_reg(type):
    return magic_reg[type]


def load_from_magic_device(type=None, label=None, extension=None):
    instr = Instruction()
    if extension is not None:
        instr.set_extension_constraint(extension)

    def c_l_type(l_type, magic_addr):
        return (l_type == 'LD' and magic_addr == 'MAGIC_RANDOM') \
               or (l_type == 'LW' and magic_addr == 'MAGIC_RDM_WORD')

    instr.add_constraint(c_l_type, ['L_TYPE', 'MAGIC_ADDR'])

    def c_rd(rd):
        return rd != 'ZERO'

    instr.add_constraint(c_rd, ['RD'])

    if type is not None and (type == 'DATA_ADDR' or type == 'TEXT_ADDR'):
        instr.set_label_constraint([label])

        def c_type(addr):
            return (addr == 'MAGIC_RDM_DATA_ADDR' and type == 'DATA_ADDR') \
                   or (addr == 'MAGIC_RDM_TEXT_ADDR' and type == 'TEXT_ADDR')

        instr.add_constraint(c_type, ['MAGIC_ADDR'])
        instr.set_category_constraint(['MAGIC_LOAD_A'])
    elif type is not None and type == 'INTEGER':
        def c_name(name):
            return name == 'MAGIC_LI'

        instr.add_constraint(c_name, ['NAME'])
    elif type is None:
        def c_name(name):
            return name in ['MAGIC_LI', 'MAGIC_LI_S', 'MAGIC_LI_D']

        instr.add_constraint(c_name, ['NAME'])

    instr.solve()

    if instr.has('MAGIC_ADDR'):
        magic_reg[instr['MAGIC_ADDR']].add(instr['RD'])
    if instr.has('MAGIC_ADDR_A'):
        magic_reg[instr['MAGIC_ADDR_A']].add(instr['RD'])
    if instr['NAME'] == 'MAGIC_LI_S':
        magic_reg['MAGIC_RDM_FLOAT'].add(instr['FRD'])
    if instr['NAME'] == 'MAGIC_LI_D':
        magic_reg['MAGIC_RDM_DOUBLE'].add(instr['FRD'])
    magic_device_reg_set_dirty(instr)
    return instr


class Instruction(InstructionBase):
    def solve(self):
        self.solve_with_out_clean()
        magic_device_reg_set_dirty(self)
