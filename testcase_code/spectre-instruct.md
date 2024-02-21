# spectre-rsb
## 工作原理
vitcim 函数首先执行 jalr ra, 0(t0)，t0 = exploit，类似于 call exploit 进入 exploit 函数。

exploit 函数：
1. 载入大浮点数 dummy1、dummy2 到浮点寄存器 fa4、fa5，然后做连续的`fdiv.s fa5, fa5, fa4`，得到 fa5 = 0
2. 执行`fcvt.lu.s	t0, fa5, rtz`，使得 t0 = 0
3. 执行`add ra, t0, main_half_bottom`，将返回地址设置为 main_half_bottom 函数的入口地址
4. `jalr zero, 0(ra)`也就是`ret`指令进入 main_half_bottom 函数做后续操作

在这个过程中，因为 fdiv.s 指令执行很慢，所以 fdiv.s 序列都在 FPU 和 保留站中等待，无法得到 fa5 最后的值。因此 fcvt.lu.s 指令无法得到 fa5 的值在保留站中等待，无法得到对应 t0 的值。 因此 add 指令因为无法得到 t0 的值在保留站中得到，无法得到对应的 ra 的值。

ret 指令本身应该等待 ra 的结果才作出跳转的，但是因为 ra 的值无法得到，所以进行了跳转地址的预测，因为 return stack 的存在一般 call 指令保存的 pc+4 就是 ret 指令的返回地址，所以猜测返回地址为 victim 的 call 的下一跳指令的地址也就是 leak_me，于是 leak_me 出不该被执行的指令被执行了，产生了一个瞬态窗口，可以在这里泄露 secret。

泄露用常见的`dummy3 = array[trapoline[offset]*CACHE_BLOCK]`，将 secret 的值对应的 probe line 读入 cache 即可。之后  return 等一系列 rob 提交，leak_me 被回滚，进入 main_half_bottom 函数用 access_time 测量 probe_line 的访问时间得到 secret 的值。

## 支持情况
* M 模式物理地址、U 模式虚拟地址都可以运行
* 可以触发瞬态窗口将 probe_line 进入 cache
* 可以测信道泄露数据根据 cache 访问时间得到 secret 值

# spectre-rewind

## 工作原理
victim 函数执行如下的汇编序列：
```
    uint64_t dummy1 = 0xa234b057963aef89ul;
    uint64_t dummy2 = 0x56fea3467def0136ul;

    asm("fcvt.s.lu	fa4, %[dummy1]\n"
        "fcvt.s.lu	fa5, %[dummy2]\n"
        "fdiv.s	fa5, fa5, fa4\n"
        "fdiv.s	fa5, fa5, fa4\n"
        "fdiv.s	fa5, fa5, fa4\n"
        "fdiv.s	fa5, fa5, fa4\n"
        "fcvt.lu.s	%[dummy2], fa5, rtz\n"
        : [dummy2] "+r" (dummy2)
        : [dummy1] "r" (dummy1)
        : "fa4", "fa5");
    INFO_DELAY_END;
```
1. 将两个大浮点数 dummy1、dummy2 载入 fa4、fa5
2. 执行连续的 fdiv.s fa5, fa5, fa4，最后得到 fa5 = 0
3. 将最后的结果 fa5 写入 dummy2 中

然后执行`if( dummy1 < dummy2 )`指令。load 指令需要从 lsu 中得到 dummy1、dummy2 的值，但是因为 dummy2 对应的 store 指令还在等待，所以 load 指令也会进入等待，branch 指令无法得到结果只能猜测执行。这个时候使用简单的分支预测器默认是 untaken，然后进入 if 语句，打开了瞬态窗口。

瞬态窗口访问 secret 的值然后和 guess 的值作比较，如果 guess 的值等于 secret 的值也就是猜测正确了，执行一个 fdiv.s 序列。如果猜测失败就不执行这个序列。

