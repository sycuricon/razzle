.section ".text.jmp_train_2","ax",@progbits
.option rvc
auipc t0, 0x200
jr t0

.section ".text.jmp_victim","ax",@progbits
.option rvc
auipc t0, 0x200
jr t0