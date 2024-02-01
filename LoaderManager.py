def section_sort(item):
    return item[1]

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
            for name,begin in section_order:
                f.write('\t'+'. = '+hex(begin)+';\n')
                f.write('\t'+name+' = { *('+name+') }\n')
            f.write('}\n')

if __name__ == "__main__":
    loader=LoaderManager()
    loader.append_section_list([(".text",0x10000),(".data",0x20000)])
    loader.append_section_list([(".tmp",0x0),(".here",0x20)])
    loader.generate_ld("link.ld")
            
