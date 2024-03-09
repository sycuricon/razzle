  slli t1, a1, 6
  add t0, a0, t1
  add t0, t0, a2
  csrr t1, cycle
  lb t0, 0(t0)
  csrr t0, cycle
  sub a0, t0, t1
  ret