#ifndef _SPECGO_TEMPLATE_H_
#define _SPECGO_TEMPLATE_H_

#define sim_exit                                \
    la a0, tohost;                              \
    nop;                                        \
1:  sd gp, 0(a0);                            \
    j 1b;

#define PASS 1
#define FAIL 3

#endif