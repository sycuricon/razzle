.align 3
strap_num_mode: 
    .dword CMD_SWITCH_STATE|STATE_DUMP_NUM
strap_char_mode: 
    .dword CMD_SWITCH_STATE|STATE_DUMP_CHAR
strap_ptr_mode: 
    .dword CMD_SWITCH_STATE|STATE_DUMP_ADDR
strap_stop: 
    .dword CMD_POWER_OFF
strap_secret_target: 
    .dword GUESS_TARGET
strap_leak_target: 
    .dword LEAK_TARGET