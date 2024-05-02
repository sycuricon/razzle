.global secret
.global secret_page_base
secret:
secret_begin:
	.byte 100,101,97,100,98,101,101,102
secret_end:
	.space 0x7f8
secret_page_base: