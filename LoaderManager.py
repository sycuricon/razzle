def section_sort(item):
    return item[2]

class LoaderManager:
    def __init__(self):
        self.section=[]

    def append_section_list(self,section_list):
        self.section.extend(section_list)

    def generate_ld(self,ld_name):
        with open(ld_name,"wt") as f:
            section_order=sorted(self.section,key=section_sort)
            f.write('OUTPUT_ARCH( "riscv" )\n')
            f.write('ENTRY(_start)\n')
            f.write('SECTIONS\n')
            f.write('{\n')
            for name,vaddr,paddr in section_order:
                f.write('\t'+'. = '+hex(vaddr)+';\n')
                f.write('\t'+name+' : AT ('+hex(paddr)+') { *('+name+') }\n')
            f.write('}\n')

if __name__ == "__main__":
    loader=LoaderManager()
    loader.append_section_list([(".bss",0x10000,0x80001000),(".rodata",0x20000,0x80020000)])
    loader.append_section_list([(".text",0x0,0x80000000),(".data",0x2000,0x80002000)])
    loader.generate_ld("link.ld")
            
