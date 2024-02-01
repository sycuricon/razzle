class SectionManager:
    def __init__(self,config,page_manager):
        self.memory_bound=[]
        self.memory_pool=[]
        for begin,end in config["bound"][0::2],config["bound"][1::2]:
            begin=int(begin,base=16)
            end=int(end,base=16)
            self.memory_bound.append((begin,end))
            self.memory_pool.extend(list(range(begin,end,0x1000)))
        self.section=[]
        self.page_manager=page_manager

    def get_new_page(self):
        if len(self.memory_pool) == 0:
            raise "no memory in memory pool"
        page_addr=self.memory_pool[0]
        self.memory_pool.pop(0)
        self.page_manager.add_page(page_addr)
        return page_addr
    
    def get_section_list(self):
        return self.section