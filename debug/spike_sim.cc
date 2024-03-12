#include "cj.h"
#include <stdio.h>

int main(int argc, const char* argv[]){
    config_t cfg;
    cfg.verbose = true;
    cfg.isa = "rv64gc_zicsr_zicntr";
    cfg.boot_addr = 0x80000000;
    if(argc==1){
        cfg.elffiles = std::vector<std::string> {
            "../../../build/fuzz_code/Testbench"
        };
    }else{
        cfg.elffiles = std::vector<std::string> {
            argv[1]
        };
    }
    cfg.mem_layout = std::vector<mem_cfg_t> {
        mem_cfg_t(0x80000000UL, 0x80000000UL),
    };
    cfg.logfile=fopen("log","wt");
    cosim_cj_t* simulator = new cosim_cj_t(cfg);
    for(int i=0;i<8000;i++){
        simulator->cosim_commit_stage(0,0,0,false);
        // puts(">\n");
        // getchar();
    }
}