from FuzzManager import *
from Utils import *

class PocManager(FuzzManager):
    def __init__(self,config):
        super().__init__(config)
        self.folder=config["folder"]
    
    def _init_section_type(self):
        self.name_dict={}
        self.name_dict[Flag.U|Flag.X|Flag.R]=[".poc.text",FuzzSection,0,[]]
        self.name_dict[Flag.U|Flag.R|Flag.W]=[".poc.data",FuzzSection,0,[]]

    def _generate_pages(self):
        flag=Flag.U|Flag.X|Flag.R
        vaddr,paddr=self._get_new_page(flag)
        self._add_page_content(FuzzPage(vaddr,paddr,flag))

    def file_generate(self,path,name):
        self._generate_pages()
        self._generate_section_list()
        for folder in self.folder:
            os.system("cp "+folder+'/* '+path)
        
        


        
            
