class Page:
    size=0x1000

class Flag:
    D=1<<7
    A=1<<6
    G=1<<5
    U=1<<4
    X=1<<3
    W=1<<2
    R=1<<1
    V=1

class Asmer:
    def global_inst(name):
        return ['.global '+name+'\n']

    def word_inst(imm):
        return ['\t'+'.word '+hex(imm)+'\n']
    
    def quad_inst(imm):
        return ['\t'+'.quad '+hex(imm)+'\n']
    
    def space_inst(imm):
        return ['\t'+'.space '+hex(imm)+'\n']

    def section_inst(name,flag):
        flag_str=""
        if flag&Flag.R:
            flag_str+="a"
        if flag&Flag.W:
            flag_str+="w"
        if flag&Flag.X:
            flag_str+="x"
        return ['.section "'+name+'","'+flag_str+'",@progbits\n']
    
    def string_inst(str):
        return ['\t'+'.string "'+str+'"\n']
    
    def label_inst(name):
        return [name+':\n']
    
    def fill_inst(repeat,size,value):
        return ['\t'+'.fill '+hex(repeat)+', '+hex(size)+', '+hex(value)+'\n']

    def byte_inst(byte_list):
        return ['\t.byte '+','.join(list(map(str,byte_list)))]

def Unsigned2Signed(unsigned):
    assert(0 <= unsigned and unsigned < 2**64)
    if unsigned < 2**63:
        return unsigned
    else:
        return unsigned - 2**64

def Signed2Unsigned(signed):
    assert(-2**63 <= signed and signed < 2**63)
    if signed>0:
        return signed
    else:
        return signed + 2**64
    