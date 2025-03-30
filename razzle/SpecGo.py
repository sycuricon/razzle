from TransBodyBlock import *
from TransFrameBlock import *
from PageTableManager import *
import os

if "RAZZLE_ROOT" not in os.environ:
    os.environ["RAZZLE_ROOT"] = os.path.join(os.path.dirname(os.path.realpath(__file__)))

def CodeGenerate(config, extension, output_path):

    if not os.path.exists(output_path):
        os.mkdir(output_path)

    reg_init_hjson = './config/reg_init.hjson'
    csr_map_hjson = './config/csr_map.hjson'
    csr_solve_hjson = './config/csr_solve.hjson'
    os.system(f'python ./razzle/snapshot/main.py --input {reg_init_hjson} --map {csr_map_hjson} --state {csr_solve_hjson} --output {output_path} --format asm --pmp 8')
    
    page_table_hjson = './config/pgtlb.hjson'
    page_manager = PageTableManager(config['page_table'])
    page_manager.load_config(page_table_hjson)
    page_manager.file_generate('build', 'page_table.S')

    delay_block = DelayBlock(extension, output_path, config['delay_len'],\
        config['delay_float_rate'], config['delay_mem'])
    delay_block.gen_instr()
    delay_block.gen_file('delay.S')

    random_block = ArbitraryBlock(extension, output_path, config['random_num'],\
        config['random_weight'])
    random_block.gen_instr()
    random_block.gen_file('random.S')

    random_data_block = RandomDataBlock(extension, output_path)
    random_data_block.gen_instr()
    random_data_block.gen_file('random_data.S')

    include_path = os.path.join(output_path, 'include')
    if not os.path.exists(include_path):
        os.mkdir(include_path)
    os.system(f'cp razzle/template/fuzzing.h {include_path}/')
    os.system(f'cp razzle/template/parafuzz.h {include_path}/')
    

if __name__ == "__main__":

    extension = [
        "RV_I",
        "RV64_I",
        "RV_ZICSR",
        "RV_F",
        "RV64_F",
        "RV_D",
        "RV64_D",
        "RV_A",
        "RV64_A",
        "RV_M",
        "RV64_M",
        "RV_C",
        "RV64_C",
        "RV_C_D",
    ]

    config = {
        'page_table': {
            'bound': [
                '0x8000b000',
                '0x8001b000'
            ],
            'virtual_bound': [
                '0x8000b000',
                '0x8001b000'
            ],
            'pg_level': 3,
            'xLen': 64
        }
    }
    config['delay_len'] = 8
    config['delay_float_rate'] = 0.6
    config['delay_mem'] = True
    config['random_num'] = 8
    config['random_weight'] = [1, 2, 2, 1]
    CodeGenerate(config, extension, 'build')
