func_begin_train:
    la t0, store_ra
    sd ra, 0(t0)
    mv t0, zero
    j predict
func_begin_victim:
    la t0, store_ra
    sd ra, 0(t0)