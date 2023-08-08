import Config
from Utils import *

reg_range = [
    "ZERO", "RA", "SP", "GP", "TP", "T0", "T1", "T2", "S0", "S1", "A0", "A1",
    "A2", "A3", "A4", "A5", "A6", "A7", "S2", "S3", "S4", "S5", "S6", "S7",
    "S8", "S9", "S10", "S11", "T3", "T4", "T5", "T6"
]

float_range = [
    "FT0", "FT1", "FT2", "FT3", "FT4", "FT5", "FT6", "FT7",
    "FS0", "FS1", "FA0", "FA1", "FA2", "FA3", "FA4", "FA5",
    "FA6", "FA7", "FS2", "FS3", "FS4", "FS5", "FS6", "FS7",
    "FS8", "FS9", "FS10", "FS11", "FT8", "FT9", "FT10", "FT11"
]

rvc_reg_range = [
    "S0", "S1", "A0", "A1", "A2", "A3", "A4", "A5"
]

rvc_float_range = [
    "FS0", "FS1", "FA0", "FA1", "FA2", "FA3", "FA4", "FA5"
]

csr_range = [
    # M-Mode
    'MVENDORID', 'MARCHID', 'MIMPID', 'MHARTID',
    'MTVEC', 'MIDELEG', 'MIP', 'MCOUNTEREN', 'MCOUNTINHIBIT',
    'MSCRATCH', 'MEPC', 'MCAUSE', 'MTVAL',
    # 'MEDELEG', 'MIE', 'MSTATUS', 'MISA'

    # S-Mode
    'SSTATUS', 'STVEC', 'SIP', 'SCOUNTEREN', 'SSCRATCH', 'SEPC', 'SCAUSE',
    'STVAL', 'SIE', 'SATP',

    # VS-Mode
    'VSSTATUS', 'VSTVEC', 'VSIP', 'VSIE', 'VSSCRATCH', 'VSEPC', 'VSCAUSE', 'VSATP', 'VSTVAL'

    # Unknown
    # 'SENVCFG', 'MSECCFG', 'MTIMECMP', 'MCONFIGPTR', 'MTIME', 'MENVCFG', 'MSTATUSH', 'MENVCFGH',
]

l_type_range = ['LW', 'LD']
magic_addr_range = ['MAGIC_RANDOM', 'MAGIC_RDM_WORD']
magic_addr_a_range = ['MAGIC_RDM_TEXT_ADDR', 'MAGIC_RDM_DATA_ADDR']

extension_range = set()
category_range = set()

for instruction in all_instructions.values():
    for variable in instruction['variables']:
        for extension in instruction['extension']:
            extension_range.add(extension)
        category_range.add(instruction['category'])

extension_range = list(extension_range)
category_range = list(category_range)

# variable_range

variable_range = {
    'RD': reg_range,
    'RS1': reg_range,
    'RS2': reg_range,
    'FRD': float_range,
    'FRS1': float_range,
    'FRS2': float_range,
    'FRS3': float_range,
    'CSR': csr_range,
    'RD_RS1': reg_range,
    'C_RS2': reg_range,
    'RS1_P': rvc_reg_range,
    'RS2_P': rvc_reg_range,
    'RD_RS1_P': rvc_reg_range,
    'RD_P': rvc_reg_range,
    'RD_RS1_N0': [reg for reg in reg_range if reg not in ['ZERO']],
    'RD_N0': [reg for reg in reg_range if reg not in ['ZERO']],
    'C_RS1_N0': [reg for reg in reg_range if reg not in ['ZERO']],
    'RS1_N0': [reg for reg in reg_range if reg not in ['ZERO']],
    'C_RS2_N0': [reg for reg in reg_range if reg not in ['ZERO']],
    'RD_N2': [reg for reg in reg_range if reg not in ['ZERO', 'SP']],
    'FRD_P': rvc_float_range,
    'FRS2_P': rvc_float_range,
    'C_FRS2': float_range,
    'L_TYPE': l_type_range,
    'MAGIC_ADDR': magic_addr_range,
    'MAGIC_ADDR_A': magic_addr_a_range,
    'EXTENSION': extension_range,
    'CATEGORY': category_range,
    'IMM': None,
    'LABEL': None
}

variable_name_remap = {
    'RS1': "RS1",
    'RS1_P': 'RS1',
    'RS1_N0': 'RS1',
    'C_RS1_N0': 'RS1',
    'RS2': 'RS2',
    'RS2_P': 'RS2',
    'C_RS2': 'RS2',
    'C_RS2_N0': 'RS2',
    'RD': 'RD',
    'RD_N2': 'RD',
    'RD_RS1': "RD",
    'RD_P': "RD",
    'RD_RS1_N0': "RD",
    'RD_N0': 'RD',
    'RD_RS1_P': 'RD',
    'FRD_P': 'FRD',
    'FRS2_P': 'FRS2',
    'C_FRS2': 'FRS2',
    'FRS1': 'FRS1',
    'FRS2': 'FRS2',
    'FRS3': 'FRS3',
    'FRD': 'FRD',
    'CSR': 'CSR',
    'L_TYPE': 'L_TYPE',
    'MAGIC_ADDR': 'MAGIC_ADDR',
    'MAGIC_ADDR_A': 'MAGIC_ADDR',
    'EXTENSION': 'EXTENSION',
    'CATEGORY': 'CATEGORY',
    'IMM': 'IMM',
    'LABEL': 'LABEL'
}

for variable in all_variables:
    if variable not in variable_range.keys() and variable not in ['IMM', 'LABEL']:
        raise Exception(f'{variable} is not defined')

assert (len(all_variables) == len(variable_range)
        and len(all_variables) == len(variable_name_remap))
