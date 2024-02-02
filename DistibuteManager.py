import hjson
import os
from ChannelManger import *
from PageTableManager import *
from LoaderManager import *
from SecretManager import *

class DistributeManager:
    def __init__(self,hjson_filename):
        hjson_file=open(hjson_filename)
        config=hjson.load(hjson_file)
        hjson_file.close()

        self.secret=SecretManager(config["secret"])
        self.channel=ChannelManager(config["channel"])
        self.page_table=PageTableManager(config["page_table"])
        self.loader=LoaderManager()
    
    def generate_test(self,path):
        secret_path=os.path.join(path,'secret.S')
        channel_path=os.path.join(path,'channel.S')
        page_table_path=os.path.join(path,'page_table.S')
        ld_path=os.path.join(path,'link.ld')
        self.secret.file_generate(secret_path)
        self.channel.file_generate(channel_path)

        self.section_list=[]
        self.section_list.extend(self.secret.get_section_list())
        self.section_list.extend(self.channel.get_section_list())

        self.page_table.register_sections(self.section_list)
        self.page_table.file_generate(page_table_path)
        self.section_list.extend(self.page_table.get_section_list())
        
        self.loader.append_section_list(self.section_list)
        self.loader.file_generate(ld_path)

if __name__ == "__main__":
    dist=DistributeManager('distribute.hjson')
    dist.generate_test(os.path.join(os.getcwd(),'build'))



        