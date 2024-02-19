import os
import logging
import argparse
from snapshot import *

if __name__ == "__main__":
    parse = argparse.ArgumentParser(description="RVSnap is a RISC-V processor snapshot generator with a user-friendly interface that allows editing in JSON format.")
    parse.add_argument("-d", "--debug", dest="debug", action="store_true", help="enable debug mode")
    parse.add_argument("--input", dest="input", required=True, help="input json")
    parse.add_argument("--output", dest="output", default="build", help="output directory")
    parse.add_argument("--format", dest="format", default="hex,64", help="snapshot format")
    parse.add_argument("--image", dest="image", default="default.hex", help="output image name")
    parse.add_argument("--asm", dest="asm", default="init.S", help="loader asm name")
    parse.add_argument("--pmp", dest="pmp", default="0", help="number of pmp regions")
    args = parse.parse_args()

    if not os.path.exists(args.output):
        os.makedirs(args.output)

    output_format = args.format.split(",")[0]
    output_width = None
    if "hex" == output_format:
        output_width = int(args.format.split(",")[1])

    if args.debug is not None:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    design = RISCVSnapshot("rv64gc", int(args.pmp), SUPPORTED_CSR)
    design.load_snapshot(args.input)
    image_name=f"{args.output}/{args.image}"
    design.save(image_name, output_format=output_format, output_width=output_width)

    if output_format == "hex":
        design.gen_loader(f"{args.output}/{args.asm}", with_rom=0x20000)
    elif output_format == "asm":
        design.gen_loader(f"{args.output}/{args.asm}", with_asm=image_name)
    else:
        design.gen_loader(f"{args.output}/{args.asm}", with_bin=image_name)
    
    os.system(f"cp ./src/loader/rvsnap.h {args.output}/")
