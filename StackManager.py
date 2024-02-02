from SectionManager import *
from Utils import *

class StackPage(Page):
    def __init__(self,vaddr,paddr,flag):
        super().__init__(vaddr,paddr,flag)

    def generate_asm(self):
        return Asmer.space_inst(Page.size)

class StackSection(Section):
    def __init__(self,name,length,section_label=None,pages=[]):
        super().__init__(name,length,section_label,pages)
    
    def generate_asm(self):
        write_lines=super().generate_asm()
        write_lines.extend(Asmer.label_inst('stack_bottom'))
        return write_lines

class StackManager(SectionManager):
    def __init__(self,config):
        super().__init__(config)
    
    def _init_section_type(self):
        self.name_dict={}
        self.name_dict[Flag.U|Flag.R|Flag.W]=[".stack",StackSection,0]

    def _generate_pages(self):
        flag=Flag.U|Flag.R|Flag.W
        vaddr,paddr=self._get_new_page(flag)
        self._add_page_content(StackPage(vaddr,paddr,flag))
        
if __name__ == "__main__":
    import hjson
    file=open("distribute.hjson","rt")
    config=hjson.load(file)
    manager=StackManager(config['stack'])
    manager.file_generate('stack.S')
    print(manager.get_section_list())

        
            
