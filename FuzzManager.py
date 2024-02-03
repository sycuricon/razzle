from SectionManager import *
from Utils import *

class FuzzPage(Page):
    def __init__(self,vaddr,paddr,flag):
        super().__init__(vaddr,paddr,flag)

    def generate_asm(self):
        pass

class FuzzSection(Section):
    def __init__(self,name,length,section_label=[],pages=[]):
        super().__init__(name,length,section_label,pages)

class FuzzManager(SectionManager):
    def __init__(self,config):
        super().__init__(config)

        
            
