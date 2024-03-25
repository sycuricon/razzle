import argparse

def hex2asm(hex_filename,asm_filename):
    hex_list=[]
    line_width=0
    with open(hex_filename,"rt") as hex_file:
        hex_list = hex_file.readlines()
        line_width=len(hex_list[0].strip())*4
    with open(asm_filename,"wt") as asm_file:
        asm_file.write(".section .data\n")
        for line in hex_list:
            if line_width == 32:
                asm_file.write("\t.word 0x"+line)
            elif line_width == 64:
                asm_file.write("\t.quadword 0x"+line)
        asm_file.write('\n')

if __name__ == "__main__":
    parse = argparse.ArgumentParser()
    parse.add_argument("-I", "--input",  dest="input",  required=True, help="input hex file")
    parse.add_argument("-O", "--output", dest="output", required=True, help="output asm file")
    args=parse.parse_args()
    hex2asm(args.input,args.output)
    
        