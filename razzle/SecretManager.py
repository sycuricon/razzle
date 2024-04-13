from SectionManager import *
from SectionUtils import *


class SecretSection(Section):
    def __init__(self, name, length, secret):
        super().__init__(name, Flag.U | Flag.W | Flag.R)
        self.length = length
        self.global_label = ["secret"]
        self.secret = secret

    def _generate_body(self):
        write_line = []
        write_line.extend(Asmer.label_inst("secret"))
        write_line.extend(Asmer.byte_inst(self.secret))

        return write_line


class SecretManager(SectionManager):
    def __init__(self, config):
        super().__init__(config)
        self.secret = config["secret_value"]

    def _generate_sections(self):
        self.section["secret"] = SecretSection(
            ".secret",
            self.memory_bound[0][1] - self.memory_bound[0][0],
            self.secret
        )

    def _distribute_address(self):
        self.section["secret"].get_bound(
            self.virtual_memory_bound[0][0], self.memory_bound[0][0], None
        )


if __name__ == "__main__":
    import hjson

    file = open("mem_init.hjson", "rt")
    config = hjson.load(file)
    manager = SecretManager(config["secret"])
    manager.file_generate(".", "secret.S")
    print(manager.get_section_list())
