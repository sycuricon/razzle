class SectionManager:
    def __init__(self,config,page_manager):
        self.memory_bound=[]
        self.memory_pool=[]
        self.virtual_memory_bound=[]
        self.virtual_memory_pool=[]
        for begin,end in config["bound"][0::2],config["bound"][1::2]:
            begin=int(begin,base=16)
            end=int(end,base=16)
            self.memory_bound.append((begin,end))
            self.memory_pool.extend(list(range(begin,end,0x1000)))
        for begin,end in config["virtual_bound"][0::2],config["virtual_bound"][1::2]:
            begin=int(begin,base=16)
            end=int(end,base=16)
            self.virtual_memory_bound.append((begin,end))
            self.virtual_memory_pool.extend(list(range(begin,end,0x1000)))
        self.section=[]
        self.page_manager=page_manager

    def get_new_page(self):
        if len(self.memory_pool) == 0 or len(self.virtual_memory_pool) == 0:
            raise "no memory in memory pool"
        paddr=self.memory_pool[0]
        vaddr=self.virtual_memory_pool[0]
        self.memory_pool.pop(0)
        self.virtual_memory_pool.pop(0)
        self.page_manager.add_page(vaddr,paddr)
        return paddr,vaddr
    
    def get_section_list(self):
        return self.section
    
    def add_section(self,name,vaddr,paddr):
        self.section.append((name,vaddr,paddr))
    
    def file_generate(self,filename):
        pass