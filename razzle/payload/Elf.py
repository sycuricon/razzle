import argparse

import Config
from Program import *
from Utils import getbit, getbits, cli_wrapper


# TODO: add seed as the argument
def round(id):
    TESTCASE = os.path.join(Config.OUTPUT_TARGET, 'fuzz_' + str(id))

    # TODO: integrate history into cli_wrapper
    history = []

    # TODO: following code has been broken, move seed generation to the outside caller
    # print(Config.INPUT_SEED)
    try:
        seed = BitArray(uint=int(Config.INPUT_SEED[0], 16), length=128)
    except:
        if not Config.RUN_ON_SPIKE:
            pass
        seed = BitArray(uint=random.getrandbits(128), length=128)
        imm = BitArray(uint=(0b1000 << 60), length=128)
        seed = seed | imm

    XLEN = 64 if getbit(seed, 63) else 32
    random.seed((getbits(seed, 111, 100) << 54) | getbits(seed, 53, 0))

    if getbits(seed, 62, 61) == 0:
        MODE = 'U'
    else:
        MODE = 'S' if getbits(seed, 62, 61) == 0b01 else 'M'

    if MODE == "U":
        ENV = "v" if getbit(seed, 60) else 'p'
    else:
        ENV = "p"

    gen_program(seed, f"{TESTCASE}.S")

    gen_elf = cli_wrapper("riscv64-unknown-elf-gcc",
                          "-g3 -static -mcmodel=medany -fvisibility=hidden -nostdlib -nostartfiles")
    gen_asm = cli_wrapper("riscv64-unknown-elf-objdump",
                          "-S --disassemble-all --disassemble-zeroes --section=.text --section=.text.startup --section=.text.init --section=.data")
    gen_sym = cli_wrapper("riscv64-unknown-elf-readelf", "-s")
    gen_bin = cli_wrapper("riscv64-unknown-elf-objcopy",
                          ["--gap-fill 0", "--set-section-flags .bss=alloc,load,contents",
                           "--set-section-flags .sbss=alloc,load,contents",
                           "--set-section-flags .tbss=alloc,load,contents", f"-O binary {TESTCASE} {TESTCASE}.bin"])
    gen_hex = cli_wrapper(f"od -v -An -tx8 {TESTCASE}.bin > {TESTCASE}.hex")

    gen_elf.append(["-march=rv{}g{}{}_zicsr_zifencei -mabi={}lp{}".format(
                        XLEN, 'c' if getbit(seed, 55) else '',
                        '_zbkb_zbkc_zbkx_zkne_zknd_zknh' if getbit(seed, 54) else '',
                        'i' if XLEN == 32 else '', XLEN),
                    f"-Ienv/{ENV} -Tenv/link.ld"])

    if not Config.RUN_ON_SPIKE:
        gen_elf.append("-DENABLE_MULTI_ROUND")
        if Config.ENABLE_MORFUZZ:
            gen_elf.append("-DENABLE_MAGIC_MASKER -DENABLE_MAGIC_DEVICE")
    if Config.ENABLE_HYPERVISOR and getbit(seed, 80) and ENV == "p" and MODE != 'M':
        gen_elf.append("-DENABLE_HYPERVISOR")

    if ENV == "v":
        entropy = random.getrandbits(32)
        gen_elf.append("-DENTROPY=" + hex(entropy))
        gen_elf.exec(
            f"-c env/v/vm.c -o {Config.OUTPUT_TARGET}/vm-env.o", cmd_history=history)
        gen_elf.exec(
            f"-c env/v/string.c -o {Config.OUTPUT_TARGET}/vm-lib.o", cmd_history=history)
        gen_elf.exec(
            f"-c env/v/entry.S -o {Config.OUTPUT_TARGET}/vm-asm.o", cmd_history=history)
        gen_elf.append(f"{Config.OUTPUT_TARGET}/vm*.o")

    gen_elf.append([TESTCASE + ".S", "-o", TESTCASE])

    if (gen_elf.exec(cmd_history=history) != 0):
        exit(1)

    gen_asm.exec(f"{TESTCASE} > {TESTCASE}.dump", cmd_history=history)
    gen_sym.exec(
        f"{TESTCASE} | (sed -u 3q; sort -k2) > {TESTCASE}.symbol", cmd_history=history)

    gen_bin.exec(cmd_history=history)
    gen_hex.exec(cmd_history=history)

    with open(f"{TESTCASE}.sh", 'w+') as file:
        for cmd in history:
            file.write(cmd + '\n')


def main():
    # TODO: add package name and description
    parser = argparse.ArgumentParser(
        description="",
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("-d", "--debug", action="store_true",
                        default=False, help="print debug information")
    parser.add_argument("-i", "--input", nargs="+", type=str,
                        default=[], help="input seeds in hex")
    parser.add_argument("-o", "--output", type=str,
                        default=os.path.join(os.getcwd(), "build"), help="output directory")
    parser.add_argument("-s", "--spike", action="store_true",
                        default=False, help="spike execution environment")
    parser.add_argument("-b", "--batch", action="store",
                        type=int, default=1, help="batch size for each seed")
    parser.add_argument("-m", "--morfuzz", action="store_true",
                        default=False, help="enable instruction morphing and magic device")

    args = parser.parse_args()
    Config.INPUT_SEED = args.input
    Config.RUN_ON_SPIKE = args.spike
    Config.OUTPUT_TARGET = os.path.abspath(args.output)
    Config.ENABLE_MORFUZZ = args.morfuzz

    if args.debug:
        Config.DETAIL = True
        logging.basicConfig(
            format="[%(levelname)s] %(asctime)s %(filename)s@L%(lineno)d: %(message)s",
            datefmt="%m/%d %H:%M:%S", level=logging.DEBUG)
    else:
        logging.basicConfig(
            format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S", level=logging.INFO)

    if not os.path.exists(args.output):
        logging.info(f"create target directory {Config.OUTPUT_TARGET}")
        os.mkdir(Config.OUTPUT_TARGET)

    # TODO: fetch each seed and perform batch generation
    for i in range(args.batch):
        round(i)


if __name__ == "__main__":
    main()
