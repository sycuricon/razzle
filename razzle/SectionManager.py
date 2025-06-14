import os
from SectionUtils import *


class Section:
    def __init__(self, name, flag):
        self.name = name
        self.flag = flag
        self.length = None
        self.vaddr = None
        self.paddr = None
        self.link = None
        self.must_m = False
        self.global_label = []

    def get_length(self):
        return self.length

    def get_bound(self, vaddr, paddr, length, must_m=False):
        if vaddr is not None:
            self.vaddr = vaddr
        if paddr is not None:
            self.paddr = paddr
        if length is not None:
            self.length = length
        self.must_m = must_m

    def add_global_label(self, global_list):
        self.global_label.extend(global_list)

    def _generate_global(self):
        write_lines = []
        for label in self.global_label:
            write_lines.extend(Asmer.global_inst(label))
        return write_lines

    def _generate_header(self):
        return Asmer.section_inst(self.name, self.flag)

    def _generate_body(self):
        return []

    def generate_asm(self):
        write_lines = []
        write_lines.extend(self._generate_global())
        write_lines.extend(self._generate_header())
        write_lines.extend(self._generate_body())
        return write_lines

    def get_section_info(self):
        info = {
            "name": self.name,
            "vaddr": self.vaddr,
            "paddr": self.paddr,
            "length": self.length,
            "flag": self.flag,
            "must_m": self.must_m,
            "link": self.link,
        }
        return info


class FileSection(Section):
    def __init__(self, name, flag, link):
        super().__init__(name, flag)
        self.link = link


class SectionManager:
    def __init__(self, config):
        self.memory_bound = []
        self.virtual_memory_bound = []
        for begin, end in zip(config["bound"][0::2], config["bound"][1::2]):
            begin = int(begin, base=16)
            end = int(end, base=16)
            self.memory_bound.append((begin, end))
        for begin, end in zip(
            config["virtual_bound"][0::2], config["virtual_bound"][1::2]
        ):
            begin = int(begin, base=16)
            end = int(end, base=16)
            self.virtual_memory_bound.append((begin, end))
        self.section = {}

        # TODO: optimize this
        template_file = []

        if "folder" in config:
            for folder in config["folder"]:
                folder = os.path.join(os.environ["RAZZLE_ROOT"], folder)
                files = list(
                    filter(
                        lambda filename: filename.endswith((".S", ".c")),
                        os.listdir(folder),
                    )
                )
                for file in files:
                    file = os.path.join(folder, file)
                    template_file.append(file)

        if "file" in config:
            for file in config["file"]:
                file = os.path.join(os.environ["RAZZLE_ROOT"], file)
                template_file.append(file)

        self.dut_file_list = template_file

    def get_section_list(self):
        section_info_list = []
        for section in self.section.values():
            section_info_list.append(section.get_section_info())
        return section_info_list

    def _write_sections(self, f):
        for section in self.section.values():
            asm_list = section.generate_asm()
            f.writelines(asm_list)

    def _generate_sections(self):
        pass

    def _distribute_address(self):
        pass

    def _write_headers(self, file):
        pass

    def _write_file(self, path, name):
        filename = os.path.join(path, name)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "wt") as f:
            self._write_headers(f)
            self._write_sections(f)
        self.dut_file_list = [os.path.join(path, name)]

    def file_generate(self, path, name):
        self._generate_sections()
        self._distribute_address()
        self._write_file(path, name)
        return self.dut_file_list
