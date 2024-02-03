import os
import logging
import argparse
from snapshot import *

if __name__ == "__main__":
    parse = argparse.ArgumentParser(description="RVSnap is a RISC-V processor snapshot generator with a user-friendly interface that allows editing in JSON format.")
    parse.add_argument("-d", "--debug", dest="debug", action="store_true", help="enable debug mode")
    parse.add_argument("-i", "--input", dest="input", required=True, help="input json")
    parse.add_argument("-O", "--output", dest="output", default="build", help="output directory")
    parse.add_argument("-f", "--format", dest="format", default="hex", help="snapshot format")
    parse.add_argument("-I", "--image", dest="image", default="default.hex", help="output image name")
    parse.add_argument("-a", "--asm", dest="asm", default="init.S", help="loader asm")
    args = parse.parse_args()

    if not os.path.exists(args.output):
        os.makedirs(args.output)

    if args.debug is not None:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    design = RISCVSnapshot("rv64gc", 8, SUPPORTED_CSR)
    design.load_snapshot(args.input)
    design.save(f"{args.output}/{args.image}", format="hex", output_width=64)

    design.gen_loader(f"{args.output}/{args.asm}", with_rom=0x20000)
