from SectionManager import *
from SectionUtils import *


class PageTablePage:
    def __init__(self, xLen, pg_level):
        self.pg_level = pg_level
        self.entry_num = 512 if xLen == 64 else 1024
        self.index_width = 9 if xLen == 64 else 10
        self.entry_byte = 8 if xLen == 64 else 4
        self.content = [0] * self.entry_num
        self.stage_array = [0] * self.entry_num
        self.vaddr_array = [0] * self.entry_num

    def is_valid(self, entry_num):
        return (self.content[entry_num] & Flag.V) != 0

    def entry_stage(self, entry_num):
        return self.stage_array[entry_num]

    def fill_entry(self, entry_num, paddr, flag, stage, vaddr):
        self.content[entry_num] = ((paddr >> 12) << 10) | flag
        self.stage_array[entry_num] = stage
        self.vaddr_array[entry_num] = vaddr

    def generate_asm(self):
        write_lines = []
        empty_entry = 0
        for i in range(self.entry_num):
            entry_value = self.content[i]
            if self.is_valid(i):
                if empty_entry != 0:
                    write_lines.extend(Asmer.space_inst(self.entry_byte * empty_entry))
                    empty_entry = 0
                if self.stage_array[i] == self.pg_level - 1:
                    write_lines.extend(
                        Asmer.label_inst(
                            "vaddr_"
                            + hex(self.vaddr_array[i])
                            + "_paddr_"
                            + hex((self.content[i] >> 10) << 12)
                        )
                    )
                if self.entry_byte == 8:
                    write_lines.extend(Asmer.quad_inst(entry_value))
                else:
                    write_lines.extend(Asmer.word_inst(entry_value))
            else:
                empty_entry += 1
        if empty_entry != 0:
            write_lines.extend(Asmer.space_inst(self.entry_byte * empty_entry))
        return write_lines


class PageTableSection(Section):
    def __init__(self, name, pg_level, page_table):
        super().__init__(name, Flag.U | Flag.W | Flag.R)
        self.length = pg_level * Page.size
        self.global_label = ["root_page_table"]
        self.pg_level = pg_level
        self.page_table = page_table

    def _generate_body(self):
        write_line = []
        write_line.extend(Asmer.label_inst("root_page_table"))
        for page in self.page_table:
            write_line.extend(page.generate_asm())
        return write_line


class PageTableManager(SectionManager):
    def __init__(self, config):
        super().__init__(config)
        self.xLen = config["xLen"]
        self.pg_level = config["pg_level"]
        self.page_tables = []
        self.pgtlb_flag = []
        assert (
            self.memory_bound[0][1] - self.memory_bound[0][0]
            >= self.pg_level * Page.size
        )
        paddrs = list(
            range(
                self.memory_bound[0][0],
                self.memory_bound[0][0] + self.pg_level * Page.size,
                Page.size,
            )
        )
        self.page_tables = [
            PageTablePage(self.xLen, self.pg_level) for i in range(self.pg_level)
        ]
        self.pgtlb_paddr = paddrs[1:] + [0]
        self.pgtlb_flag = [Flag.V] * (self.pg_level - 1) + [0]
        self.index_width = 9 if self.xLen == 64 else 10

    def _register_page(self, vaddr, paddr, flag):
        self.pgtlb_paddr[-1] = paddr
        self.pgtlb_flag[-1] = flag | Flag.A | Flag.D | Flag.V

        old_vaddr = vaddr
        vaddr >>= 12
        mask = (1 << self.index_width) - 1
        for i in range(self.pg_level):
            entry_num = vaddr & mask
            vaddr >>= self.index_width
            stage = self.pg_level - i - 1
            if (
                stage == self.pg_level - 1
                and not self.page_tables[stage].is_valid(entry_num)
                or stage != self.pg_level - 1
                and self.page_tables[stage].entry_stage(entry_num) != self.pg_level - 1
            ):
                self.page_tables[stage].fill_entry(
                    entry_num,
                    self.pgtlb_paddr[stage],
                    self.pgtlb_flag[stage],
                    stage,
                    old_vaddr,
                )
            else:
                raise "virtual address is conflicted"

    def register_sections(self, section_list):
        for info in section_list:
            if info["must_m"]:
                continue
            vaddr = info["vaddr"]
            paddr = info["paddr"]
            flag = info["flag"]
            length = info["length"]
            if vaddr == paddr:
                continue
            for offset in range(0, length, Page.size):
                vaddr_offset = vaddr + offset
                paddr_offset = paddr + offset
                vaddr_virtual_offset = vaddr_offset + 0xFFFFFFFFFFF00000
                self._register_page(vaddr_offset, paddr_offset, flag)
                self._register_page(vaddr_virtual_offset, paddr_offset, flag & ~Flag.U)

    def _generate_sections(self):
        self.section["pagetable"] = PageTableSection(
            ".pagetable", self.pg_level, self.page_tables
        )
        self.section["pagetable"].add_global_label(["vaddr_0x4000_paddr_0x80004000"])
        self.section["pagetable"].add_global_label(["vaddr_0xfffffffffff04000_paddr_0x80004000"])

    def _distribute_address(self):
        self.section["pagetable"].get_bound(
            self.virtual_memory_bound[0][0], self.memory_bound[0][0], None
        )
