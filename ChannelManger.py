from SectionManager import *
from Utils import *

class ChannelSection(Section):
    def __init__(self,name,length,image_value
    ):
        super().__init__(name,Flag.U|Flag.W|Flag.R)
        self.length=length
        self.global_label=['trapoline','array']
        self.image_value=image_value
    
    def _generate_body(self,is_variant):
        write_line=[]
        write_line.extend(Asmer.label_inst('array'))
        write_line.extend(Asmer.label_inst('trapoline'))
        write_line.extend(Asmer.fill_inst(self.length,1,self.image_value))
        return write_line

class ChannelManager(SectionManager):
    def __init__(self,config):
        super().__init__(config)
        self.image_value=int(config["image_value"],base=16)
    
    def _generate_sections(self):
        self.section['channel']=ChannelSection('channel',self.memory_bound[0][1]-self.memory_bound[0][0],self.image_value)

    def _distribute_address(self):
        self.section['channel'].get_bound(self.virtual_memory_bound[0][0],self.memory_bound[0][0],None)
        
if __name__ == "__main__":
    import hjson
    file=open("mem_init.hjson","rt")
    config=hjson.load(file)
    manager=ChannelManager(config['channel'])
    manager.file_generate('.','channel.S')
    print(manager.get_section_list())
        
            
