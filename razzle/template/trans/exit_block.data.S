.global num_mode
.global ptr_mode
.global char_mode
.global exit_stop
.global secret_target
num_mode: 
    .dword CMD_SWITCH_STATE|STATE_DUMP_NUM
ptr_mode: 
    .dword CMD_SWITCH_STATE|STATE_DUMP_ADDR
char_mode: 
    .dword CMD_SWITCH_STATE|STATE_DUMP_CHAR
exit_stop: 
    .dword CMD_POWER_OFF
secret_target:
    .dword GUESS_TARGET