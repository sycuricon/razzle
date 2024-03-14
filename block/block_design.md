# fuzz code 的 block 设计

## block 流程图
```
    +---------------+                      +---------------+ 
    |               |       +------------->|               |    
    |     init      |       |              |     delay     | 
    |               |       |              |               | 
    +---------------+       |              +---------------+     
            ||              |                      ||                                
            ||              |                      ||                                
            \/              |                      \/                                
    +---------------+       |              +---------------+                         
    |               |-------+              |               |                         
    |     train     |                      |    predict    |-------+                 
    |               |<----------+          |               |       |                 
    +---------------+           |          +---------------+       |                 
            ||                  |                  ||              |                 
            ||                  |                  ||              |                 
            \/                  |                  \/              |                 
    +---------------+           |          +---------------+       |                 
    |               |           |          |               |       |                 
    |     poc       |           |          |     victim    |       |                 
    |               |           |          |               |       |                 
    +---------------+           |          +---------------+       |                    
            ||                  |                  ||              |                 
            ||                  |                  ||              |                 
            \/                  |                  \/              |                 
    +---------------+           |          +---------------+       |                 
    |               |           |          |               |       |                 
    |     exit      |           +----------|     return    |<------+                
    |               |                      |               |                 
    +---------------+                      +---------------+                         
```

## init
* 作用：用来做寄存器的初始化，设置页表、handle、运行模式，进入 _init 开始正式 fuzz
* 实现：rvsnap + InstGenerator/InitManager.S + reg_init.hjson

## delay
* 作用：对 predict 块的数据流进行延迟，迫使 predict 块进行猜测执行
* 实现：对某些寄存器做随机立即数初始化，随机生成一些指令做数据流计算
* 约束：有大量的 RAW 数据依赖，且尽量复用寄存器

## predict
* 作用：被 delay 块延迟执行，被迫进入猜测执行，产生瞬态窗口
* 实现：branch、call、return、except、store+load 中的一种
* 约束：涉及的 RS 是 delay 得到的 RD

## victim
* 作用：执行瞬态窗口的时候执行的代码，用来泄露 secret
* 实现：任意代码随机执行？
* 约束：第一条指令必须 trapline[param2] 访问指定 secret 地址的内存

## return
* 作用：跳转预测的 predict 触发瞬态窗口时，回滚之后会进入的块；victim 直接退出到的块
* 实现：恢复 train 返回的 ra 地址，return 返回 train 块
* 其他：可以考虑在 delay 前加一些操作，比如保存 ra 的值到堆栈，然后直接回复 ra 的值

## train
* 作用：训练 predict 使得猜测执行的时候跳入瞬态窗口执行 vicitim
* 实现：简单的 for 循环，提供一个 {param1,param2} 数组；param1 影响 predict 的控制流，param2 影响 victim 的数据流。前 N 组 {param1,param2} 是跳入 victim，不访问 secret 的；最后一组 {param1,param2} 是跳入 return，但是进入 victim 的时候是访问 secret 的
* param1 的计算：predict 的指令事先生成，然后约束 param1 分别满足进入 victim 和 return
* param2 的计算：victim 的指令事先生成，然后约束 param2 分别访问 secret 和不访问 secret

## poc
* 作用：进一步泄露 taint
* 实现：PocManager + access_time()

## exit
* 作用：停机
* 实现：exit() 写特殊寄存器

## 寄存器分工
* sp：堆栈寄存器，不可以随机使用
* gp：数据段寄存器，用于访问随即指令和 train 的 param 需要的立即数
* tp：堆栈寄存器，不可以随机使用
* a0：param1 的传参，不可以随机使用
* a1：param2 的传参，不可以随机使用
* ra：返回地址，除了 return 的猜测执行不可以随即使用

## 控制变量
对于 delay、predict、victim 都有已有的样例，可以考虑每次之随机生成三个模块中的其中一个，其他的用固定样例，然后只针对这个 block 进行 fuzz

## train param for train block
没有启用 bim，默认 not taken
branch_taken 情况下，默认 not taken，不训练就可以触发成功
启用bim，默认 taken
branch_taken 情况下，初始化为 10，train 1 次可以成功触发 1 次，train 2 次可以成功触发 2 次

没有启用 bim，默认 not taken
branch_not_taken 情况下，默认 not taken，train 3 次可以成功触发 1 次，train 4 次可以成功触发 2 次
启用 bim，默认 taken
branch_not_taken 情况下，初始化为 10，默认 taken，不 train 就可以触发 1 次，train 1 次以上可以触发 2 次

## delay param for delay block
| transient window | kind  | instruction sequence                           |
|------------------|-------|------------------------------------------------|
| 8                | 1 F/D | fcvt                                           |
| 14               | 2 F/D | fnmadd fcvt                                    |
| 14               | 2 F/D | fmadd  fcvt                                    |
| 15               | 2 F/D | fcvt   fcvt                                    |
| 22               | 2 F/D | fsub   fcvt                                    |
| 17               | 3 F/D | fsgnjn fmadd  fcvt                             |
| 20               | 3 F/D | fmadd  fmadd  fcvt                             |
| 21               | 3 F/D | fnmadd fsgnjx fcvt                             |
| 21               | 3 F/D | fnmadd fcvt   fcvt                             |
| 24               | 4 F/D | fsgnjx fmin   fmadd  fcvt                      |
| 21               | 5 F/D | fsgnjx fsqrt  fsqrt  fsqrt  fcvt               |
| 24               | 5 F/D | fadd   fmax   fdiv   fmax   fcvt               |
| 24               | 7 F/D | fdiv   fdiv   fdiv   fidv   fidv   fdiv   fcvt |

* 1 条浮点的瞬态窗口为 8
* 2 条浮点的瞬态窗口为 14-22
* 3 条以上浮点的瞬态窗口为 17-24
* 瞬态窗口大小不超过 24

结论：浮点指令数目以 3-5 为宜，瞬态窗口基本在 20-24 之间

| transient window | kind      | instruction sequence                           |
|------------------|-----------|------------------------------------------------|
| 3                | 3 I       | and    and    and                              |
| 10               | 2 I + 1 M | srlw   mulhsu addiw                            |
| 12               | 2 I + 1 M | mulhsu add    divu                             |
| 14               | 2 I + 1 M | sub    divw   add                              |
| 20               | 1 I + 2 M | mulu   remu   sltu                             |
| 21               | 2 I + 1 I | div    srli   sub                              |
| 24               | 1 I + 2 M | divw   addiw  div                              |
| 12               | 3 I + 1 M | mulw   sll    slliw   srli                     |
| 13               | 3 I + 1 M | srai   rem    xor     slti                     |

* 任意指令都可以打开大小为 3 的瞬态窗口，这是 branch 预测错误本身的代价
* 3 条整型指令不会带来任何额外的收益
* 1 条 M 指令配合 2 条 I 指令的瞬态窗口 10-12
* 2 条 M 指令配合 1 条 I 指令的瞬态窗口 20-24
* 只有 M 指令可以带来瞬态窗口收益
* 瞬态窗口最大不超过 24
* div/rem 的收益略大于 mul，但是也和操作数大小有关
* 只有靠近 predict 指令的最近的指令序列才有效

结论：M 型指令和 F 型指令混合使用，指令序列长度 3-5 为宜，可以打开瞬态窗口大小 18-24 






