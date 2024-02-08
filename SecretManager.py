from SectionManager import *
from Utils import *

class SecretPage(Page):
    def __init__(self,vaddr,paddr,flag,secret,secret_variant,offset,length):
        super().__init__(vaddr,paddr,flag)
        self.secret=secret[offset:offset+length]
        self.secret_variant=secret_variant[offset:offset+length]

    def generate_asm(self,is_variant):
        if is_variant:
            return Asmer.byte_inst(self.secret_variant)
        else:
            return Asmer.byte_inst(self.secret)

class SecretSection(Section):
    def __init__(self,name,length,section_label=[],pages=[]):
        super().__init__(name,length,section_label,pages)

class SecretManager(SectionManager):
    def __init__(self,config):
        super().__init__(config)
        self.secret=config["secret_value"]
        self.secret_variant=config["secret_value_variant"]
    
    def _init_section_type(self):
        self.name_dict={}
        self.name_dict[Flag.U|Flag.R|Flag.W]=[".secret",SecretSection,0,["secret"]]

    def _generate_pages(self):
        flag=Flag.U|Flag.R|Flag.W
        vaddr,paddr=self._get_new_page(flag)
        length=min(0x1000,len(self.secret))
        self._add_page_content(SecretPage(vaddr,paddr,flag,self.secret,self.secret_variant,0,length))
    
    def file_generate(self,path,name):
        filename=os.path.join(path,name)
        self._generate_pages()
        self._generate_section_list()
        with open(filename,"wt") as f:
            self._generate_sections(f,False)
        var_filename=os.path.join(path,"variant_"+name)
        with open(var_filename,"wt") as f:
            self._generate_sections(f,True)
        return [[filename],[var_filename]]
        
if __name__ == "__main__":
    import hjson
    file=open("distribute.hjson","rt")
    config=hjson.load(file)
    manager=SecretManager(config['secret'])
    manager.file_generate('secret.S')
    print(manager.get_section_list())

        
            
