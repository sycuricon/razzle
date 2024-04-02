from SectionManager import *
from SectionUtils import *


class SecretSection(Section):
    def __init__(self, name, length, secret, secret_variant):
        super().__init__(name, Flag.U | Flag.W | Flag.R)
        self.length = length
        self.global_label = ["secret"]
        self.secret = secret
        self.secret_variant = secret_variant

    def _generate_body(self, is_variant):
        write_line = []
        write_line.extend(Asmer.label_inst("secret"))
        if is_variant:
            write_line.extend(Asmer.byte_inst(self.secret_variant))
        else:
            write_line.extend(Asmer.byte_inst(self.secret))
        return write_line


class SecretManager(SectionManager):
    def __init__(self, config):
        super().__init__(config)
        self.secret = config["secret_value"]
        self.secret_variant = config["secret_value_variant"]

    def _generate_sections(self):
        self.section["secret"] = SecretSection(
            ".secret",
            self.memory_bound[0][1] - self.memory_bound[0][0],
            self.secret,
            self.secret_variant,
        )

    def _distribute_address(self):
        self.section["secret"].get_bound(
            self.virtual_memory_bound[0][0], self.memory_bound[0][0], None
        )

    def _write_file(self, path, name):
        filename = os.path.join(path, name)
        with open(filename, "wt") as f:
            self._write_sections(f, False)
        var_filename = os.path.join(path, "variant_" + name)
        with open(var_filename, "wt") as f:
            self._write_sections(f, True)
        self.dut_file_list.append(f"$OUTPUT_PATH/{name}")
        self.vnt_file_list.append(f"$OUTPUT_PATH/variant_{name}")


if __name__ == "__main__":
    import hjson

    file = open("mem_init.hjson", "rt")
    config = hjson.load(file)
    manager = SecretManager(config["secret"])
    manager.file_generate(".", "secret.S")
    print(manager.get_section_list())
