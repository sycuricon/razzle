.global exit_stop
.global secret_target
exit_stop: 
    .dword CMD_POWER_OFF
secret_target:
    .dword GUESS_TARGET