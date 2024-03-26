from BuildManager import *
from SectionUtils import *


class PocManager(FileManager):
    def __init__(self, config):
        super().__init__(config)

    def _generate_sections(self):
        self.section["poc.text"] = FileSection(
            ".poc.text", Flag.U | Flag.X | Flag.R, None
        )

    def _distribute_address(self):
        self.section["poc.text"].get_bound(
            self.virtual_memory_bound[0][0], self.memory_bound[0][0], 0x1000
        )
