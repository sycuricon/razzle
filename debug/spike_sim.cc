#include "cj.h"
#include <stdio.h>

int main(){
    config_t cfg;
    cfg.verbose = true;
    cfg.isa = "rv64gc";
    cfg.boot_addr = 0x10000;
    cfg.elffiles = std::vector<std::string> {
        "/home/zyy/starship-parafuzz/build/firmware/rvsnap/init.elf",
        "/home/zyy/starship-parafuzz/build/fuzz_code/reg_init.elf",
        "/home/zyy/starship-parafuzz/build/fuzz_code/Testbench"
    };
    cfg.mem_layout = std::vector<mem_cfg_t> {
        mem_cfg_t(0x80000000UL, 0x80000000UL),
    };
    cfg.logfile=fopen("log","wt");
    cosim_cj_t* simulator = new cosim_cj_t(cfg);
    for(int i=0;i<1000;i++){
        simulator->cosim_commit_stage(0,0,0,false);
        // puts(">\n");
        // getchar();
    }
}