trap_num_mode: 
    .dword CMD_SWITCH_STATE|STATE_DUMP_NUM
trap_char_mode: 
    .dword CMD_SWITCH_STATE|STATE_DUMP_CHAR
trap_ptr_mode: 
    .dword CMD_SWITCH_STATE|STATE_DUMP_ADDR
trap_stop: 
    .dword CMD_POWER_OFF
trap_secret_target: 
    .dword GUESS_TARGET
trap_leak_target: 
    .dword LEAK_TARGET