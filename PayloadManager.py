from FuzzManager import *
from Utils import *

class PayloadManager(FuzzManager):
    def __init__(self,config):
        super().__init__(config)
        self.folder=config["folder"]
    
    def _init_section_type(self):
        self.name_dict={}
        self.name_dict[Flag.U|Flag.X|Flag.R]=[".text",FuzzSection,0,[]]
        self.name_dict[Flag.U|Flag.R|Flag.W]=[".data",FuzzSection,0,[]]
    
    def get_section_list(self):
        section_list=super().get_section_list()
        section_list[0][1]=[
            '\t\t*(.text.init)\n'
            '\t\t*(.text.trap)\n'
            '\t\t*(.text*)\n'
        ]
        section_list[1][1]=[
            '\t\t*(.rodata)\n'
            '\t\t*(.data)\n'
            '\t\t__global_pointer$ = . + 0x800;\n'
            '\t\t*(.srodata.cst16) *(.srodata.cst8) *(.srodata.cst4) *(.srodata.cst2) *(.srodata*)\n'
            '\t\t*(.sdata .sdata.* .gnu.linkonce.s.*)\n'
            '\t\t*(.sbss .sbss.* .gnu.linkonce.sb.*)\n'
            '\t\t*(.scommon)\n'
            '\t\t*(.bss)\n'
            '\t\t*(.tdata)\n'
            '\t\t*(.tbss)\n'
        ]
        return section_list
    
    def _generate_pages(self):
        flag=Flag.U|Flag.X|Flag.R
        vaddr,paddr=self._get_new_page(flag)
        self._add_page_content(FuzzPage(paddr,paddr,flag))
        flag=Flag.U|Flag.X|Flag.R
        vaddr,paddr=self._get_new_page(flag)
        self._add_page_content(FuzzPage(vaddr,paddr,flag))
        flag=Flag.U|Flag.X|Flag.R
        vaddr,paddr=self._get_new_page(flag)
        self._add_page_content(FuzzPage(vaddr,paddr,flag))
        flag=Flag.U|Flag.X|Flag.R
        vaddr,paddr=self._get_new_page(flag)
        self._add_page_content(FuzzPage(vaddr,paddr,flag))
        flag=Flag.U|Flag.W|Flag.R
        vaddr,paddr=self._get_new_page(flag)
        self._add_page_content(FuzzPage(vaddr,paddr,flag))
        
if __name__ == "__main__":
    import hjson
    file=open("distribute.hjson","rt")
    config=hjson.load(file)
    manager=PayloadManager(config['payload'])
    manager.file_generate('','payload.S')
    print(manager.get_section_list())

            
