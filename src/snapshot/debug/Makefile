CC	=	$(RISCV)/bin/riscv64-unknown-elf-gcc

ASM = 	$(patsubst %.hex,%.S,$(INPUT))	

all:$(OUTPUT)

$(OUTPUT):$(ASM) link.ld
	$(CC) -Tlink.ld $< -nostdlib -static -Wl,--no-gc-sections -o $@

$(ASM):$(INPUT)
	python hex2asm.py -I $< -O $@