from BuildManager import *
from SectionUtils import *
from razzle.snapshot.riscv_state import *


class InitManager(SectionManager):
    def __init__(self, config, output_path, priv):
        super().__init__(config)
        self.output_path = output_path
        self.init_input = config["init_input"]
        if 'csr_map' in config:
            self.csr_map = config['csr_map']
        else:
            self.csr_map = None
        if 'csr_solve' in config:
            self.csr_solve = config['csr_solve']
        else:
            self.csr_solve = None
        
        self.pmp = config["pmp"]
        self.priv = priv
        self.design = RISCVSnapshot("rv64gc", int(self.pmp), SUPPORTED_CSR, True)

    def _set_symbol_relate_register(self, mode):
        priv, addr = mode
        # close interrupt
        self.reg_init_config["csr"]["mstatus"]["SIE"] = "0b0"
        self.reg_init_config["csr"]["mstatus"]["SPIE"] = "0b0"
        self.reg_init_config["csr"]["mstatus"]["MIE"] = "0b0"
        self.reg_init_config["csr"]["mstatus"]["MPIE"] = "0b0"
        self.reg_init_config["csr"]["mstatus"]["MPRIV"] = "0b0"
        # mtvec/stvec
        self.reg_init_config["csr"]["mtvec"]["BASE"] = "0x80001000"
        self.reg_init_config["csr"]["mtvec"]["MODE"] = "0b00"
        self.reg_init_config["csr"]["stvec"]["BASE"] = "0xffffffff80001800"
        self.reg_init_config["csr"]["stvec"]["MODE"] = "0b00"
        # mepc/sepc
        if priv == 'U' or priv == 'M':
            self.reg_init_config["csr"]["mepc"]["EPC"] = "0x80200000"
        else:
            self.reg_init_config["csr"]["mepc"]["EPC"] = "0xffffffff80200000"
        # satp
        if addr == 'v':
            self.reg_init_config["csr"]["satp"]["PPN"] = "0x8000d000"
            self.reg_init_config["csr"]["satp"]["ASID"] = "0x0"
            self.reg_init_config["csr"]["satp"]["MODE"] = "0x8"
        else:
            self.reg_init_config["csr"]["satp"]["PPN"] = "0x0"
            self.reg_init_config["csr"]["satp"]["ASID"] = "0x0"
            self.reg_init_config["csr"]["satp"]["MODE"] = "0x0"
        # mstatus
        self.reg_init_config["csr"]["mstatus"]["MPP"] = \
            {'U':'0b00', 'S':'0b01', 'M':'0b11'}[priv]
        
        # pmp
        pmp_name = f'pmp{self.pmp - 1}'
        self.reg_init_config["pmp"][pmp_name]["R"] = "0b1"
        self.reg_init_config["pmp"][pmp_name]["W"] = "0b1"
        self.reg_init_config["pmp"][pmp_name]["X"] = "0b1"
        self.reg_init_config["pmp"][pmp_name]["L"] = "0b0"
        self.reg_init_config["pmp"][pmp_name]["A"] = "NAPOT"
        self.reg_init_config["pmp"][pmp_name]["ADDR"] = "0x80000000"
        self.reg_init_config["pmp"][pmp_name]["RANGE"] = "0x800000"

        # access_fault_pmp
        self.reg_init_config["pmp"]["pmp0"]["R"] = "0b0"
        self.reg_init_config["pmp"]["pmp0"]["W"] = "0b0"
        self.reg_init_config["pmp"]["pmp0"]["X"] = "0b0"
        self.reg_init_config["pmp"]["pmp0"]["L"] = "0b1"
        self.reg_init_config["pmp"]["pmp0"]["A"] = "NAPOT"
        self.reg_init_config["pmp"]["pmp0"]["ADDR"] = "0x80005000"
        self.reg_init_config["pmp"]["pmp0"]["RANGE"] = "0x1000"

    def _reg_init_generate(self):
        with open(self.init_input, "rt") as base_init_file:
            self.reg_init_config = hjson.load(base_init_file)
        if self.csr_map is not None:
            with open(self.csr_map, "rt") as csr_map_file:
                self.csr_map_config = hjson.load(csr_map_file)
        else:
            self.csr_map_config = {}
        if self.csr_solve is not None:
            with open(self.csr_solve, "rt") as csr_solve_file:
                self.csr_solve_config = hjson.load(csr_solve_file)
        else:
            self.csr_solve_config = {}
        self.reg_init_config = self.design.csr_map(self.reg_init_config, self.csr_map_config, self.csr_solve_config)
        self._set_symbol_relate_register(self.priv)
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

