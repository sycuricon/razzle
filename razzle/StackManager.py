from SectionManager import *
from SectionUtils import *


class StackSection(Section):
    def __init__(self, name, length):
        super().__init__(name, Flag.U | Flag.W | Flag.R)
        self.length = length
        self.global_label = ["stack_bottom", "stack_top"]

    def _generate_body(self, is_variant):
        write_line = []
        write_line.extend(Asmer.label_inst("stack_top"))
        write_line.extend(Asmer.space_inst(self.length))
        write_line.extend(Asmer.label_inst("stack_bottom"))
        return write_line


class StackManager(SectionManager):
    def __init__(self, config):
        super().__init__(config)

    def _generate_sections(self):
        self.section["stack"] = StackSection(
            ".stack", self.memory_bound[0][1] - self.memory_bound[0][0]
        )

    def _distribute_address(self):
        self.section["stack"].get_bound(
            self.virtual_memory_bound[0][0], self.memory_bound[0][0], None
        )


if __name__ == "__main__":
    import hjson

    file = open("mem_init.hjson", "rt")
    config = hjson.load(file)
    manager = StackManager(config["stack"])
    manager.file_generate(".", "stack.S")
    print(manager.get_section_list())
