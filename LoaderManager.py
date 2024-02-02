

class LoaderManager:
    def __init__(self):
        self.section=[]

    def append_section_list(self,section_list):
        self.section.extend(section_list)

    def file_generate(self,ld_name):
        def section_sort(item):
            return item[2]
        with open(ld_name,"wt") as f:
            section_order=sorted(self.section,key=section_sort)
            f.write('OUTPUT_ARCH( "riscv" )\n')
            f.write('ENTRY(_start)\n')
            f.write('SECTIONS\n')
            f.write('{\n')
            for name,vaddr,paddr,length,flag in section_order:
                f.write('\t'+'. = '+hex(vaddr)+';\n')
                f.write('\t'+name+' : AT ('+hex(paddr)+') { *('+name+') }\n')
            f.write('}\n')

if __name__ == "__main__":
    loader=LoaderManager()
    loader.append_section_list([(".bss",0x10000,0x80001000,0x3000,2),(".rodata",0x20000,0x80020000,0x2000,14)])
    loader.append_section_list([(".text",0x0,0x80000000,0x1000,6),(".data",0x2000,0x80002000,0x1000,4)])
    loader.file_generate("link.ld")
            
