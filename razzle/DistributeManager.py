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
        self.config = hjson.load(hjson_file)
        hjson_file.close()

        self.baker = BuildManager(
            {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, output_path
        )
        self.attack_privilege = self.config["attack"]
        self.victim_privilege = self.config["victim"]
        privilege_stage = {"M": 3, "S": 1, "U": 0}
        assert (
            privilege_stage[self.attack_privilege]
            <= privilege_stage[self.victim_privilege]
        ), "the privilege of vicitm smaller than attack's is meanless"

        self.output_path = output_path
        self.virtual = virtual if self.attack_privilege != "M" else False

        self.code = {}
        self.code["secret"] = SecretManager(self.config["secret"])
        self.code["channel"] = ChannelManager(self.config["channel"])
        self.code["stack"] = StackManager(self.config["stack"])
        if do_fuzz:
            self.code["payload"] = TransManager(
                self.config["fuzz"], self.victim_privilege, self.virtual, output_path
            )
        else:
            self.code["payload"] = PayloadManager(self.config["payload"])
            self.code["poc"] = PocManager(self.config["poc"])
        self.code["init"] = InitManager(
            self.config["init"], do_fuzz, self.virtual, self.attack_privilege, output_path
        )

        self.page_table = PageTableManager(
            self.config["page_table"], self.attack_privilege == "U"
        )
        self.loader = LoaderManager(self.virtual)

        self.file_list = []

    def _collect_compile_file(self, file_list):
        self.file_list.extend(file_list)

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
                "-march=rv64gc_zicsr",
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
            gen_elf.save_cmd([*self.file_list, "-o", f"$OUTPUT_PATH/Testbench"])
        )

        gen_bin = ShellCommand("riscv64-unknown-elf-objcopy", ["-O", "binary"])
        self.baker.add_cmd(
            gen_bin.save_cmd(
                [f"$OUTPUT_PATH/Testbench", f"$OUTPUT_PATH/Testbench.bin"]
            )
        )

        # gen_hex = ShellCommand("od", ["-v", "-An", "-tx1"])
        # self.baker.add_cmd(
        #     gen_hex.save_cmd(
        #         [
        #             f"$OUTPUT_PATH/Testbench.bin",
        #             f"> $OUTPUT_PATH/Testbench.hex",
        #         ]
        #     )
        # )

        gen_asm = ShellCommand("riscv64-unknown-elf-objdump", ["-d"])
        self.baker.add_cmd(
            gen_asm.save_cmd(
                [
                    f"$OUTPUT_PATH/Testbench",
                    f"> $OUTPUT_PATH/Testbench.asm",
                ]
            )
        )

        dump_symbol = ShellCommand("nm")
        self.baker.add_cmd(
            dump_symbol.save_cmd(
                [
                    f"$OUTPUT_PATH/Testbench",
                    f"> $OUTPUT_PATH/Testbench.symbol",
                ]
            )
        )

    def run(self, cmd=None):
        self.baker.run(cmd)
    
    def _get_symbol_file(self, file_name):
        symbol_table = {}
        for line in open(file_name, "rt"):
            address, kind, symbol = line.strip().split()
            symbol_table[symbol] = int(address, base=16)
        return symbol_table

    def generate_variant(self):
        bin_dist = []

        mem_begin = 0x80000000
        mem_end   = 0x80040000

        symbol_table = self._get_symbol_file(os.path.join(self.output_path, 'Testbench.symbol'))

        file_origin = os.path.join(self.output_path, 'Testbench.bin')
        file_variant = os.path.join(self.output_path, 'Testbench.variant.bin')
        with open(file_origin, "rb") as file:
            origin_byte_array = bytearray(file.read())
        
        if self.virtual:
            address_base = 0
        else:
            address_base = 0x80000000
        
        if self.virtual:
            address_offset = 0x80000000
        else:
            address_offset = 0

        # init, secret, channel, mtrap, strap, data, random_data
        # origin_common
        # variant_common
        file_origin_common  = os.path.join(self.output_path, 'origin_common.bin')
        file_variant_common = os.path.join(self.output_path, 'variant_common.bin')

        common_begin = 0
        common_end   = symbol_table['_random_data_end'] - address_base
        common_byte_array = origin_byte_array[common_begin:common_end]
        with open(file_origin_common, "wb") as file:
            file.write(common_byte_array)

        secret_begin = symbol_table['_secret_start'] - address_base
        secret_end   = symbol_table['_secret_end'] - address_base
        origin_byte_array[secret_begin:secret_end] = bytes([i for i in range(0, secret_end - secret_begin)])
        with open(file_variant, "wb") as file:
            file.write(origin_byte_array)
        common_byte_array = origin_byte_array[common_begin:common_end]
        with open(file_variant_common, "wb") as file:
            file.write(common_byte_array)

        with open(file_variant, "wb") as file:
            file.write(origin_byte_array)
        
        bin_dist.append((mem_begin, [file_origin_common, file_variant_common]))

        # text_common
        file_text_common = os.path.join(self.output_path, 'text_common.bin')
        text_begin = symbol_table['_text_start'] - address_base
        text_end   = symbol_table['_text_end'] - address_base
        text_common_byte_array = origin_byte_array[text_begin:text_end]
        with open(file_text_common, "wb") as file:
            file.write(text_common_byte_array)
        
        bin_dist.append((text_begin + address_offset, [file_text_common]))

        # train_0, train_nop_0
        depth = self.config['fuzz']['transient_depth']
        for i in range(1, depth+1):
            file_text_train = os.path.join(self.output_path, f'text_train_{i}.bin')
            file_text_train_nop = os.path.join(self.output_path, f'text_train_nop_{i}.bin')
            text_train_begin = symbol_table[f'_text_train_{i}_start'] - address_base
            text_train_end   = symbol_table[f'_text_train_{i}_end'] - address_base
            text_train_byte_array = origin_byte_array[text_train_begin:text_train_end]
            with open(file_text_train, "wb") as file:
                file.write(text_train_byte_array)
            if i == depth:
                transient_begin = symbol_table['begin_access_secret'] - address_base
                transient_end = symbol_table['encode_exit'] - address_base
            else:
                transient_begin = symbol_table[f'transient_block_{i}_entry'] - address_base
                transient_end = symbol_table[f'transient_block_{i}_exit'] - address_base
            transient_begin -= text_train_begin
            transient_end   -= text_train_begin
            text_train_byte_array[transient_begin:transient_end] = bytes([0x01, 0x00] * ((transient_end - transient_begin)//2))
            with open(file_text_train_nop, "wb") as file:
                file.write(text_train_byte_array)
            
            bin_dist.append((text_train_begin + address_offset, [file_text_train, file_text_train_nop]))

        file_stack = os.path.join(self.output_path, f'stack.bin')
        with open(file_stack, "wb") as file:
                file.write(bytes([0x00]))
        bin_dist.append(((text_train_end + address_offset + Page.size)&~0xfff, [file_stack]))
        bin_dist.append((mem_end, (None)))

        file_bin_dist = os.path.join(self.output_path, f'bin_dist')
        with open(file_bin_dist, "wt") as file:
            file.write(f'{hex(mem_begin)} {hex(mem_end)}\n')
            for i, (addr_begin, file_list) in enumerate(bin_dist):
                if file_list == None:
                    break
                file.write(f'{hex(addr_begin)} {hex(bin_dist[i+1][0])} {" ".join(file_list)}\n')

        self.baker.reset()
        gen_hex = ShellCommand("od", ["-v", "-An", "-tx8"])

        self.baker.add_cmd(
            gen_hex.save_cmd(
                [
                    f"$OUTPUT_PATH/Testbench.bin",
                    f"> $OUTPUT_PATH/Testbench.hex",
                ]
            )
        )

        self.baker.add_cmd(
            gen_hex.save_cmd(
                [
                    f"$OUTPUT_PATH/Testbench.variant.bin",
                    f"> $OUTPUT_PATH/Testbench.variant.hex",
                ]
            )
        )
