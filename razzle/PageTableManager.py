from SectionManager import *
from SectionUtils import *
import hjson
import random

class PageTablePage:
    def __init__(self, xLen, paddr, pg_level):
        self.entry_num = 512 if xLen == 64 else 1024
        self.index_width = 9 if xLen == 64 else 10
        self.entry_byte = 8 if xLen == 64 else 4
        self.content = [0] * self.entry_num
        self.page_array = [None] * self.entry_num
        self.vaddr_array = [0] * self.entry_num
        self.paddr = paddr
        self.pg_level = pg_level

    def is_valid(self, entry_num):
        return (self.content[entry_num] & Flag.V) != 0
    
    def get_next_table(self, entry_num):
        return self.page_array[entry_num]

    def fill_entry(self, entry_num, paddr, flag, vaddr, page_table):
        self.content[entry_num] = ((paddr >> 12) << 10) | flag
        self.page_array[entry_num] = page_table
        self.vaddr_array[entry_num] = vaddr

    def generate_asm(self):
        write_lines = []
        write_lines.extend(
            Asmer.label_inst(
                f'paddr_{hex(self.paddr)}'
            )
        )
        empty_entry = 0
        for i in range(self.entry_num):
            entry_value = self.content[i]
            if self.is_valid(i):
                if empty_entry != 0:
                    write_lines.extend(Asmer.space_inst(self.entry_byte * empty_entry))
                    empty_entry = 0
                mask = (1 << (self.index_width * (self.pg_level - self.stage_num - 1) + 12)) - 1
                write_lines.extend(
                    Asmer.label_inst(
                        "vaddr_"
                        + hex(self.vaddr_array[i] | mask)
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
        self.free_page_tables = [
            PageTablePage(self.xLen, paddr, self.pg_level)
            for paddr in range(
                self.memory_bound[0][0],
                self.memory_bound[0][1],
                Page.size,
            )
        ]
        self.root_page_tables = self._alloc_free_page(0)
        self.index_width = 9 if self.xLen == 64 else 10
    
    def _alloc_free_page(self, stage_num):
        if len(self.free_page_tables) == 0:
            raise Exception("no free page table in free_page_tables")
        self.page_tables.append(self.free_page_tables.pop(0))
        self.page_tables[-1].stage_num = stage_num
        return self.page_tables[-1]

    def _register_page(self, vaddr, paddr, flag):
        pgtlb_flag = flag | Flag.A | Flag.D | Flag.V

        old_vaddr = vaddr
        vaddr >>= 12
        mask = (1 << self.index_width) - 1
        page_table = self.root_page_tables
        for i in range(self.pg_level):
            offset = self.index_width * (self.pg_level - i - 1)
            entry_num = (vaddr >> offset) & mask
            if not page_table.is_valid(entry_num):
                next_paddr = paddr
                next_page_table = None
                if i != self.pg_level - 1:
                    next_page_table = self._alloc_free_page(i + 1)
                    next_paddr = next_page_table.paddr
                page_table.fill_entry(entry_num, next_paddr, flag, old_vaddr, next_page_table)
            if i != self.pg_level - 1:
                page_table = page_table.get_next_table(entry_num)
    
    def load_config(self, filename):
        def str2int(value):
            if type(value) is not int:
                try:
                    if value.startswith('0x'):
                        value = int(value, base=16)
                    elif value.startswith('0b'):
                        value = int(value, base=2)
                    else:
                        value = int(value, base=10)
                except ValueError:
                    value = value
            return value

        with open(filename) as file:
            config = hjson.loads(file.read())
        section_list = []
        for entry_config in config:
            flag = 0
            for key, value in zip(['V', 'W', 'R', 'X', 'U'], [Flag.V, Flag.W, Flag.R, Flag.X, Flag.U]):
                if key in entry_config:
                    if entry_config[key] == 1:
                        flag |= value
                elif random.randint(0, 1) == 1:
                    flag |= value
            flag |= Flag.D | Flag.A

            info = {
                "name": entry_config['name'],
                "vaddr": str2int(entry_config['vaddr']),
                "paddr": str2int(entry_config['paddr']),
                "length": str2int(entry_config['length']),
                "flag": flag,
                "must_m": bool(entry_config.get('must_m', False)),
                "link": entry_config.get('link', ""),
            }

            section_list.append(info)
            
        with open('./config/temp1', 'wt') as file:
            hjson.dump(section_list, file)
            
        self.register_sections(section_list)

    def register_sections(self, section_list):
        for info in section_list:
            if info["must_m"]:
                continue
            vaddr = info["vaddr"]
            paddr = info["paddr"]
            flag = info["flag"]
            length = info["length"]
            # if vaddr == paddr:
            #     continue
            for offset in range(0, length, Page.size):
                vaddr_offset = vaddr + offset
                paddr_offset = paddr + offset
                vaddr_virtual_offset = vaddr_offset + 0xFFFFFFFF00000000
                self._register_page(vaddr_offset, paddr_offset, flag | Flag.U)
                self._register_page(vaddr_virtual_offset, paddr_offset, flag & ~Flag.U)

    def _generate_sections(self):
        self.section["pagetable"] = PageTableSection(
            ".pagetable", self.pg_level, self.page_tables
        )
        self.section["pagetable"].add_global_label(["vaddr_0x80007000_paddr_0x80007000"])
        self.section["pagetable"].add_global_label(["vaddr_0xffffffff80004000_paddr_0x80007000"])

    def _distribute_address(self):
        self.section["pagetable"].get_bound(
            self.virtual_memory_bound[0][0], self.memory_bound[0][0], None
        )
