import hjson
import argparse
import os
from ChannelManger import *
from PageTableManager import *
from LoaderManager import *
from SecretManager import *
from StackManager import *
from PocManager import *
from PayloadManager import *

class DistributeManager:
    def __init__(self,hjson_filename,output_path,virtual):
        hjson_file=open(hjson_filename)
        config=hjson.load(hjson_file)
        hjson_file.close()
        
        self.output_path=output_path

        self.secret=SecretManager(config["secret"])
        self.channel=ChannelManager(config["channel"])
        self.page_table=PageTableManager(config["page_table"])
        self.stack=StackManager(config["stack"])
        self.payload=PayloadManager(config["payload"])
        self.poc=PocManager(config["poc"])

        self.loader=LoaderManager(virtual)

        self.file_list=[]
        self.var_file_list=[]
    
    def _collect_compile_file(self,file_list):
        self.file_list.extend(file_list[0])
        self.var_file_list.extend(file_list[1])

    def _generate_compile_file(self,filename,var_name,files_list):
        with open(filename,"wt") as f:
            f.write(var_name+'_C = \\\n')
            for file in files_list:
                if file.endswith(".c"):
                    f.write('\t'+file+' \\\n')
            f.write('\n')

            f.write(var_name+'_S = \\\n')
            for file in files_list:
                if file.endswith(".S"):
                    f.write('\t'+file+' \\\n')
            f.write('\n')

    def _generate_compile_files(self):
        origin_files=os.path.join(self.output_path,'origin_list.mk')
        variant_files=os.path.join(self.output_path,'variant_list.mk')
        self._generate_compile_file(origin_files,'ORIGIN_SRC',self.file_list)
        self._generate_compile_file(variant_files,'VARIANT_SRC',self.var_file_list)
    
    def generate_test(self):
        secret_name='secret.S'
        channel_name='channel.S'
        page_table_name='page_table.S'
        stack_name='stack.S'
        payload_name='payload.S'
        poc_name='poc.S'
        ld_name='link.ld'
        self._collect_compile_file(self.secret.file_generate(self.output_path,secret_name))
        self._collect_compile_file(self.channel.file_generate(self.output_path,channel_name))
        self._collect_compile_file(self.stack.file_generate(self.output_path,stack_name))
        self._collect_compile_file(self.payload.file_generate(self.output_path,payload_name))
        self._collect_compile_file(self.poc.file_generate(self.output_path,poc_name))

        self.section_list=[]
        self.section_list.extend(self.secret.get_section_list())
        self.section_list.extend(self.channel.get_section_list())
        self.section_list.extend(self.stack.get_section_list())
        self.section_list.extend(self.payload.get_section_list())
        self.section_list.extend(self.poc.get_section_list())

        self.page_table.register_sections(self.section_list)
        self._collect_compile_file(self.page_table.file_generate(self.output_path,page_table_name))
        self.section_list.extend(self.page_table.get_section_list())
        
        self.loader.append_section_list(self.section_list)
        self.loader.file_generate(self.output_path,ld_name)

        self._generate_compile_files()

if __name__ == "__main__":
    parse = argparse.ArgumentParser()
    parse.add_argument("-I", "--input",  dest="input",  required=True, help="input hjson")
    parse.add_argument("-O", "--output", dest="output", required=True, help="output of the fuzz code")
    parse.add_argument("-V", "--virtual", dest="virtual", action="store_true", help="link in virtual address")
    
    args = parse.parse_args()
    if not os.path.exists(args.output):
        os.makedirs(args.output)
    dist=DistributeManager(args.input,args.output,args.virtual)
    dist.generate_test()



        