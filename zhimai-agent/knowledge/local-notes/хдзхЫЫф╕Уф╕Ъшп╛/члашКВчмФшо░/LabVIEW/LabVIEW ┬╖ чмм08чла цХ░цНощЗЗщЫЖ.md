---
tags: [大四, 章节笔记, LabVIEW]
课程: LabVIEW虚拟仪器设计及应用
章节: 第08章 数据采集
状态: 待学习
created: 2026-10-22
updated: 2026-10-23
---

# LabVIEW · 第08章　数据采集

返回 [[课程 · LabVIEW虚拟仪器设计及应用]] · [[大四专业课 · 总览]]

## 学习目标

- [ ] 能用数据流解释本章 VI 的执行过程
- [ ] 能搭出一个最小可运行示例并保存测试数据
- [ ] 能处理错误线、资源释放、时序和版本差异

## 目录锚点

- 采集系统构成、信号输入、采样定理与数据采集卡
- 任务、虚拟通道、基本环节与两种途径
- 定时与任务状态转换
- 采集卡连接、测试与模拟输入/输出

## 学习任务

1. 建立一个只验证本章核心概念的最小 VI。
2. 为输入、输出和关键节点标注数据类型。
3. 设计正常、边界和异常三组测试。
4. 保存前面板截图、程序框图截图和测试结果。

## 可直接使用的知识

采样定理要求 $f_s>2f_{max}$，但工程上还需抗混叠滤波和过渡带，常取信号最高有效频率的 2.5–10 倍。频率分辨率为 $\Delta f=f_s/N$，提高分辨率需要更长记录或更低采样率。

### DAQ 任务配置

通道定义传感类型、物理端口、量程和接线方式；Timing 定义采样率、每通道样本数及有限/连续采样；Trigger 决定共同起点；Read 决定每次从缓冲区取多少样本。

差分接线抗共模干扰较好；RSE/NRSE 是否合适取决于信号是否接地和接地关系。量程应尽量贴近信号峰值以利用 ADC 动态范围，同时留出过载余量。

连续采集的读速率必须长期不低于产生速率。出现缓冲区溢出时，检查每次读取量、循环耗时、磁盘写入、显示刷新和采样率，而不是只扩大缓存。

### 来源与版本

- [清华大学出版社：本教材图书页](https://www.tup.tsinghua.edu.cn/bookscenter/book_07683001.html)确认本书以 LabVIEW 2017 为基础，且第 8 章涉及数据采集。
- [NI：DAQmx Timing 与采样率](https://knowledge.ni.com/KnowledgeArticleDetails?id=kA00Z000000P7KdSAK&l=en-US)区分硬件采样速率与软件读取量。
- [NI：DAQmx 时序与同步](https://www.ni.com/en/support/documentation/supplemental/06/timing-and-synchronization-features-of-ni-daqmx.html)说明共享采样时钟与触发的差异。

## 课堂补充

## 可复现实验：一路电压有限采样与连续采样

有支持 NI-DAQmx 的设备时，先在 NI MAX 的测试面板确认设备及输入端口正常，并以设备手册核对允许输入范围。下面是 NI DAQmx 接口的一般实验顺序，物理通道名、接线和实际最大采样率均由设备型号决定。

1. **有限采样**：`DAQmx Create Virtual Channel (AI Voltage)` 选择实际物理通道并设量程；`DAQmx Timing (Sample Clock)` 设 `1000 samples/s`、有限 `1000 samples/channel`；`DAQmx Start Task → DAQmx Read (1 Channel N Samples)`；记录波形和错误码；最后 `DAQmx Clear Task`。预期记录时长约 1 秒，采样率和样本数只作为教学示例。
2. **连续采样**：Timing 改为 Continuous，Start 放在 While 循环外；每次 Read 取 `100 samples/channel`，名义上每次覆盖 `0.1 s`。循环内只做轻量显示，原始块送到保存队列；停止后先退出循环，再 Clear Task。不要在每次 Read 前重新 Start。
3. 检验时间轴：若波形 `dt=0.001 s`，1,000 点的首末时间相差 `0.999 s`，而采集窗口约 1 秒。把“每次 Read 读取 100 点”和“硬件每秒采样 1,000 点”分别记录，二者不是同一个参数。
4. 用 0 V 或厂商批准的测试信号做正常测试；拔掉设备/改错通道名测试错误路径。若连续采集丢样，先检查读循环与写盘吞吐、显示刷新及设备支持的通道合计速率。

**来源**：[NI：NI-DAQmx 常用函数与 LabVIEW 流程](https://www.ni.com/en/support/documentation/supplemental/06/learn-10-functions-in-ni-daqmx-and-handle-80-percent-of-your-dat.html)、[清华大学出版社：本书目录](https://www.tup.tsinghua.edu.cn/bookscenter/bookcatalog?id=07683001)。示例参数为学习演算，不是教材指定设备参数。

> [!note] 记录 LabVIEW/驱动版本、硬件型号、教师强调和考试提示。

## 核心概念

| 节点/概念 | 输入 | 输出 | 时序/错误处理 |
| --- | --- | --- | --- |
|  |  |  |  |

## 实践记录

- VI 目标：
- 软件与驱动版本：
- 硬件/接口：
- 采样或通信参数：
- 测试数据：
- 异常与排查：
- VI/数据文件：

## 易错点

- [ ] 不用连线整齐代替数据流与时序分析
- [ ] 采集和通信程序必须处理停止、超时、错误与资源释放
- [ ] 波形、数组、动态数据类型之间的转换需记录单位和采样信息

## 自测

1. 哪条数据依赖决定执行顺序？
2. 哪些参数会造成丢样、阻塞或界面卡顿？
3. 怎样证明程序对边界输入仍然可靠？

## 一句话总结

> 待学习后补充。

