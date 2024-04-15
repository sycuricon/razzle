access_time:
  la a0, array
  la a1, secret_target
  ld a1, 0(a1)
  slli t1, a1, 6
  add t0, a0, t1
  csrr t1, cycle
  lb t0, 0(t0)
  csrr t0, cycle
  sub a0, t0, t1
  