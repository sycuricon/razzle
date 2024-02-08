from SectionManager import *
from Utils import *

class ChannelPage(Page):
    def __init__(self,vaddr,paddr,flag,image_value):
        super().__init__(vaddr,paddr,flag)
        self.image_value=int(image_value,base=16)

    def generate_asm(self,is_variant):
        return Asmer.fill_inst(Page.size,1,self.image_value)

class ChannelSection(Section):
    def __init__(self,name,length,section_label=[],pages=[]):
        super().__init__(name,length,section_label,pages)

class ChannelManager(SectionManager):
    def __init__(self,config):
        super().__init__(config)
        self.image_value=config["image_value"]
    
    def _init_section_type(self):
        self.name_dict={}
        self.name_dict[Flag.U|Flag.R|Flag.W]=[".trapoline",ChannelSection,0,["trapoline","array"]]

    def _generate_pages(self):
        flag=Flag.U|Flag.R|Flag.W
        while not self._new_page_empty():
            vaddr,paddr=self._get_new_page(flag)
            self._add_page_content(ChannelPage(vaddr,paddr,flag,self.image_value))
        
if __name__ == "__main__":
    import hjson
    file=open("distribute.hjson","rt")
    config=hjson.load(file)
    manager=ChannelManager(config['channel'])
    manager.file_generate('channel.S')
    print(manager.get_section_list())

        
            
