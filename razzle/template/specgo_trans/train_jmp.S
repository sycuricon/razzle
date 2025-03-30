.section ".text.jmp_train_1","ax",@progbits
.option rvc
auipc t0, 0x200000
jr t0

.section ".text.jmp_victim","ax",@progbits
.option rvc
auipc t0, 0x200000
jr t0