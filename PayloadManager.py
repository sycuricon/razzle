from FileManager import *
from Utils import *

class PayloadManager(FileManager):
    def __init__(self,config):
        super().__init__(config)

    def _generate_sections(self):
        trap_link=[
            '\t\t*(.text.entry)\n'
            '\t\t*(.text.trap)\n'
            '\t\t*(.data.trap)\n'
        ]
        self.section['.entry']=FileSection('.entry',Flag.U|Flag.X|Flag.R,trap_link)

        text_link=[
            '\t\t*(.text)\n'
        ]
        self.section['.text']=FileSection('.text',Flag.U|Flag.X|Flag.R,text_link)

        data_link=[
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
        self.section['.data']=FileSection('.data',Flag.U|Flag.R|Flag.W,data_link)

    def _distribute_address(self):
        self.section['.entry'].get_bound(self.memory_bound[0][0],self.memory_bound[0][0],0x1000)
        self.section['.text'].get_bound(self.virtual_memory_bound[0][0]+0x1000,self.memory_bound[0][0]+0x1000,0x3000)
        self.section['.data'].get_bound(self.virtual_memory_bound[0][0]+0x4000,self.memory_bound[0][0]+0x4000,0x1000)
        
if __name__ == "__main__":
    import hjson
    file=open("distribute.hjson","rt")
    config=hjson.load(file)
    manager=PayloadManager(config['payload'])
    manager.file_generate('','payload.S')
    print(manager.get_section_list())

            
