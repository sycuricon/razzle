from TransBodyBlock import *
from TransFrameBlock import *
from PageTableManager import *
from SpecGoVictimBlock import *
from InitManager import *
import os

if "RAZZLE_ROOT" not in os.environ:
    os.environ["RAZZLE_ROOT"] = os.path.join(os.path.dirname(os.path.realpath(__file__)))

def CodeGenerate(config, seed, extension, output_path):

    if not os.path.exists(output_path):
        os.mkdir(output_path)

    init_manager = InitManager(config['init'], output_path, seed['mode'])
    init_manager.file_generate(output_path, 'init.S')
    
    page_table_hjson = './config/pgtlb.hjson'
    page_manager = PageTableManager(config['page_table'])
    page_manager.load_config(page_table_hjson)
    page_manager.file_generate(output_path, 'page_table.S')

    channel_block = ChannelBlock(extension, output_path)
    channel_block.gen_instr()
    channel_block.gen_file('channel.S')

    random_block = ArbitraryBlock(extension, output_path, seed['random_num'],\
        seed['random_weight'], 'arbtrary_block_0')
    random_block.gen_instr()
    random_block.gen_file('random_0.S')
    random_block = ArbitraryBlock(extension, output_path, seed['random_num'],\
        seed['random_weight'], 'arbtrary_block_1')
    random_block.gen_instr()
    random_block.gen_file('random_1.S')

    random_data_block = RandomDataBlock(extension, output_path)
    random_data_block.gen_instr()
    random_data_block.gen_file('random_data.S')

    delay_block = DelayBlock(extension, output_path, seed['delay_len'],\
        seed['delay_float_rate'], seed['delay_mem'])
    delay_block.gen_instr()
    delay_block.gen_file('delay.S')

    nop_block = NopBlock(extension, output_path, 32)
    nop_block.gen_instr()
    nop_block.gen_file('nop.S')

    root_info_path = './config/root_param.hjson'
    trigger_block = SpecGoTriggerBlock(root_info_path, delay_block.result_reg, extension, output_path)
    trigger_block.gen_instr()
    trigger_block.gen_file('trigger.S')

    load_init_block = SpecGoLoadInitBlock(0, extension, output_path, [delay_block, trigger_block], delay_block, trigger_block, random_data_block, seed['mode'])
    load_init_block.gen_instr()
    load_init_block.gen_file('load_init.S')

    baker = BuildManager(
        {"RAZZLE_ROOT": os.environ["RAZZLE_ROOT"]}, output_path, output_path, file_name=f"compile.sh"
    )
    gen_elf = ShellCommand(
        "riscv64-unknown-elf-gcc",
        [
            "-march=rv64gc",
            "-mabi=lp64",
            "-mcmodel=medany",
            "-nostdlib",
            "-nostartfiles",
            "-I$OUTPUT_PATH",
            "-I$RAZZLE_ROOT/template",
            "-I$RAZZLE_ROOT/template/specgo_trans",
            "-I$RAZZLE_ROOT/template/loader",
            "-T$RAZZLE_ROOT/template/specgo_trans/link.ld",
            "$RAZZLE_ROOT/template/specgo_trans/*.S",
            f"{output_path}/*.S",
            "-o",
            f"{output_path}/victim"
        ],
    )
    baker.add_cmd(gen_elf.gen_cmd())

    dump_asm = ShellCommand(
        "riscv64-unknown-elf-objdump",
        ["-d", f"{output_path}/victim", ">", f"{output_path}/victim.asm"],
    )
    baker.add_cmd(dump_asm.gen_cmd())

    baker.run()
    

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
        'init': {
            'bound': [
                '0x80000000',
                '0x80001000'
            ],
            'virtual_bound': [
                '0x0000000080000000',
                '0x0000000080001000'
            ],
            'pmp': 8,
            'init_input': 'config/snapshot/dummy_state.hjson',
            'csr_map': 'config/csr_map.hjson',
            'csr_solve': 'config/csr_solve.hjson',
        },
        'page_table': {
            'bound': [
                '0x8000d000',
                '0x8001d000'
            ],
            'virtual_bound': [
                '0x8000b000',
                '0x8001b000'
            ],
            'pg_level': 3,
            'xLen': 64
        }
    }
    seed = {}
    seed['delay_len'] = 8
    seed['delay_float_rate'] = 0.6
    seed['delay_mem'] = True
    seed['random_num'] = 8
    seed['random_weight'] = [1, 2, 2, 1]
    seed['mode'] = 'Uv'
    CodeGenerate(config, seed, extension, '/home/specgo/specgo/InstGenerator/build')
