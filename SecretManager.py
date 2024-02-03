from SectionManager import *
from Utils import *

class SecretPage(Page):
    def __init__(self,vaddr,paddr,flag,secret,offset,length):
        super().__init__(vaddr,paddr,flag)
        self.content=secret[offset:offset+length]

    def generate_asm(self):
        return Asmer.string_inst(self.content)

class SecretSection(Section):
    def __init__(self,name,length,section_label=[],pages=[]):
        super().__init__(name,length,section_label,pages)

class SecretManager(SectionManager):
    def __init__(self,config):
        super().__init__(config)
        self.secret=config["secret_value"]
    
    def _init_section_type(self):
        self.name_dict={}
        self.name_dict[Flag.U|Flag.R|Flag.W]=[".secret",SecretSection,0,["secret"]]

    def _generate_pages(self):
        flag=Flag.U|Flag.R|Flag.W
        vaddr,paddr=self._get_new_page(flag)
        length=min(0x1000,len(self.secret))
        self._add_page_content(SecretPage(vaddr,paddr,flag,self.secret,0,length))
        
if __name__ == "__main__":
    import hjson
    file=open("distribute.hjson","rt")
    config=hjson.load(file)
    manager=SecretManager(config['secret'])
    manager.file_generate('secret.S')
    print(manager.get_section_list())

        
            
