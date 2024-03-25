import hjson
import argparse
import os
from ChannelManger import *
from PageTableManager import *
from LoaderManager import *
from SecretManager import *
from StackManager import *
from PocManager import *
from PayloadManager import *
from InitManager import *
from TransManager import *


class DistributeManager:
    def __init__(self, hjson_filename, output_path, virtual, do_fuzz):
        hjson_file = open(hjson_filename)
        config = hjson.load(hjson_file)
        hjson_file.close()

        self.output_path = output_path
        self.virtual = virtual

        self.code = {}
        self.code["secret"] = SecretManager(config["secret"])
        self.code["channel"] = ChannelManager(config["channel"])
        self.code["stack"] = StackManager(config["stack"])
        if do_fuzz:
            self.code["payload"] = TransManager(config["fuzz"])
        else:
            self.code["payload"] = PayloadManager(config["payload"])
            self.code["poc"] = PocManager(config["poc"])
        self.code["init"] = InitManager(config["init"], do_fuzz, virtual, output_path)

        self.page_table = PageTableManager(config["page_table"])
        self.loader = LoaderManager(virtual)

        self.file_list = []
        self.var_file_list = []

    def _collect_compile_file(self, file_list):
        self.file_list.extend(file_list[0])
        self.var_file_list.extend(file_list[1])

    def _generate_compile_file(self, filename, var_name, files_list):
        with open(filename, "wt") as f:
            f.write(var_name + "_C = \\\n")
            for file in files_list:
                if file.endswith(".c"):
                    f.write("\t" + file + " \\\n")
            f.write("\n")

            f.write(var_name + "_S = \\\n")
            for file in files_list:
                if file.endswith(".S"):
                    f.write("\t" + file + " \\\n")
            f.write("\n")

    def _generate_compile_files(self):
        origin_files = os.path.join(self.output_path, "origin_list.mk")
        variant_files = os.path.join(self.output_path, "variant_list.mk")
        self._generate_compile_file(origin_files, "ORIGIN_SRC", self.file_list)
        self._generate_compile_file(variant_files, "VARIANT_SRC", self.var_file_list)

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

        self._generate_compile_files()

        # os.system(f'make BUILD_PATH={self.output_path}')
        # os.system(f'make sim BUILD_PATH={self.output_path}')
