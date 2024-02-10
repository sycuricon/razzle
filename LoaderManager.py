import os

class LoaderManager:
    def __init__(self,virtual):
        self.section=[]
        self.virtual=virtual

    def append_section_list(self,section_list):
        self.section.extend(section_list)

    def file_generate(self,path,name):
        ld_name=os.path.join(path,name)
        def section_sort(item):
            return item[0][1] if self.virtual else item[0][2]
        with open(ld_name,"wt") as f:
            section_order=sorted(self.section,key=section_sort)
            print(section_order)
            f.write('OUTPUT_ARCH( "riscv" )\n')
            f.write('ENTRY(_start)\n')
            f.write('SECTIONS\n')
            f.write('{\n')
            for (name,vaddr,paddr,length,flag),append in section_order:
                link_addr=hex(vaddr if self.virtual else paddr)
                load_addr=hex(paddr)
                f.write('\t'+'. = '+link_addr+';\n')
                if self.virtual:
                    f.write('\t'+name+' : AT ('+load_addr+') {\n')
                else:
                    f.write('\t'+name+' : {\n')
                f.write('\t\t'+name.replace('.','_')+'_start = .;\n')
                if append is None:
                    f.write('\t\t*('+name+'*)\n')
                else:
                    f.writelines(append) 
                f.write('\t\t'+name.replace('.','_')+'_end = .;\n')
                f.write('\t}\n')
            f.write('\t_end = .;\n')
            f.write('}\n')

if __name__ == "__main__":
    loader=LoaderManager()
    loader.append_section_list([(".bss",0x10000,0x80001000,0x3000,2),(".rodata",0x20000,0x80020000,0x2000,14)])
    loader.append_section_list([(".text",0x0,0x80000000,0x1000,6),(".data",0x2000,0x80002000,0x1000,4)])
    loader.file_generate("link.ld")
            
