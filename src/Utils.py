import json
import logging
import os
import random


class cli_wrapper:
    def __init__(self, prog, args=[]):
        self.prog = prog
        self.args = [prog] + self.input2list(args)
        self.debug = False

    def input2list(self, sth):
        return [sth] if isinstance(sth, str) else list(sth)

    def append(self, input):
        self.args += self.input2list(input)

    def drop(self):
        self.args = self.args[:-1]

    def clean(self):
        self.args = [self.prog]

    def exec(self, extra_args=[], cmd_history=None):
        args = " ".join(self.args + self.input2list(extra_args))
        logging.debug(args)
        if cmd_history is not None:
            cmd_history += [args]
        return os.system(args)


def gen_imm(type, length):
    imm = 0
    if type == 'IMM':
        imm = random.randint(-2 ** (length - 1), 2 ** (length - 1) - 1)
    elif type == 'NZIMM':
        imm = random.randint(-2 ** (length - 1), 2 ** (length - 1) - 1)
        while imm == 0:
            imm = random.randint(-2 ** (length - 1), 2 ** (length - 1) - 1)
    elif type == 'UIMM':
        imm = random.randint(0, 2 ** length - 1)
    else:  # NZUIMM
        imm = random.randint(1, 2 ** length - 1)
    mask = [

    ]
    if 'NZ' not in type:
        mask.append('0x00000000')

# instructions


with open('src/instruction.json', 'r') as f:
    all_instructions = json.load(f)

# variables

all_variables = set()

for instruction in all_instructions.values():
    for variable in instruction['variables']:
        all_variables.add(variable)

all_variables = list(all_variables)
all_variables.extend(['EXTENSION', 'CATEGORY'])

# instructions_name

all_instructions_name = list(all_instructions.keys())

data_pattern_t = ["RAND_DATA", "INCR_VAL"]

program_include_instr = """#include "riscv_test.h"

"""

program_code_begin_instr = """
RVTEST_CODE_BEGIN

"""

program_test_pass_instr = """
RVTEST_PASS

"""

program_mtvec_handler_instr = """
.section .text.init
.align 3
.option push
.option norvc
mtvec_handler:
    csrr t0, mtval;
    csrwi mip, 0;
    li t0, MSTATUS_MPIE;
    csrs mstatus, t0;
    csrr t0, mepc;
#ifndef ENABLE_MAGIC_DEVICE
    lh   t1, 0(t0);
    andi t1, t1, 3;
    li   t2, 3;
    bne  t1, t2, mtvec_handler_add_2;
mtvec_handler_add_4:
    addi t0, t0, 4;
    csrw mepc, t0;
    mret;
mtvec_handler_add_2:
    addi t0, t0, 2;
    csrs misa, 4
    csrw mepc, t0;
    mret;
#else
    ld t0, MAGIC_MEPC_NEXT(x0)
    csrw mepc, t0;
    ZJV_FUZZ_INSNRDM_CLEAN;
    mret;
#endif
.option pop

"""

program_stvec_handler_instr = """
.section .text.init
.align 3
.option push
.option norvc
stvec_handler:
    csrr t0, stval;
    csrr t0, sepc;
    csrwi sip, 0;
    csrw satp, zero;
#ifndef ENABLE_MAGIC_DEVICE
    lh   t1, 0(t0);
    andi t1, t1, 3;
    li   t2, 3;
    bne  t1, t2, stvec_handler_add_2;
stvec_handler_add_4:
    addi t0, t0, 4;
    csrw sepc, t0;
    sret;
stvec_handler_add_2:
    addi t0, t0, 2;
    csrw sepc, t0;
    sret;
#else
    ld t0, MAGIC_SEPC_NEXT(x0)   # generate legal addr
    csrw sepc, t0;
    ZJV_FUZZ_INSNRDM_CLEAN;
    sret;
#endif
.option pop

"""

program_code_end_instr = """
RVTEST_CODE_END

"""

program_data_start_instr = """
RVTEST_DATA_BEGIN

"""

program_data_end_instr = """
RVTEST_DATA_END

"""


def getbits(a, st, ed):
    return a[a.len - st - 1: a.len - ed].uint


def getbit(a, pos):
    return a[a.len - pos - 1]
