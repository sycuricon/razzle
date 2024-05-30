import argparse
import libconf
import os
import sys
from SectionUtils import *

def offline_compile(test_folder):
    with open(os.path.join(test_folder, 'swap_mem.cfg'), 'rt') as config_file:
        test_config = libconf.load(config_file)
    swap_list = test_config['swap_list']
    swap_list.reverse()
    for idx in swap_list:
        if idx == 0:
            continue
        os.system(os.path.join(test_folder, f'compile_{idx}.sh'))
        file_origin = os.path.join(test_folder, f'Testbench_{idx}.bin')
        with open(file_origin, "rb") as file:
            origin_byte_array = bytearray(file.read())
        symbol_table = get_symbol_file(os.path.join(test_folder, f'Testbench_{idx}.symbol'))

        if symbol_table['_text_swap_start'] > 0x80000000:
            address_base = 0x80000000
        else:
            address_base = 0x0

        file_text_swap_base = f'text_swap_{idx}.bin'
        file_text_swap = os.path.join(test_folder, file_text_swap_base)
        text_begin = symbol_table['_text_swap_start'] - address_base
        text_end   = symbol_table['_text_swap_end'] - address_base
        text_swap_byte_array = origin_byte_array[text_begin:text_end]
        with open(file_text_swap, "wb") as file:
            file.write(text_swap_byte_array)
        
        match(idx):
            case 1:
                data_name = 'data_victim'
            case 2:
                data_name = 'data_decode'
            case _:
                data_name = 'data_train'

        data_begin_label = f'_{data_name}_start'
        data_end_label = f'_{data_name}_end'

        file_data_base = f'{data_name}_{idx}.bin'
        file_data = os.path.join(test_folder, file_data_base)
        data_begin = symbol_table[data_begin_label] - address_base
        data_end   = symbol_table[data_end_label] - address_base
        data_byte_array = origin_byte_array[data_begin:data_end]
        with open(file_data, "wb") as file:
            file.write(data_byte_array)
        
        

if __name__ == "__main__":
    parse = argparse.ArgumentParser(description="offline compiler to adjust the assembler of the test program generator")
    parse.add_argument("--input", "-I", dest="input", required=True, help="workspace need to adjust")
    args = parse.parse_args()

    offline_compile(args.input)