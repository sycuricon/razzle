.extern _train2_start
.extern _victim_start

.section ".text.jmp_train_2","ax",@progbits
.option rvc
la t0, _train2_start
jr t0

.section ".text.jmp_victim","ax",@progbits
.option rvc
la t0, _victim_start
jr t0