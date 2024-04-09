  slli t1, a1, 6
  add t0, a0, t1
  add t0, t0, a2
  INFO_LEAK_START
  csrr t1, cycle
  lb t0, 0(t0)
  csrr t0, cycle
  INFO_LEAK_END
  sub a0, t0, t1
  ret