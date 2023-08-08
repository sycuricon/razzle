import json
import re

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
    'LABEL': 'LABEL',
}

with open('instruction.json', 'r') as f:
    instructions = json.load(f)

for key, instruction in instructions.items():
    for variable in instruction['variables']:
        if variable_name_remap[variable] != variable:
            instruction['format'] = instruction['format'].replace(variable_name_remap[variable], '{' + variable_name_remap[variable] + '}')
with open('instruction1.json', 'w') as f:
    json.dump(indent=4, fp=f, obj=instructions)
