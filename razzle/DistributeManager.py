from BuildManager import *
from ChannelManger import *
from InitManager import *
from LoaderManager import *
from PageTableManager import *
from PocManager import *
from PayloadManager import *
from SecretManager import *
from StackManager import *
from TransManager import *


class DistributeManager:
    def __init__(self, hjson_filename, output_path, virtual, do_fuzz):
        hjson_file = open(hjson_filename)
        config = hjson.load(hjson_file)
        hjson_file.close()

        self.baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, output_path
        )
        self.attack_privilege = config["attack"]
        self.victim_privilege = config["victim"]
        privilege_stage = {"M": 3, "S": 1, "U": 0}
        assert (
            privilege_stage[self.attack_privilege]
            <= privilege_stage[self.victim_privilege]
        ), "the privilege of vicitm smaller than attack's is meanless"

        self.output_path = output_path
        self.virtual = virtual if self.attack_privilege != "M" else False

        self.code = {}
        self.code["secret"] = SecretManager(config["secret"])
        self.code["channel"] = ChannelManager(config["channel"])
        self.code["stack"] = StackManager(config["stack"])
        if do_fuzz:
            self.code["payload"] = TransManager(
                config["fuzz"], self.victim_privilege, self.virtual, output_path
            )
        else:
            self.code["payload"] = PayloadManager(config["payload"])
            self.code["poc"] = PocManager(config["poc"])
        self.code["init"] = InitManager(
            config["init"], do_fuzz, self.virtual, self.attack_privilege, output_path
        )

        self.page_table = PageTableManager(
            config["page_table"], self.attack_privilege == "U"
        )
        self.loader = LoaderManager(self.virtual)

        self.file_list = []
        self.var_file_list = []

    def _collect_compile_file(self, file_list):
        self.file_list.extend(file_list[0])
        self.var_file_list.extend(file_list[1])

    def generate_test(self):
        page_table_name = "page_table.S"
        ld_name = "link.ld"

        self.section_list = []
        for key, value in self.code.items():
            self._collect_compile_file(
                value.file_generate(self.output_path, f"{key}.S")
            )
            self.section_list.extend(value.get_section_list())

        if self.virtual:
            self.page_table.register_sections(self.section_list)
            self._collect_compile_file(
                self.page_table.file_generate(self.output_path, page_table_name)
            )
            self.section_list.extend(self.page_table.get_section_list())

        self.loader.append_section_list(self.section_list)
        self.loader.file_generate(self.output_path, ld_name)

        RAZZLE_ROOT = os.environ["RAZZLE_ROOT"]
        gen_elf = ShellCommand(
            "riscv64-unknown-elf-gcc",
            [
                "-march=rv64g_zicsr",
                "-mabi=lp64f",
                "-mcmodel=medany",
                "-nostdlib",
                "-nostartfiles",
                f"-I$OUTPUT_PATH",
                f"-I$RAZZLE_ROOT/template",
                f"-I$RAZZLE_ROOT/template/trans",
                f"-I$RAZZLE_ROOT/template/loader",
                f"-T$OUTPUT_PATH/{ld_name}",
            ],
        )
        self.baker.add_cmd(
            gen_elf.generate([*self.file_list, "-o", f"$OUTPUT_PATH/Testbench"])
        )
        self.baker.add_cmd(
            gen_elf.generate(
                [*self.var_file_list, "-o", f"$OUTPUT_PATH/Testbench.variant"]
            )
        )

        gen_bin = ShellCommand("riscv64-unknown-elf-objcopy", ["-O", "binary"])
        self.baker.add_cmd(
            gen_bin.generate(
                [f"$OUTPUT_PATH/Testbench", f"$OUTPUT_PATH/Testbench.bin"]
            )
        )
        self.baker.add_cmd(
            gen_bin.generate(
                [
                    f"$OUTPUT_PATH/Testbench.variant",
                    f"$OUTPUT_PATH/Testbench.variant.bin",
                ]
            )
        )

        gen_hex = ShellCommand("od", ["-v", "-An", "-tx8"])
        self.baker.add_cmd(
            gen_hex.generate(
                [
                    f"$OUTPUT_PATH/Testbench.bin",
                    f"> $OUTPUT_PATH/Testbench.hex",
                ]
            )
        )
        self.baker.add_cmd(
            gen_hex.generate(
                [
                    f"$OUTPUT_PATH/Testbench.variant.bin",
                    f"> $OUTPUT_PATH/Testbench.variant.hex",
                ]
            )
        )

        gen_asm = ShellCommand("riscv64-unknown-elf-objdump", ["-d"])
        self.baker.add_cmd(
            gen_asm.generate(
                [
                    f"$OUTPUT_PATH/Testbench",
                    f"> $OUTPUT_PATH/Testbench.asm",
                ]
            )
        )

    def run(self, cmd=None):
        self.baker.run(cmd)
