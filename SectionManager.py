from Utils import *
import os

class Section:
    def __init__(self,name,flag):
        self.name=name
        self.flag=flag
        self.length=None
        self.vaddr=None
        self.paddr=None
        self.link=None

    def get_length(self):
        return self.length
    
    def get_bound(self,vaddr,paddr,length):
        assert(self.vaddr is None or vaddr is None)
        assert(self.paddr is None or paddr is None)
        assert(self.length is None or length is None)

        if self.vaddr is None:
            self.vaddr=vaddr
        if self.paddr is None:
            self.paddr=paddr
        if self.length is None:
            self.length=length
    
    def _generate_global(self):
        write_lines=[]
        for label in self.global_label:
            write_lines.extend(Asmer.global_inst(label))
        return write_lines
    
    def _generate_header(self):
        return Asmer.section_inst(self.name,self.flag)
    
    def _generate_body(self,is_variant):
        return []

    def generate_asm(self,is_variant):
        write_lines=[]
        write_lines.extend(self._generate_global())
        write_lines.extend(self._generate_header())
        write_lines.extend(self._generate_body(is_variant))
        return write_lines

    def get_section_info(self):
        info={'name':self.name,'vaddr':self.vaddr,'paddr':self.paddr,'length':self.length,'flag':self.flag,'link':self.link}
        return info

class SectionManager:
    def __init__(self,config):
        self.memory_bound=[]
        self.virtual_memory_bound=[]
        for begin,end in zip(config["bound"][0::2],config["bound"][1::2]):
            begin=int(begin,base=16)
            end=int(end,base=16)
            self.memory_bound.append((begin,end))
        for begin,end in zip(config["virtual_bound"][0::2],config["virtual_bound"][1::2]):
            begin=int(begin,base=16)
            end=int(end,base=16)
            self.virtual_memory_bound.append((begin,end))
        self.section={}

    def get_section_list(self):
        section_info_list=[]
        for section in self.section.values():
            section_info_list.append(section.get_section_info())
        return section_info_list

    def _write_sections(self,f,is_variant):
        for section in self.section.values():
            f.writelines(section.generate_asm(is_variant))
        
    def _generate_sections(self):
        pass

    def _distribute_address(self):
        pass

    def _write_file(self,path,name):
        filename=os.path.join(path,name)
        with open(filename,"wt") as f:
            self._write_sections(f,False)
        return [[filename],[filename]]

    def file_generate(self,path,name):
        self._generate_sections()
        self._distribute_address()
        return self._write_file(path,name)
        