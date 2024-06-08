.global exit_stop
.global secret_target
.global give_me_secret
exit_stop: 
    .dword CMD_POWER_OFF
give_me_secret:
    .dword CMD_GIVE_ME_SECRET
secret_target:
    .dword GUESS_TARGET