一段时间后延迟窗口的指令在 rob 中提交，然后回滚瞬态窗口的指令。如果 guess == secret 执行了 fdiv.s 序列，这个时候 rob 无法直接清空流水线和 rob，因为 fdiv.s 在 FPU 中执行且 FPU 作为协处理器无法被直接清空，因此必须等待 FPU 执行完毕，然后才可以清空 rob。不然就可以直接清空。这使得猜中与否对应的瞬态窗口的大小会变得不一样，可以测量这个瞬态窗口的时间大小来判断 guess 的值是否等于 secret，进入泄露 secret 的值。

我们可以在 taint.log 中看到如果猜测正确，rob 的提交用时如下：
```
INFO_TEXE_END,                 1220
INFO_DELAY_END_COMMIT,         1339
INFO_VCTM_END,                 1356
INFO_LEAK_END,                 1361
INFO_VCTM_END_COMMIT,          1363
INFO_LEAK_END_COMMIT,          1368
```
猜测失败如下：
```
INFO_TEXE_END,                 1220
INFO_TEXE_END,                 1251
INFO_DELAY_END_COMMIT,         1305
INFO_VCTM_END,                 1323
INFO_LEAK_END,                 1328
INFO_VCTM_END_COMMIT,          1330
INFO_LEAK_END_COMMIT,          1335
```
可以看到猜测成功的时候泄露用时更长，也就是内部的瞬态窗口更长

## 支持情况
* M 模式物理地址，U 模式虚拟地址可以运行
* 可以触发瞬态窗口得到 secret 的值
* 可以根据 if 语句延迟瞬态窗口的回滚，从而泄露 secret 的值

# spectre-v1

## 工作原理
使用连续的 fdiv.s 制造延迟，然后利用`if(dummy1<dummy2)`因为要等待 fdiv.s 得到的 dummy2 的结果而进行分支预测 untaken 进入 if 块，打开瞬态窗口和 spectre-rewind 开发瞬态窗口的方法保持一致。

使用`dummy3 = array[trapoline[offset]*CACHE_BLOCK]`配合 access_time 做侧信道的信息泄露，方法和 spectre-rsb 保持一致。

## 支持情况
* M 模式物理地址、U 模式虚拟地址都可以运行
* 可以触发瞬态窗口将 probe_line 进入 cache
* 可以测信道泄露数据根据 cache 访问时间得到 secret 值
U 模式虚拟地址原来的代码无法有效泄露信息，瞬态窗口的时间不够长，所以将 dummy2 改小，将 fdiv.s 序列改长使得瞬态窗口有足够的时间将 probe_line 写入 cache

# spectre-v2

## 工作原理
victim 接受两个参数，一个是跳板数组 trapoline 的数组索引 offset，一个是访问的函数指针 next。首先输入 offset=0，next=exploit，然后执行如下的汇编序列：
1. 载入 dummy1、dummy2 到 fa4、fa5，执行`fdiv.s fa5,fa5,fa4`的序列得到 fa5=0
2. 计算 dummy2=fa5+next
3. 将参数 offset 写入 a0，然后执行`jalr ra,0(dummy)`，相当于执行`next(offset)`

exploit 函数执行`dummy3 = array[trapoline[offset]*CACHE_BLOCK]`，所以这次就是调用 exploit，然后访问`trapoline[0]`，不会造成任何非法的操作。但是 BTB 和记住这个 jalr 预测的跳转目标是 exploit 的地址。

然后再次执行 victim，传入的参数选择 secret_offset 和 safe，其中`trapoline[secret_offset]`是需要泄露的 secret 的值，safe 是一个安全的函数。因为 fdiv.s 会导致 fa5 的值出现延迟，dummy2 的计算结果也会出现延迟，于是 jalr 的跳转目标会进行猜测执行，因为之前的训练使得 jalr 的预测目标是 exploit，所以打开了一个瞬态窗口可以执行 exploit 的指令，从而可以执行`dummy3 = array[trapoline[offset]*CACHE_BLOCK]`将 secret 泄漏到 cache 中。

## 支持情况
* M 模式物理地址、U 模式虚拟地址都可以运行
* 可以触发瞬态窗口将 probe_line 进入 cache
* 可以测信道泄露数据根据 cache 访问时间得到 secret 值

