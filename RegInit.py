import hjson
import argparse
import os

class RegInit:
    def __init__(self,base_init_name,output_name,do_fuzz,virtual):
        self.base_init_name=base_init_name
        self.output_name=output_name
        self.virtual=virtual
        self.do_fuzz=do_fuzz
    
    def _get_symbol_address(self):
        self.symbol={}
        with open(self.symbol_name,"rt") as symbol_file:
            symbol_lines=symbol_file.readlines()
            for line in symbol_lines:
                [vaddr,kind,name] = list(line.strip().split(' '))
                self.symbol[name] = vaddr

    def _num2hex(self,num):
        return '0x'+num

    def _set_symbol_relate_register(self):
        # sp
        self.reg_init_config["xreg"][1]="stack_bottom"
        # tp
        self.reg_init_config["xreg"][3]="stack_top"
        # gp
        if not self.do_fuzz:
            self.reg_init_config["xreg"][2]="__global_pointer$"
        # mtvec
        self.reg_init_config["csr"]["mtvec"]["BASE"]="trap_entry"
        self.reg_init_config["csr"]["mtvec"]["MODE"]="0b00"
        # stvec
        if not self.do_fuzz:
            self.reg_init_config["csr"]["stvec"]["BASE"]="abort"
            self.reg_init_config["csr"]["stvec"]["MODE"]="0b00"
        # mepc/sepc
        if self.do_fuzz:
            self.reg_init_config["csr"]["mepc"]["EPC"]="_init_block_entry"
            self.reg_init_config["csr"]["sepc"]["EPC"]="_init_block_entry"
        else:
            self.reg_init_config["csr"]["mepc"]["EPC"]="_init"
            self.reg_init_config["csr"]["sepc"]["EPC"]="_init"
        # satp
        if self.virtual:
            self.reg_init_config["csr"]["satp"]["PPN"]="0x80001000"
            self.reg_init_config["csr"]["satp"]["ASID"]="0x0"
            self.reg_init_config["csr"]["satp"]["MODE"]="0x8"
        else:
            self.reg_init_config["csr"]["satp"]["PPN"]="0x0000000000000000"
            self.reg_init_config["csr"]["satp"]["ASID"]="0x0"
            self.reg_init_config["csr"]["satp"]["MODE"]="0x0"
        #mstatus
        if self.virtual:
            self.reg_init_config["csr"]["mstatus"]["MPP"]="0b00"
        else:
            self.reg_init_config["csr"]["mstatus"]["MPP"]="0b11"
        #mscratch
        self.reg_init_config["csr"]["mscratch"]["SCRATCH"]="0x80003800"
        # pmp
        self.reg_init_config["pmp"]["pmp1"]["R"]="0b1"
        self.reg_init_config["pmp"]["pmp1"]["W"]="0b1"
        self.reg_init_config["pmp"]["pmp1"]["X"]="0b1"
        self.reg_init_config["pmp"]["pmp1"]["L"]="0b0"
        self.reg_init_config["pmp"]["pmp1"]["A"]="NAPOT"
        self.reg_init_config["pmp"]["pmp1"]["ADDR"]="0x80000000"
        self.reg_init_config["pmp"]["pmp1"]["RANGE"]="0x40000"

    def generate(self):
        with open(self.base_init_name,"rt") as base_init_file:
            self.reg_init_config=hjson.load(base_init_file)
        self._set_symbol_relate_register()  
        with open(self.output_name,"wt") as output_file:
            hjson.dump(self.reg_init_config,output_file)

if __name__ == "__main__":
    parse = argparse.ArgumentParser()
    parse.add_argument("-I", "--input",  dest="input",  required=True, help="input hjson")
    parse.add_argument("-O", "--output", dest="output", required=True, help="output of the reg initialization")
    parse.add_argument("-V", "--virtual", dest="virtual", action="store_true", help="link in virtual address")
    parse.add_argument("--fuzz", dest="do_fuzz", action="store_true", help="payload generate by fuzz")
    args = parse.parse_args()
    reg_init = RegInit(args.input,args.output,args.do_fuzz,args.virtual)
    reg_init.generate()