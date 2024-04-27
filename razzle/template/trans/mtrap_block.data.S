.align 3
mtrap_num_mode: 
    .dword CMD_SWITCH_STATE|STATE_DUMP_NUM
mtrap_char_mode: 
    .dword CMD_SWITCH_STATE|STATE_DUMP_CHAR
mtrap_ptr_mode: 
    .dword CMD_SWITCH_STATE|STATE_DUMP_ADDR
mtrap_stop: 
    .dword CMD_POWER_OFF
mtrap_secret_target: 
    .dword GUESS_TARGET
mtrap_leak_target: 
    .dword LEAK_TARGET
mtrap_swap_mem_op:
    .dword CMD_SWAP_MEM

mtrap_stack_top:
    .space 0x100
mtrap_stack_bottom:
