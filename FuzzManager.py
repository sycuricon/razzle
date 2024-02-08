from SectionManager import *
from Utils import *

class FuzzPage(Page):
    def __init__(self,vaddr,paddr,flag):
        super().__init__(vaddr,paddr,flag)

    def generate_asm(self,is_variant):
        pass

class FuzzSection(Section):
    def __init__(self,name,length,section_label=[],pages=[]):
        super().__init__(name,length,section_label,pages)

class FuzzManager(SectionManager):
    def __init__(self,config):
        super().__init__(config)

    def file_generate(self,path,name):
        self._generate_pages()
        self._generate_section_list()
        filename=[]
        for folder in self.folder:
            os.system("cp "+folder+'/* '+path)
            files=list(filter(lambda filename:filename.endswith(('.S','.c')),os.listdir(folder)))
            filename.extend(files)
        for i in range(len(filename)):
            filename[i]=os.path.join(path,filename[i])
        return [filename,filename]

        
            
