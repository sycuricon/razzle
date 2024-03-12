#include "cj.h"
#include <stdio.h>
#include "elf.h"

int main(int argc, const char* argv[]){
    config_t cfg;
    cfg.verbose = true;
    cfg.isa = "rv64gc_zicsr_zicntr";
    cfg.boot_addr = 0x80000000;
    cfg.elffiles = std::vector<std::string> {
        argv[1]
    };
    cfg.mem_layout = std::vector<mem_cfg_t> {
        mem_cfg_t(0x80000000UL, 0x80000000UL),
    };

    int text_len=0;

    FILE* input_elf=fopen(argv[1],"rb");
    Elf64_Ehdr elf_header;
    fread(&elf_header,sizeof(Elf64_Ehdr),1,input_elf);
    fseek(input_elf,elf_header.e_shoff,SEEK_SET);

    assert(sizeof(Elf64_Shdr)==elf_header.e_shentsize);
    Elf64_Shdr* shdr=(Elf64_Shdr*)malloc(sizeof(Elf64_Shdr)*elf_header.e_shnum);
    fread(shdr,sizeof(Elf64_Shdr),elf_header.e_shnum,input_elf);
    for(int i=0;i<elf_header.e_shnum;i++){
        // printf("%x\n",shdr[i].sh_flags);
        if(shdr[i].sh_type == SHT_PROGBITS && shdr[i].sh_flags&SHF_EXECINSTR){
            text_len=shdr[i].sh_size;
        }
    }
    // printf("%x\n",text_len);
    free(shdr);
    fclose(input_elf);

    cfg.logfile=fopen("log","wt");
    cosim_cj_t* simulator = new cosim_cj_t(cfg);
    processor_t *core = simulator->get_core(0);
    for(int i=0;i<text_len/4;i++){
        simulator->cosim_commit_stage(0,0,0,false);
    }

    FILE* dump_file=fopen("dump","wt");
    const char* reg_name[]={
        "ZERO", "RA", "SP", "GP", "TP", "T0", "T1", "T2", "S0", "S1", "A0", "A1",
        "A2", "A3", "A4", "A5", "A6", "A7", "S2", "S3", "S4", "S5", "S6", "S7",
        "S8", "S9", "S10", "S11", "T3", "T4", "T5", "T6"
    };
    for(int i=0;i<sizeof(reg_name)/sizeof(const char*);i++){
        fprintf(dump_file, "%s %016llx\n",reg_name[i], core->get_state()->XPR[i]);
    }

    const char* freg_name[]={
        "FT0", "FT1", "FT2", "FT3", "FT4", "FT5", "FT6", "FT7",
        "FS0", "FS1", "FA0", "FA1", "FA2", "FA3", "FA4", "FA5",
        "FA6", "FA7", "FS2", "FS3", "FS4", "FS5", "FS6", "FS7",
        "FS8", "FS9", "FS10", "FS11", "FT8", "FT9", "FT10", "FT11"
    };
    for(int i=0;i<sizeof(freg_name)/sizeof(const char*);i++){
        fprintf(dump_file, "%s %016llx\n",freg_name[i], core->get_state()->FPR[i]);
    }


}