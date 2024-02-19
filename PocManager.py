from FileManager import *
from Utils import *

class PocManager(FileManager):
    def __init__(self,config):
        super().__init__(config)
    
    def _init_section_type(self):
        self.name_dict={}
        self.name_dict[Flag.U|Flag.X|Flag.R]=[".poc.text",FileSection,0,[]]
        self.name_dict[Flag.U|Flag.R|Flag.W]=[".poc.data",FileSection,0,[]]

    def _generate_pages(self):
        flag=Flag.U|Flag.X|Flag.R
        vaddr,paddr=self._get_new_page(flag)
        self._add_page_content(FilePage(vaddr,paddr,flag))

    
        
        


        
            
