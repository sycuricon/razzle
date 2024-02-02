from SectionManager import *
from Assembler import Asmer

class SecretPage(Page):
    def __init__(self,secret,offset,length):
        super().__init__()
        self.content=secret[offset:offset+length]

    def generate_asm(self):
        return Asmer.string_inst(self.content)

class SecretSection(Section):
    def __init__(self,name,vaddr,paddr,length,flag,section_label=None,pages=[]):
        super().__init__(name,vaddr,paddr,length,flag,section_label,pages)

class SecretManager(SectionManager):
    def __init__(self,config):
        super().__init__(config)
        self.secret=config["secret_value"]
    
    def _init_section_type(self):
        self.name_dict={}
        self.name_dict[self.flag.U|self.flag.R|self.flag.W]=[".secret",SecretSection,0]

    def _generate_pages(self):
        flag=self.flag.U|self.flag.R|self.flag.W
        vaddr,paddr=self._get_new_page(flag)
        length=min(0x1000,len(self.secret))
        self._add_page_content(vaddr,SecretPage(self.secret,0,length))
        
if __name__ == "__main__":
    import hjson
    file=open("distribute.hjson","rt")
    config=hjson.load(file)
    manager=SecretManager(config['secret'])
    manager.file_generate('secret.S')
    print(manager.get_section_list())

        
            
