from Assembler import Asmer

class Flag:
    D=1<<7
    A=1<<6
    G=1<<5
    U=1<<4
    X=1<<3
    W=1<<2
    R=1<<1
    V=1

class Page:
    size=0x1000

    def __init__(self,vaddr,paddr,flag):
        self.vaddr=vaddr
        self.paddr=paddr
        self.flag=flag
        self.global_label=[]

    def generate_asm(self):
        return []

    def global_label(self):
        return self.global_label
    
    def add_global_label(self,label):
        self.global_label.append(label)

class Section:
    def __init__(self,name,length,section_label=None,pages=[]):
        self.name=name
        self.vaddr=pages[0].vaddr
        self.paddr=pages[0].paddr
        self.length=length
        self.flag=pages[0].flag
        self.section_label=section_label
        self.pages=pages
    
    def _generate_global(self):
        write_lines=[]
        write_lines.extend(Asmer.global_inst(self.section_label))
        for page in self.pages:
            for label in page.global_label:
                write_lines.extend(Asmer.global_inst(label))
        return write_lines

    def generate_asm(self):
        write_lines=[]
        write_lines.extend(self._generate_global())
        write_lines.extend(Asmer.section_inst(self.name))
        write_lines.extend(Asmer.label_inst(self.section_label))
        for page in self.pages:
            write_lines.extend(page.generate_asm())
        return write_lines

    def get_section_info(self):
        return (self.name,self.vaddr,self.paddr,self.length,self.flag)

class SectionManager:
    def __init__(self,config):
        self._init_section_type()

        self.memory_bound=[]
        self.memory_pool=[]
        self.virtual_memory_bound=[]
        self.virtual_memory_pool=[]
        for begin,end in zip(config["bound"][0::2],config["bound"][1::2]):
            begin=int(begin,base=16)
            end=int(end,base=16)
            self.memory_bound.append((begin,end))
            self.memory_pool.extend(list(range(begin,end,Page.size)))
        for begin,end in zip(config["virtual_bound"][0::2],config["virtual_bound"][1::2]):
            begin=int(begin,base=16)
            end=int(end,base=16)
            self.virtual_memory_bound.append((begin,end))
            self.virtual_memory_pool.extend(list(range(begin,end,Page.size)))
        self.use_page=[]
        self.section=[]
    
    def _new_page_empty(self):
        return len(self.memory_pool) == 0 or len(self.virtual_memory_pool) == 0
    
    def _choose_new_page(self,flag):
        if self._new_page_empty():
            raise "no memory in memory pool"
        paddr=self.memory_pool[0]
        vaddr=self.virtual_memory_pool[0]
        self.memory_pool.pop(0)
        self.virtual_memory_pool.pop(0)
        return vaddr,paddr

    def _get_new_page(self,flag):
        vaddr,paddr=self._choose_new_page(flag)
        return vaddr,paddr
    
    def _add_page_content(self,page):
        self.use_page.append(page)
    
    def _init_section_type(self):
        self.name_dict={}
        self.name_dict[Flag.U|Flag.R]=[".rodata",Section,0]
        self.name_dict[Flag.U|Flag.R|Flag.W]=[".data",Section,0]
        self.name_dict[Flag.U|Flag.R|Flag.X]=[".text",Section,0]

    def _get_section_type(self,flag):
        name,section,num=self.name_dict[flag]
        self.name_dict[flag][2]+=1
        return name if num==0 else name+str(num),section
    
    def _add_new_section(self,pages,length_base):
        name,section=self._get_section_type(pages[0].flag)
        self.section.append(section(name,length_base,name[1:],pages))
    
    def _generate_section_list(self):
        def _sort_key(item):
            return item.vaddr
        self.use_page=sorted(self.use_page,key=_sort_key)
        pages=[]
        pages.append(self.use_page[0])
        length_base=Page.size
        for page in self.use_page[1:]:
            if(page.vaddr==pages[0].vaddr+length_base and\
                page.paddr==pages[0].paddr+length_base and\
                page.flag==pages[0].flag):
                length_base+=Page.size
                pages.append(page)
                continue
            self._add_new_section(pages,length_base)
            pages,length_base=[page],Page.size
        self._add_new_section(pages,length_base)

    def get_section_list(self):
        section_info_list=[]
        for section in self.section:
            section_info_list.append(section.get_section_info())
        return section_info_list

    def _generate_pages(self):
        pass

    def _generate_sections(self,f):
        for section in self.section:
            f.writelines(section.generate_asm())

    def file_generate(self,filename):
        self._generate_pages()
        self._generate_section_list()
        with open(filename,"wt") as f:
            self._generate_sections(f)