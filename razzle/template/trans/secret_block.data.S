.global secret
.global secret_page_base
secret:
secret_begin:
	.fill 0x8, 0x1, 0xff
secret_end:
	.space 0x7f8
secret_page_base: