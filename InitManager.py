from FileManager import *
from Utils import *

class InitManager(FileManager):
    def __init__(self,config):
        super().__init__(config)
    
    def _generate_sections(self):
        init_link=[
            # '\t\t*(.text.init)\n'
            '\t\t*(.text.init)\n'
            '\t\t*(.data.init)\n'
        ]
        self.section['init']=FileSection('.init',Flag.U|Flag.X|Flag.R,init_link)

    def _distribute_address(self):
        self.section['init'].get_bound(self.memory_bound[0][0],self.memory_bound[0][0],0x1000)

    
        
        


        
            
