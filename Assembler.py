class Asmer:
    def global_inst(name):
        return ['.global '+name+'\n']

    def word_inst(imm):
        return ['\t'+'.word '+hex(imm)+'\n']
    
    def quad_inst(imm):
        return ['\t'+'.quad '+hex(imm)+'\n']
    
    def space_inst(imm):
        return ['\t'+'.space '+hex(imm)+'\n']

    def section_inst(name):
        return ['.section '+name+'\n']
    
    def string_inst(str):
        return ['\t'+'.string "'+str+'"\n']
    
    def label_inst(name):
        return [name+':\n']
    
    def fill_inst(repeat,size,value):
        return ['\t'+'.fill '+hex(repeat)+', '+hex(size)+', '+hex(value)+'\n']
    