# spectre-v3

## 工作原理
首先在 setup_pmp 函数中修改 pmpaddr0 和 pmpcfg0，将 secret 对应的 0x1000 的数据设置为 M 态不可读、不可写、不可执行，然后执行 victim。

victim 首先用 fdiv.s 序列做延迟，然后执行`dummy3 = array[trapoline[offset]*CACHE_BLOCK]`，这个时候虽然读取`trapoline[offset]`会触发异常，但是因为 fdiv.s 正在执行，后续的 load 指令虽然触发了异常，但是因为读取`trapoline[offset]`的 load 还没有提交，exception 还没有被 rob 提交的地方接受然后回滚后续指令，所以 load 后续的指令可以继续执行，将 probe_line 存入 cache。

之后我们改写 trap_handle 函数，在这个函数里面调用 access_time 得到 secret 的值。

## 存疑
既然 load 指令已经被 pmp 机制检测出来存在异常了，为什么不直接终止 load 指令的执行还要允许它继续从内存中读入数据呢？为什么还要允许后续指令的执行？还是说允许后续指令执行仅仅是为了 rob 回滚的实现方便？

可以想见一条指令如果检查出存在异常或者说存在跳转的错误，这个时候我们可以发出信号让前端停止指令的发射，但是已经发射的、rob 中在这条指令后的指令的撤回是困难，它们的数量是变化的、存在的功能单元是多样的、执行完毕的情况是多样的，如果要求都准确找到位置然后准确无效会导致巨大的硬件资源开销。所以可以猜测这里是允许一旦一条指令检查出存在异常或者说存在跳转的错误，已经在 rob 中的后续指令允许他们执行完毕，然后依次提交，只不过这个提交过程是被无效处理的，也就是提交的寄存器的值不允许修改寄存器文件和内存的值。但是 load 对于 cache 的影响不算在其中。

实际上是不是这样有待确认。

## 支持情况
* M 模式物理地址、U 模式虚拟地址都可以运行
* 可以触发瞬态窗口将 probe_line 进入 cache
* 可以测信道泄露数据根据 cache 访问时间得到 secret 值

# spectre-v4

## 工作原理
1. 将 offset 的地址写入寄存器 t0、t1
2. 执行经典的 fdiv.s 进行延迟操作得到 t5=0
3. 执行`add t0, t5, t0`，让 t0 依赖于 t5
4. 执行`sd t5, 0(t0)`将 offset 写入 0
5. 执行`ld t6, 0(t1)`将写入 offset 的 0 读入 t6
6. 执行`dummy3 = array[trapoline[offset]*CACHE_BLOCK]`做侧信道泄露

这里因为 fdiv.s 的延迟的存在，t5 的值迟迟计算不到，所以 add 指令需要等待无法执行，sd 指令也进行等待无法执行，所以 offset 暂时不会被修改为 0。

之后 ld 指令访问 offset，他首先检查 lsu 来看看 store buffer 有没有冲突的地址之类会影响 load 结果的，但是 sd 没有执行所以猜测 offset 没有被修改，开启了瞬态窗口。它将 offset 的老值载入 t6，于是 之后的`array[trapoline[offset]*CACHE_BLOCK]`可以将数据泄漏到 cache。

之后 t0 计算得到结果，lsu 的 store 会和 load 发生冲突，于是后续的 load 操作开始回滚，offset 得到的值是 0，`trapoline[offset]`也是合法地址，所以正常执行结束。

## 支持情况
* M 模式物理地址、U 模式虚拟地址都可以运行
* 可以触发瞬态窗口将 probe_line 进入 cache
* 可以测信道泄露数据根据 cache 访问时间得到 secret 值
U 模式虚拟地址原来的代码无法有效泄露信息，瞬态窗口的时间不够长，所以将 dummy2 改小，将 fdiv.s 序列改长使得瞬态窗口有足够的时间将 probe_line 写入 cache（同 spectre-v1）