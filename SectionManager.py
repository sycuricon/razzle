from Assembler import Asmer

class Page:
    size=0x1000

    def __init__(self):
        self.global_label=[]

    def generate_asm(self):
        return []

    def global_label(self):
        return self.global_label
    
    def add_global_label(self,label):
        self.global_label.append(label)

class Section:
    def __init__(self,name,vaddr,paddr,length,flag,section_label=None,pages=[]):
        self.name=name
        self.vaddr=vaddr
        self.paddr=paddr
        self.length=length
        self.flag=flag
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

class Flag:
    def __init__(self):
        self.U=1<<4
        self.X=1<<3
        self.W=1<<2
        self.R=1<<1

class SectionManager:
    def __init__(self,config):
        self.flag=Flag()
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
        self.page_content={}
    
    def _add_page_content(self,vaddr,page):
        self.page_content[vaddr]=page
    
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
        self.use_page.append((vaddr,paddr,flag))
        return vaddr,paddr
    
    def _init_section_type(self):
        self.name_dict={}
        self.name_dict[self.flag.U|self.flag.R]=[".rodata",Section,0]
        self.name_dict[self.flag.U|self.flag.R|self.flag.W]=[".data",Section,0]
        self.name_dict[self.flag.U|self.flag.R|self.flag.X]=[".text",Section,0]

    def _get_section_type(self,flag):
        name,section,num=self.name_dict[flag]
        self.name_dict[flag][2]+=1
        return name if num==0 else name+str(num),section
    
    def _add_new_section(self,vaddr_base,paddr_base,length_base,flag_base):
        name,section=self._get_section_type(flag_base)
        pages=[]
        for vaddr in range(vaddr_base,vaddr_base+length_base,Page.size):
            pages.append(self.page_content[vaddr])
        self.section.append(section(name,vaddr_base,paddr_base,length_base,flag_base,name[1:],pages))
    
    def _generate_section_list(self):
        def _sort_key(item):
            return item[0]
        self.use_page=sorted(self.use_page,key=_sort_key)
        (vaddr_base,paddr_base,flag_base)=self.use_page[0]
        length_base=Page.size
        for vaddr,paddr,flag in self.use_page[1:]:
            if(vaddr==vaddr_base+length_base,paddr==paddr_base+length_base,flag==flag_base):
                length_base+=Page.size
                continue
            self._add_new_section(vaddr_base,paddr_base,length_base,flag_base)
            vaddr_base,paddr_base,flag_base,length_base=vaddr,paddr,flag,Page.size
        self._add_new_section(vaddr_base,paddr_base,length_base,flag_base)

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