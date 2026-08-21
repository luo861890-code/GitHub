# 最终 Benchmark 报告（16 组完成）

## 运行方式

```bash
python tools/run_final_benchmark.py          # 全 16 组
python tools/run_final_benchmark.py --map tourism --scale 100000   # 单组
python tools/audit.py --benchmark            # 从输出评分汇总
```

输出：`benchmarks/wuhan/final/<map>_<scale>/{before,after,metrics,qa,runtime}.json`

## 16 组评分汇总（2026-08-21 实测）

| 组 | scale | QA | grade | status | dup | recall | Critical | runtime |
|---|--:|--:|---|--:|--:|--:|--:|--:|
| administrative | 1:500k | 934 | S | PASS | 0 | 1.0 | 0 | 33.6s |
| administrative | 1:250k | 934 | S | PASS | 0 | 1.0 | 0 | 33.4s |
| administrative | 1:100k | 934 | S | PASS | 0 | 1.0 | 0 | 34.9s |
| administrative | 1:25k | 922 | S | PASS | 0 | 1.0 | 0 | 35.6s |
| traffic | 1:500k | 923 | S | PASS | 0 | 1.0 | 0 | 88.8s |
| traffic | 1:250k | 920 | S | PASS | 0 | 1.0 | 0 | 97.1s |
| traffic | 1:100k | 920 | S | PASS | 0 | 1.0 | 0 | 104.1s |
| traffic | 1:25k | 918 | S | PASS | 0 | 1.0 | 0 | 103.9s |
| tourism | 1:500k | 929 | S | PASS | 0 | 1.0 | 0 | 154.4s |
| tourism | 1:250k | 927 | S | PASS | 0 | 1.0 | 0 | 160.6s |
| tourism | 1:100k | 927 | S | PASS | 0 | 1.0 | 0 | 169.9s |
| tourism | 1:25k | 926 | S | PASS | 0 | 1.0 | 0 | 171.6s |
| terrain | 1:500k | 900 | S | PASS | 0 | 1.0 | 0 | 8.9s |
| terrain | 1:250k | 900 | S | PASS | 0 | 1.0 | 0 | 10.0s |
| terrain | 1:100k | 900 | S | PASS | 0 | 1.0 | 0 | 10.5s |
| terrain | 1:25k | 894 | A | PASS | 0 | 1.0 | 0 | 18.5s |

## 性能修复

- terrain 生成从 ~10 分钟降至 8-19 秒（连接步骤不再合并无名称等高线）。
- 交通图 89-104s/尺度（位移规模保护 + 属性同步）。
- 未通过关闭 QA 提速（QA 全开）。
