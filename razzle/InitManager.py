from BuildManager import *
from SectionUtils import *
from razzle.snapshot.riscv_state import *


class InitManager(SectionManager):
    def __init__(self, config, do_fuzz, virtual, privilege, output_path):
        super().__init__(config)
        self.do_fuzz = do_fuzz
        self.virtual = virtual
        self.privilege = privilege
        self.output_path = output_path
        self.init_input = config["init_input"]
        self.init_output = config["init_output"]

        pmp = config["pmp"]
        self.design = RISCVSnapshot("rv64gc", int(pmp), SUPPORTED_CSR, do_fuzz)
        self.output_format = config["format"]
        self.asm = config["asm"]
        self.image = config["image"]

    def _set_symbol_relate_register(self):
        # sp
        self.reg_init_config["xreg"][1] = "stack_bottom"
        # tp
        self.reg_init_config["xreg"][3] = "stack_top"
        # gp
        if not self.do_fuzz:
            self.reg_init_config["xreg"][2] = "__global_pointer$"
        # mtvec/stvec
        if self.do_fuzz:
            self.reg_init_config["csr"]["mtvec"]["BASE"] = "secret_protect_block_entry"
            self.reg_init_config["csr"]["mtvec"]["MODE"] = "0b00"
            self.reg_init_config["csr"]["stvec"][
                "BASE"
            ] = "strap_block_entry  + 0xfffffffffff00000"
            self.reg_init_config["csr"]["stvec"]["MODE"] = "0b00"
        else:
            self.reg_init_config["csr"]["mtvec"]["BASE"] = "trap_entry"
            self.reg_init_config["csr"]["mtvec"]["MODE"] = "0b00"
            self.reg_init_config["csr"]["stvec"]["BASE"] = "abort"
            self.reg_init_config["csr"]["stvec"]["MODE"] = "0b00"
        # mepc/sepc
        if self.do_fuzz:
            self.reg_init_config["csr"]["mepc"]["EPC"] = "_init_block_entry"
            self.reg_init_config["csr"]["sepc"]["EPC"] = "_init_block_entry"
        else:
            self.reg_init_config["csr"]["mepc"]["EPC"] = "_init"
            self.reg_init_config["csr"]["sepc"]["EPC"] = "_init"
        # satp
        if self.virtual:
            self.reg_init_config["csr"]["satp"]["PPN"] = "0x80001000"
            self.reg_init_config["csr"]["satp"]["ASID"] = "0x0"
            self.reg_init_config["csr"]["satp"]["MODE"] = "0x8"
        else:
            self.reg_init_config["csr"]["satp"]["PPN"] = "0x0000000000000000"
            self.reg_init_config["csr"]["satp"]["ASID"] = "0x0"
            self.reg_init_config["csr"]["satp"]["MODE"] = "0x0"
        # mstatus
        match (self.privilege):
            case "M":
                self.reg_init_config["csr"]["mstatus"]["MPP"] = "0b11"
            case "S":
                self.reg_init_config["csr"]["mstatus"]["MPP"] = "0b01"
            case "U":
                self.reg_init_config["csr"]["mstatus"]["MPP"] = "0b00"
            case _:
                raise "privilege must be M, S or U"
        # mscratch
        if self.do_fuzz:
            self.reg_init_config["csr"]["mscratch"]["SCRATCH"] = "mtrap_stack_bottom"
            self.reg_init_config["csr"]["sscratch"][
                "SCRATCH"
            ] = "strap_stack_bottom + 0xfffffffffff00000"
        else:
            self.reg_init_config["csr"]["mscratch"]["SCRATCH"] = "0x80003800"
        # pmp
        self.reg_init_config["pmp"]["pmp1"]["R"] = "0b1"
        self.reg_init_config["pmp"]["pmp1"]["W"] = "0b1"
        self.reg_init_config["pmp"]["pmp1"]["X"] = "0b1"
        self.reg_init_config["pmp"]["pmp1"]["L"] = "0b0"
        self.reg_init_config["pmp"]["pmp1"]["A"] = "NAPOT"
        self.reg_init_config["pmp"]["pmp1"]["ADDR"] = "0x80000000"
        self.reg_init_config["pmp"]["pmp1"]["RANGE"] = "0x40000"

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
        with open(self.init_output, "wt") as output_file:
            hjson.dump(self.reg_init_config, output_file)

    def _reg_asm_generate(self):
        self.design.load_snapshot(self.init_output)
        image_name = f"{self.output_path}/{self.image}"
        self.design.save(image_name, output_format=self.output_format, output_width=64)

        if self.output_format == "hex":
            self.design.gen_loader(f"{self.output_path}/{self.asm}", with_rom=0x20000)
        elif self.output_format == "asm":
            self.design.gen_loader(
                f"{self.output_path}/{self.asm}", with_asm=image_name
            )
        else:
            self.design.gen_loader(
                f"{self.output_path}/{self.asm}", with_bin=image_name
            )

        # os.system(f"cp ./rvsnap/src/loader/rvsnap.h {self.output_path}/")

    def _generate_sections(self):
        self._reg_init_generate()
        self._reg_asm_generate()

        init_link = [
            # '\t\t*(.text.init)\n'
            "\t\t*(.text.init)\n"
            "\t\t*(.data.init)\n"
        ]
        self.section["init"] = FileSection(".init", Flag.U | Flag.X | Flag.R, init_link)

    def _distribute_address(self):
        self.section["init"].get_bound(
            self.memory_bound[0][0], self.memory_bound[0][0], 0x1000, must_m=True
        )

    def _write_file(self, path, name):
        filename = os.path.join(path, self.asm)
        self.dut_file_list.append(filename)
        self.vnt_file_list.append(filename)

