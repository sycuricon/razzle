from BuildManager import *
from SectionUtils import *
from razzle.snapshot.riscv_state import *


class InitManager(SectionManager):
    def __init__(self, config, output_path):
        super().__init__(config)
        self.output_path = output_path
        self.init_input = config["init_input"]

        pmp = config["pmp"]
        self.design = RISCVSnapshot("rv64gc", int(pmp), SUPPORTED_CSR, True)

    def _set_symbol_relate_register(self):
        # sp
        self.reg_init_config["xreg"][1] = "stack_bottom"
        # tp
        self.reg_init_config["xreg"][3] = "stack_top"
        # mtvec/stvec
        self.reg_init_config["csr"]["mtvec"]["BASE"] = "mtrap_block_entry"
        self.reg_init_config["csr"]["mtvec"]["MODE"] = "0b00"
        self.reg_init_config["csr"]["stvec"]["BASE"] = "strap_block_entry  + 0xfffffffffff00000"
        self.reg_init_config["csr"]["stvec"]["MODE"] = "0b00"
        # mepc/sepc
        self.reg_init_config["csr"]["mepc"]["EPC"] = "init_block_entry"
        self.reg_init_config["csr"]["sepc"]["EPC"] = "init_block_entry"
        # satp
        self.reg_init_config["csr"]["satp"]["PPN"] = "0x80001000"
        self.reg_init_config["csr"]["satp"]["ASID"] = "0x0"
        self.reg_init_config["csr"]["satp"]["MODE"] = "0x8"
        # mstatus
        self.reg_init_config["csr"]["mstatus"]["MPP"] = "0b00"
        
        # pmp
        self.reg_init_config["pmp"]["pmp2"]["R"] = "0b1"
        self.reg_init_config["pmp"]["pmp2"]["W"] = "0b1"
        self.reg_init_config["pmp"]["pmp2"]["X"] = "0b1"
        self.reg_init_config["pmp"]["pmp2"]["L"] = "0b0"
        self.reg_init_config["pmp"]["pmp2"]["A"] = "NAPOT"
        self.reg_init_config["pmp"]["pmp2"]["ADDR"] = "0x80000000"
        self.reg_init_config["pmp"]["pmp2"]["RANGE"] = "0x40000"

        # access_fault_pmp
        self.reg_init_config["pmp"]["pmp1"]["R"] = "0b0"
        self.reg_init_config["pmp"]["pmp1"]["W"] = "0b0"
        self.reg_init_config["pmp"]["pmp1"]["X"] = "0b0"
        self.reg_init_config["pmp"]["pmp1"]["L"] = "0b1"
        self.reg_init_config["pmp"]["pmp1"]["A"] = "NAPOT"
        self.reg_init_config["pmp"]["pmp1"]["ADDR"] = "0x8003c000"
        self.reg_init_config["pmp"]["pmp1"]["RANGE"] = "0x1000"

        # self.reg_init_config["pmp"]["pmp0"]["R"]="0b0"
        # self.reg_init_config["pmp"]["pmp0"]["W"]="0b0"
        # self.reg_init_config["pmp"]["pmp0"]["X"]="0b0"
        # self.reg_init_config["pmp"]["pmp0"]["L"]="0b1"
        # self.reg_init_config["pmp"]["pmp0"]["A"]="NAPOT"
        # self.reg_init_config["pmp"]["pmp0"]["ADDR"]="0x80004000"
        # self.reg_init_config["pmp"]["pmp0"]["RANGE"]="0x1000"

    def _reg_init_generate(self):
        with open(self.init_input, "rt") as base_init_file:
            self.reg_init_config = hjson.load(base_init_file)
        self._set_symbol_relate_register()
        # TODO: add a debug option to enable this
        # output_path = os.path.join(self.output_path, "init.done.hjson")
        # with open(output_path, "wt") as output_file:
        #     print(f"[*] The init file is overwritten, check {output_path}")
        #     hjson.dump(self.reg_init_config, output_file)

    def _reg_asm_generate(self, path, name):
        self.design.load_state(self.reg_init_config)
        image_name = os.path.join(path, "reg_init.h")
        os.makedirs(path, exist_ok=True)
        self.design.save(image_name, output_format="asm", output_width=64)
        self.design.gen_loader(os.path.join(path, name), with_asm=image_name)

    def _generate_sections(self):
        init_link = [
            "\t\t*(.text.init)\n"
            "\t\t*(.data.init)\n"
        ]
        self.section["init"] = FileSection(".init", Flag.U | Flag.X | Flag.R, init_link)

    def _distribute_address(self):
        self.section["init"].get_bound(
            self.memory_bound[0][0], self.memory_bound[0][0], 0x1000, must_m=True
        )

    def _write_file(self, path, name):
        self._reg_init_generate()
        self._reg_asm_generate(path, name)
        self.dut_file_list.append(os.path.join(path, name))

