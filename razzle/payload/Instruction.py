import random
import re

from constraint import *

from razzle.payload.Field import *


class InstructionBase:
    def __init__(self, asm=None):
        self._problem = Problem(MinConflictsSolver())
        self._solution = None
        self._added_variable = set()
        self._problem.addVariable('NAME', all_instructions_name)
        self.comment = ""
        self.protect = False

        if asm is not None:
            self._solution = {}
            vars = re.split(' |,|\(|\)|\t', asm)
            while '' in vars:
                vars.remove('')
            name = vars[0].upper()
            format = re.split(
                ' |,|{|}|\(|\)|\t', all_instructions[name]['format'])
            while '' in format:
                format.remove('')
            for i in range(1, len(vars)):
                for variable in all_instructions[name]['variables']:
                    if variable_name_remap[variable] == format[i]:
                        if format[i] != 'LABEL' and format[i] != 'IMM':
                            self._solution[variable] = vars[i].upper()
                        else:
                            self._solution[variable] = vars[i]
            self._solution['NAME'] = name

    def __setitem__(self, item, value):
        if self._solution is None:
            raise Exception('Please call solve() first')
        for name, rename in variable_name_remap.items():
            if rename == item: 
                self._solution[name] = value

    def __getitem__(self, item):
        if self._solution is None:
            raise Exception('Please call solve() first')
        for variable in all_instructions[self._solution['NAME']]['variables']:
            if variable_name_remap[variable] == item:
                return self._solution[variable]
        if item == 'EXTENSION':
            return self._solution['EXTENSION']
        if item == 'CATEGORY':
            return self._solution['CATEGORY']
        if item == 'NAME':
            return self._solution['NAME']
        raise Exception(f'{item} is not a variable of this instruction')

    def has(self, item):
        if self._solution is None:
            raise Exception('Please call solve() first')
        for variable in all_instructions[self._solution['NAME']]['variables']:
            if variable_name_remap[variable] == item:
                return True
        return False

    def add_constraint(self, constraint, variables_name, mandatory=False):
        for variable_name in variables_name:
            if variable_name == 'IMM':
                raise Exception(
                    'IMM should not be added as a variable, please use set_imm_constraint() instead')
            if variable_name == 'LABEL':
                raise Exception(
                    'LABEL should not be added as a variable, please use set_label_constraint() instead')
            if variable_name == 'NAME':
                continue

            for variable in variable_name_remap.keys():
                if variable_name_remap[variable] != variable_name:
                    continue
                if variable not in self._added_variable:
                    self._problem.addVariable(
                        variable, variable_range[variable])
                    self._added_variable.add(variable)

        extend_args = ['NAME']
        for variable_name in variables_name:
            extend_args.extend([v for v in variable_name_remap.keys(
            ) if variable_name_remap[v] == variable_name])

        def wrapper(name, *args):
            real_args = {}
            for variable in all_instructions[name]['variables']:
                if variable_name_remap[variable] in variables_name:
                    real_args[variable_name_remap[variable]
                              ] = extend_args.index(variable) - 1
            if 'NAME' in variables_name:
                real_args['NAME'] = -1
            if len(real_args) < len(variables_name):
                # not mandatory
                return True
            return constraint(*[args[real_args[v]] if v != 'NAME' else name for v in variables_name])

        self._problem.addConstraint(wrapper, extend_args)

        if mandatory:
            def c_mandatory(name):
                now_variables_name = []
                for variable in all_instructions[name]['variables']:
                    now_variables_name.append(variable_name_remap[variable])
                for variable_name in variables_name:
                    if variable_name != 'NAME' and variable_name not in now_variables_name:
                        return False
                return True

            self._problem.addConstraint(c_mandatory, ['NAME'])

    def set_name_constraint(self, name_list):
        def c_name(name):
            return name in name_list

        self._problem.addConstraint(c_name, ['NAME'])

    def set_category_constraint(self, category_list):
        def c_category(name):
            return all_instructions[name]['category'] in category_list

        self._problem.addConstraint(c_category, ['NAME'])

    def set_extension_constraint(self, extension_list):
        def c_extension(name):
            for extension in all_instructions[name]['extension']:
                if extension in extension_list:
                    return True
            return False

        self._problem.addConstraint(c_extension, ['NAME'])

    def set_imm_constraint(self, imm_range, mandatory=False):
        self._problem.addVariable('IMM', imm_range)

        def imm_c(name, imm):
            if 'imm_type' not in all_instructions[name].keys():
                return not mandatory
            type = all_instructions[name]['imm_type']
            length = all_instructions[name]['imm_length']
            if type == 'UIMM':
                return 0 <= imm < 2 ** length
            elif type == 'NZUIMM':
                return 0 < imm < 2 ** length
            elif type == 'IMM':
                return -2 ** (length - 1) <= imm < 2 ** (length - 1)
            else:  # type == 'NZIMM':
                return imm != 0 and -2 ** (length - 1) <= imm < 2 ** (length - 1)

        self._problem.addConstraint(imm_c, ['NAME', 'IMM'])

    def set_label_constraint(self, label_range):
        self._problem.addVariable('LABEL', label_range)

    def _fix_imm(self):
        name = self._solution['NAME']
        if 'IMM' not in self._solution.keys():
            length = all_instructions[name]['imm_length']
            type = all_instructions[name]['imm_type']
            if type == 'IMM':
                imm = random.randint(-2 ** (length - 1), 2 ** (length - 1) - 1)
            elif type == 'NZIMM':
                imm = random.randint(-2 ** (length - 1), 2 ** (length - 1) - 1)
                while imm == 0:
                    imm = random.randint(-2 ** (length - 1),
                                         2 ** (length - 1) - 1)
            elif type == 'UIMM':
                imm = random.randint(0, 2 ** length - 1)
            else:  # NZUIMM
                imm = random.randint(1, 2 ** length - 1)
            self._solution['IMM'] = imm

        imm = self._solution['IMM']

        if 'imm_align' in all_instructions[name].keys():
            align = all_instructions[name]['imm_align']
            imm = imm // align * align

        if all_instructions[name]['imm_type'] in ['NZIMM', 'NZUIMM'] and imm == 0:
            imm += all_instructions[name]['imm_align'] if 'imm_align' in all_instructions[name].keys() else 1

        if name in ['AES64KS1I']:
            imm = min(imm, 0xA)

        self._solution['IMM'] = imm

    def solve_with_out_clean(self):
        self._solution = self._problem.getSolution()
        for variable in all_instructions[self._solution['NAME']]['variables']:
            if variable not in self._solution.keys():
                if variable == 'LABEL':
                    raise Exception('LABEL must be set')
                if variable == 'IMM':
                    continue
                self._solution[variable] = random.choice(
                    variable_range[variable])
        if 'IMM' in all_instructions[self._solution['NAME']]['variables']:
            self._fix_imm()
        if 'CATEGORY' not in self._solution.keys():
            self._solution['CATEGORY'] = all_instructions[self._solution['NAME']]['category']
        if 'EXTENSION' not in self._solution.keys():
            self._solution['EXTENSION'] = random.choice(
                all_instructions[self._solution['NAME']]['extension'])

    def to_asm(self):
        name = self._solution['NAME']
        asm = all_instructions[name]['format']
        for variable in all_instructions[name]['variables']:
            if variable != 'NAME':
                var = self._solution[variable]
                if variable == 'IMM':
                    try:
                        var = hex(int(var))
                    except ValueError:
                        var = hex(int(var, base=16))
                elif variable != 'LABEL' and variable_name_remap[variable] != 'MAGIC_ADDR':
                    var = var.lower()
                asm = asm.replace(
                    '{' + variable_name_remap[variable] + '}', var)
        return asm
    
    def is_rvc(self):
        return self._solution['NAME'].startswith('C.')

    def get_len(self):
        if self._solution['NAME'] == 'LA' or self._solution['NAME'] == 'Li':
            return 8
        elif self.is_rvc():
            return 2
        else:
            return 4

class RawInstruction(InstructionBase):
    def __init__(self, raw_inst):
        self.raw_inst = raw_inst

    def to_asm(self):
        return self.raw_inst
    
    def is_rvc(self):
        return self.raw_inst.startswith('c.')

    def get_len(self):
        if self.raw_inst.startswith('la') or self.raw_inst.startswith('li'):
            return 8
        elif self.is_rvc():
            return 2
        else:
            return 4

# for i in range(100):
#    instr = Instruction()
#    try:
#        def c_name(name, rs1):
#            return name in ['ADD', 'ADDIW', 'ADDI'] and rs1 == 'ZERO'
#        instr.add_constraint(c_name, ['NAME', 'RS1'], True)
#        instr.set_extension_constraint(['RV_I', 'RV64_I'])
#        instr.solve()
#    except:
#        continue
#    print(instr.to_asm())
