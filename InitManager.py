from FileManager import *
from Utils import *

class InitManager(FileManager):
    def __init__(self,config):
        super().__init__(config)
    
    def _init_section_type(self):
        self.name_dict={}
        self.name_dict[Flag.U|Flag.X|Flag.R]=[".init",FileSection,0,[]]

    def _generate_pages(self):
        flag=Flag.U|Flag.X|Flag.R
        vaddr,paddr=self._get_new_page(flag)
        self._add_page_content(FilePage(vaddr,paddr,flag))
    
    def get_section_list(self):
        section_list=super().get_section_list()
        section_list[0][1]=[
            # '\t\t*(.text.init)\n'
            '\t\t*(.text.init)\n'
            '\t\t*(.data.init)\n'
        ]
        return section_list

    
        
        


        
            
