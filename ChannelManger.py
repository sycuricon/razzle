from SectionManager import *
from Assembler import Asmer

class ChannelPage(Page):
    def __init__(self,image_value):
        super().__init__()
        self.image_value=int(image_value,base=16)

    def generate_asm(self):
        return Asmer.fill_inst(Page.size,1,self.image_value)

class ChannelSection(Section):
    def __init__(self,name,vaddr,paddr,length,flag,section_label=None,pages=[]):
        super().__init__(name,vaddr,paddr,length,flag,section_label,pages)

class ChannelManager(SectionManager):
    def __init__(self,config):
        super().__init__(config)
        self.image_value=config["image_value"]
    
    def _init_section_type(self):
        self.name_dict={}
        self.name_dict[self.flag.U|self.flag.R|self.flag.W]=[".trapoline",ChannelSection,0]

    def _generate_pages(self):
        flag=self.flag.U|self.flag.R|self.flag.W
        while not self._new_page_empty():
            vaddr,paddr=self._get_new_page(flag)
            self._add_page_content(vaddr,ChannelPage(self.image_value))
        
if __name__ == "__main__":
    import hjson
    file=open("distribute.hjson","rt")
    config=hjson.load(file)
    manager=ChannelManager(config['channel'])
    manager.file_generate('channel.S')
    print(manager.get_section_list())

        
            
