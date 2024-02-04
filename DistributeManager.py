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
    def __init__(self,hjson_filename):
        hjson_file=open(hjson_filename)
        config=hjson.load(hjson_file)
        hjson_file.close()

        self.secret=SecretManager(config["secret"])
        self.channel=ChannelManager(config["channel"])
        self.page_table=PageTableManager(config["page_table"])
        self.stack=StackManager(config["stack"])
        self.payload=PayloadManager(config["payload"])
        self.poc=PocManager(config["poc"])

        self.loader=LoaderManager()
    
    def generate_test(self,path):
        secret_name='secret.S'
        channel_name='channel.S'
        page_table_name='page_table.S'
        stack_name='stack.S'
        payload_name='payload.S'
        poc_name='poc.S'
        ld_name='link.ld'
        self.secret.file_generate(path,secret_name)
        self.channel.file_generate(path,channel_name)
        self.stack.file_generate(path,stack_name)
        self.payload.file_generate(path,payload_name)
        self.poc.file_generate(path,poc_name)

        self.section_list=[]
        self.section_list.extend(self.secret.get_section_list())
        self.section_list.extend(self.channel.get_section_list())
        self.section_list.extend(self.stack.get_section_list())
        self.section_list.extend(self.payload.get_section_list())
        self.section_list.extend(self.poc.get_section_list())

        self.page_table.register_sections(self.section_list)
        self.page_table.file_generate(path,page_table_name)
        self.section_list.extend(self.page_table.get_section_list())
        
        self.loader.append_section_list(self.section_list)
        self.loader.file_generate(path,ld_name)

if __name__ == "__main__":
    parse = argparse.ArgumentParser()
    parse.add_argument("-i", "--input",  dest="input",  required=True, help="input hjson")
    parse.add_argument("-O", "--output", dest="output", required=True, help="output of the fuzz code")
    args = parse.parse_args()
    if not os.path.exists(args.output):
        os.makedirs(args.output)
    dist=DistributeManager(args.input)
    dist.generate_test(args.output)



        