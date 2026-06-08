# Windows llama-cpp-python 安装 runbook（0.A.0）

日期：2026-06-02
配套：Notion 0.A.0（新设备硬件探测 + 跨平台安装 onboarding）/ spike 0.C.1 / spec `docs/specs/2026-05-27-llm-backend-selection.md` §11.4
适用范围：Windows 11 + NVIDIA 独显（本例 RTX 3070 Ti，Ampere sm_86，8 GB 显存）

llama-cpp-python 不是纯 Python，它是 llama.cpp 的绑定，里面带一份 native 二进制（llama.cpp 本体 + GPU 后端）。装的时候这份二进制必须和本机的「OS + CPU 架构 + 加速后端（CUDA / Metal / CPU）+ GPU 架构（CUDA 下的 sm 版本）」对上，错一项要么装不上要么装上了不认卡。Python 版本（cp 标签）是否要对，取决于 wheel 的 ABI：标准 CPython-ABI wheel 要对，dougeeai 的 py3-none（ctypes）wheel 不绑 Python 版本（详见 §3）。所以这台机的流程是：先探测，再按探测结果挑装法。

## 1. 探测本地设备

激活 venv 之前或之后都能跑（脚本只用标准库），但建议在目标 venv 里跑，好顺带看到 `python.in_venv` 和 `llama_cpp_python` 这两项的真实状态：

```powershell
python scripts\detect_device.py
```

跑完会在仓库根生成 `device-detected.json`，同时 stdout 打一份中文摘要。

**关于 `device-detected.json` 这个文件**：它是本机环境快照，由 `scripts/detect_device.py` 生成。字段含义见下表。它已被 `.gitignore` 忽略，因为每台机的硬件、驱动、Python 版本都不同，入库没意义还会互相覆盖。它的用途有三个：① 给本 runbook 的安装决策提供输入（装哪个 wheel、要不要自编译、要不要降参）；② 留一份环境快照便于复现问题；③ 当 0.C.1 spike 的验证证据，跑通后可脱敏附 PR。

字段说明：

| 字段 | 含义 |
| --- | --- |
| `schema_version` | JSON 结构版本，当前 1。结构变更时递增。 |
| `timestamp` | 探测时刻（`datetime.now().isoformat()`）。 |
| `os` | `system` / `release` / `version` / `machine` / `platform`，来自 platform 模块。 |
| `python` | `version` / `executable` / `implementation` / `in_venv`（`sys.prefix != sys.base_prefix`，判是否在 venv 里）。 |
| `nvidia_gpu` | `detected` / `name` / `memory_total_mb` / `driver_version` / `compute_cap`（GPU compute capability，形如 "8.6"，对应 sm 架构，选 wheel 用）/ `cuda_version_driver`（驱动支持的 CUDA 版本，非 Toolkit）/ `error`。靠 nvidia-smi。 |
| `cuda_toolkit` | `nvcc_found` / `version` / `error`。靠 nvcc，只有自编译时才需要它。 |
| `apple_metal` | `detected` / `chip` / `error`。仅 macOS 有意义，Windows 上 `detected=false`。 |
| `llama_cpp_python` | `installed` / `version` / `import_ok` / `gpu_offload_supported` / `error`。装之前全是 false/null，装完回来再跑就能看到。 |
| `model` | `gemma_model_path_env` / `env_path_exists` / `default_path` / `default_path_exists` / `size_bytes`。只看路径是否存在，不碰 huggingface_hub。 |

一台 Windows 11 + RTX 3070 Ti、已建好 Python 3.12 venv、但还没装 llama-cpp-python 的机器，探测结果大致长这样（脱敏样例，路径和值按本机会不同）：

```json
{
  "schema_version": 1,
  "timestamp": "2026-06-02T14:30:00.000000",
  "os": {
    "system": "Windows",
    "release": "11",
    "version": "10.0.26100",
    "machine": "AMD64",
    "platform": "Windows-11-10.0.26100-SP0"
  },
  "python": {
    "version": "3.12.10",
    "executable": "C:\\Users\\dev\\Soundspeed\\.venv\\Scripts\\python.exe",
    "implementation": "CPython",
    "in_venv": true
  },
  "nvidia_gpu": {
    "detected": true,
    "name": "NVIDIA GeForce RTX 3070 Ti",
    "memory_total_mb": 8192,
    "driver_version": "560.94",
    "compute_cap": "8.6",
    "cuda_version_driver": "12.6",
    "error": null
  },
  "cuda_toolkit": {
    "nvcc_found": false,
    "version": null,
    "error": "nvcc 未找到（未装 CUDA Toolkit 或不在 PATH）"
  },
  "apple_metal": {
    "detected": false,
    "chip": null,
    "error": "非 Darwin 平台，Apple Metal 不适用"
  },
  "llama_cpp_python": {
    "installed": false,
    "version": null,
    "import_ok": false,
    "gpu_offload_supported": null,
    "error": "llama-cpp-python 未安装（PackageNotFoundError）"
  },
  "model": {
    "gemma_model_path_env": null,
    "env_path_exists": false,
    "default_path": "C:\\Users\\dev\\Soundspeed\\models\\gemma-4-E4B-it-Q4_K_M.gguf",
    "default_path_exists": false,
    "size_bytes": null
  }
}
```

看这份样例做几个决策：`nvidia_gpu.compute_cap=8.6` → Ampere 架构 sm86 → 选带 `sm86.ampere` 的 wheel（架构选错装上不认卡，详见 §3）；`nvidia_gpu.cuda_version_driver=12.6` → 选 cuda12.1 的 wheel（CUDA 12.x 向下通吃）；首选的 dougeeai py3-none wheel 与 Python 版本无关，不用纠结 cp 标签；`cuda_toolkit.nvcc_found=false` → 没装 Toolkit，走现成 wheel 主路（自编译才需要它）。

## 2. 装 Python 3.12 + 建并激活 venv

从 python.org 装 Python 3.12（勾「Add to PATH」），然后：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

如果激活报「无法加载文件……禁止运行脚本」，是 PowerShell 执行策略挡了，放开当前用户即可：

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

激活成功后提示符前面会出现 `(.venv)`。

venv 用的 Python 版本（这里是 3.12）决定了能装哪个 cp 标签的 wheel——但这只对标准 CPython-ABI wheel 成立：那种 wheel 在 3.12 venv 里只能装 cp312 的，装错标签 pip 会拒绝或回退去编译源码。§3 首选的 dougeeai py3-none（ctypes）wheel 不绑 Python 版本，不受此限。选 3.12 是因为它对标准 ABI 和 py3-none 两类 wheel 覆盖都全（详见 §3 / §8）。各台机的 venv 互相独立，不同机器可独立选版本。

## 3. 装 llama-cpp-python

**主路：装现成的 CUDA wheel（dougeeai）。** 来源是 GitHub 上的 `dougeeai/llama-cpp-python-wheels`，从它的 releases 下。dougeeai 不像 PyPI 那样一个版本一个 wheel，它按**三个维度**切：**CUDA 版本 × GPU 架构（sm_xx）× ABI**。挑文件时这三维都要对上，错一维要么装不上要么装上不认卡。

**架构维（最容易踩坑）：选 sm 架构。** 你的卡 RTX 3070 Ti 是 Ampere，compute capability 8.6，对应 `sm86.ampere`。用 §1 探测的 `nvidia_gpu.compute_cap=8.6` 直接判，或按型号查下表：

| GPU 代次 | 例子 | compute_cap | sm 标签 |
| --- | --- | --- | --- |
| Turing | RTX 20 系 | 7.5 | sm75 |
| **Ampere** | **RTX 30 系 / A100** | **8.0 / 8.6** | **sm80 · sm86** |
| Ada | RTX 40 系 | 8.9 | sm89 |
| Blackwell | RTX 50 系 | 10.0 / 12.0 | sm100 · sm120 |

dougeeai 的 latest release 往往是 Blackwell（sm100/120）的，**别直接抓 latest**，那个装上去不认你的 Ampere 卡。3070 Ti 必须找带 `sm86.ampere` 的文件。

**CUDA 维：选 CUDA 版本。** 看 §1 的 `nvidia_gpu.cuda_version_driver`（本例 12.6）。dougeeai 有 cuda11.8 / cuda12.1 / cuda13.0 三档。规则是 wheel 的 CUDA ≤ 驱动支持的 CUDA。**推荐 cuda12.1**：CUDA 12.x 驱动向下兼容整条 12.x，兼容面最广。如果驱动支持 13.0 且你想要新的，可选 cuda13.0。

**ABI 维：py3-none 还是 cp 标签。** dougeeai 两代命名不同：
- **v0.3.20 是 `py3-none`**（ctypes 实现，**Python 版本无关**，3.12 / 3.13 都能装），按 CUDA+sm 分。
- **v0.3.16 是 cp 标签**（cp310/311/312/313，绑 Python 版本，**没有 cp314**），也按 CUDA+sm 分。

**首选**（最新 + Python 版本灵活 + Ampere + CUDA 12.x 通吃）：

```
llama_cpp_python-0.3.20+cuda12.1.sm86.ampere-py3-none-win_amd64.whl
```

**备选**（要 cp 标签的标准 ABI 构建时）：

```
llama_cpp_python-0.3.16+cuda12.1.sm86.ampere-cp312-cp312-win_amd64.whl
```

下载地址形如 `https://github.com/dougeeai/llama-cpp-python-wheels/releases/download/<tag>/<文件名>`，tag 形如 `v0.3.20-cuda12.1-sm86`。**tag 段去 dougeeai releases 页核对实际名再拼**（下面命令里的 tag 是示例，对不上会 404）。直接 pip 装这个 URL（或先下到本地再装本地路径）：

```powershell
pip install "https://github.com/dougeeai/llama-cpp-python-wheels/releases/download/v0.3.20-cuda12.1-sm86/llama_cpp_python-0.3.20+cuda12.1.sm86.ampere-py3-none-win_amd64.whl"
```

注意：首选的 v0.3.20 是 py3-none，不绑 Python 版本，所以这一步不用纠结 cp 标签和 venv 的 Python 对不对——只有走备选的 v0.3.16（或下面自编译）那种标准 CPython-ABI wheel 才要 cp312 对齐 3.12 venv。

**备路：自己编译。** 现成 wheel 找不到合适的 CUDA×sm 组合，或要最新的 llama.cpp（比如认 Gemma 4 架构）时才走这条。先装好三样：Visual Studio Build Tools（勾「使用 C++ 的桌面开发」工作负载）、CMake、CUDA Toolkit（版本对齐驱动支持的 CUDA）。然后：

```powershell
$env:CMAKE_ARGS="-DGGML_CUDA=on"
pip install llama-cpp-python --no-binary llama-cpp-python
```

`--no-binary` 强制从源码编译，`CMAKE_ARGS` 把 CUDA 后端打开。编译要十几分钟，期间吃 CPU 和内存。自编译产出的是标准 CPython-ABI wheel，绑当前 venv 的 Python 版本。

**安装顺序很重要：先装 llama-cpp-python（§3），再装其余依赖（§4）。** 顺序反了的话，`pip install -r backend\requirements.txt` 里有 llama-cpp-python 这一项，pip 会去 PyPI 找 Windows 预编译 wheel——PyPI 上没有 CUDA 版的，于是回退去编译 sdist，而本机多半没装编译链，直接失败。先把对的 wheel 装进去，requirements 再装时 pip 看到已满足就跳过，不会去 PyPI 找。

## 4. 装依赖

```powershell
pip install -r backend\requirements.txt
```

承上，这一步前提是 §3 已把 llama-cpp-python 装好。

> **依赖清单已是 uv 派生物。** `backend/requirements.txt` 现由 `uv export` 从 `uv.lock` 自动生成，头部自带「autogenerated by uv」注释，勿手改。要改依赖先动 `pyproject.toml`，再重跑 `uv export`。它是 universal 清单（带平台 marker），mac 与 Windows 各取所需。
>
> **Windows 优先 `uv sync`。** 一条命令按 `[tool.uv.sources]` 把 torch/torchaudio 走 cu128 index、其余走 PyPI，省掉本节手装。若坚持 `pip install -r`：清单里 `torch==2.11.0+cu128`、`torchaudio==2.11.0+cu128` 这两行 PyPI 上没有，pip 直接找不到。须先从 cu128 index 单装好 torch/torchaudio，套路同 §3「先装对的，再让 -r 看到已满足就跳过」，再跑 `pip install -r`。

## 5. 三层验证

**① 看版本装上了没：**

```powershell
pip show llama-cpp-python
```

**② import 能不能成（这步最容易爆雷）：**

```powershell
python -c "import llama_cpp; print(llama_cpp.__version__)"
```

最常见的失败是 `ImportError: DLL load failed while importing llama_cpp`。含义是 native 二进制加载时找不到 CUDA 运行时 DLL（cudart、cublas 等）。解法：装对应版本的 CUDA Toolkit 让这些 DLL 进 PATH，或者确认所选 wheel 是「自带 DLL」的构建（dougeeai 的多数 wheel 把运行时 DLL 一并打进包里，装上即可 import，这种就不必单独装 Toolkit）。

**③ 端到端真加载一次模型并推理。** 这步才是真正的验证门——前两步只证明包装上了、能 import，证明不了这份 wheel 里 vendored 的 llama.cpp 认不认 Gemma 4、卡有没有真用上。在仓库根放一个 `check_llama.py`：

```python
from llama_cpp import Llama

MODEL = r"C:\Users\dev\Soundspeed\models\gemma-4-E4B-it-Q4_K_M.gguf"

llm = Llama(
    model_path=MODEL,
    n_gpu_layers=-1,
    n_ctx=4096,
    verbose=True,
)
out = llm.create_chat_completion(
    messages=[{"role": "user", "content": "ping"}]
)
print(out["choices"][0]["message"]["content"])
```

```powershell
python check_llama.py
```

`verbose=True` 会打一大片日志，盯三样：

- `ggml_cuda_init: found 1 CUDA devices` —— CUDA 后端认到卡了。没有这行说明这份 wheel 是 CPU 版或 CUDA 没起来。
- `load_tensors: offloaded N/N layers to GPU` —— 层真卸载到 GPU 了。如果是 `0/N`，说明根本没用上 GPU（在 CPU 上跑），白搭。
- 有没有 `unknown architecture` 之类不认 Gemma 4 的报错。如果有，说明这份 wheel 里 vendored 的 llama.cpp 太旧，不认 Gemma 4 架构，得换更新的 wheel 或走 §3 备路自编译（自编译会拉当时最新的 llama.cpp）。

三样都对、`ping` 有回复，才算这台机 LLM 后端通了。

## 6. 起后端

Windows PowerShell 设环境变量是 `$env:VAR="..."`，不是 mac 那种行内 `VAR=val cmd`，得一行一行设好再起进程：

```powershell
$env:SOUNDSPEED_DEV="1"
$env:ADMIN_TOKEN="devtoken"
$env:SOUNDSPEED_DB="./soundspeed_dev.db"
$env:GEMMA_MODEL_PATH="C:\Users\dev\Soundspeed\models\gemma-4-E4B-it-Q4_K_M.gguf"
python -m backend.api
```

`GEMMA_MODEL_PATH` 给 Windows 绝对路径指向本机权重；不设的话 service 会自动从 HuggingFace 下载（首次慢，要联网）。健康检查：

```powershell
curl http://localhost:8000/healthz
```

返回 `{"status":"ok"}` 即后端起来了。

## 7. 显存调参

3070 Ti 只有 8 GB 显存。模型 4.6 GB，再加 `n_ctx=8192` 的 KV cache、算子缓冲、还有 Windows 桌面本身占的那部分显存，全卸载（`n_gpu_layers=-1`）时余量很窄，可能 CUDA OOM。

策略：先按生产默认原样跑——`python -m backend.api` 用的就是 `backend/llm/client.py` 里的 `n_ctx=8192, n_gpu_layers=-1`（§5 第③步 `check_llama.py` 里的 `n_ctx=4096` 只是个更小的冒烟测试，不是调参基线，别拿它当起点）。全卸载（`-1`）是最吃显存、最可能 OOM 的配置，所以下面这套降级只在真 OOM 了才动，按这个顺序往「保守」走：

1. 先把 `n_gpu_layers` 从 -1 降到部分卸载（比如 30），保住 `n_ctx=8192` 的长 take 能力。剩余的层留在 CPU 上，慢一点但不 OOM。
2. 还不够，再把 `n_ctx` 砍回 4096，省下一半 KV cache 显存。

**别直接改死 `backend/llm/client.py` 的 `_LLAMA_DEFAULTS`。** 那份默认（`n_ctx=8192, n_gpu_layers=-1, seed=42, verbose=False`）是 mac 和 Windows 共用的，在这里改死会拖累 mac（M1 Max 显存充足，不需要降）。`GemmaClient` 构造函数支持 `**llama_kwargs` 覆盖，但 `service.py` 的 `_ensure_client` 现在没把任何 per-machine 参数传下去。真要按机调参，正确做法是后续给 service 加一条环境变量覆盖通道（读 env 拼进 llama_kwargs）。这属于 0.A.0 决策层 playbook 的后续工作，不在本 runbook 动代码。

## 8. 已知坑 / 限制

- **`ImportError: DLL load failed`**：CUDA 运行时 DLL 找不到。装对应 CUDA Toolkit，或换自带 DLL 的 wheel。见 §5 第②步。
- **GPU 架构（sm）必须匹配**：dougeeai 按 sm 架构分 wheel，装错架构（如给 Ampere 卡装 Blackwell 的 sm100/120 wheel）装上去不认卡。按 §1 的 `compute_cap` 或 §3 的型号对照表选对 sm（3070 Ti = sm86.ampere）。别直接抓 latest release，那个常是 Blackwell 的。
- **cp 标签必须对齐 Python 版本（仅限标准 ABI wheel）**：只对标准 CPython-ABI wheel 成立——dougeeai v0.3.16、rookiemann、自编译产物这类，cp312 wheel 只能进 3.12 venv，装错 pip 会拒装或回退编译。dougeeai **v0.3.20 是 py3-none（ctypes），Python 版本无关，不受此限**，3.12/3.13 都能装。
- **PowerShell 执行策略**：激活 venv 报禁止运行脚本，`Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`。见 §2。
- **现成 wheel 是社区构建**：dougeeai 等来源是第三方构建，有信任和版本风险，用前对一下 CUDA / sm 架构 / 平台标签（cp 标签视 ABI 而定），跑通 §5 第③步再信。
- **Gemma 4 后端兼容**：能不能认 Gemma 4 架构，只能靠 §5 第③步实测（看有没有 `unknown architecture`），不能假定现成 wheel 一定认。
- **cp 标签覆盖说明（供参考）**：dougeeai v0.3.16 标准 ABI wheel 提供 cp310/311/312/313，cp312 覆盖面广且稳定。dougeeai v0.3.20 是 py3-none，Python 版本无关，3.12/3.13/3.14 都能装。项目 `requires-python = ">=3.12"`，Windows 推荐用 Python 3.12 venv，与 pyproject.toml 对齐。
- **真实音频 ASR（1.C）未完成**：不影响本 runbook 的 LLM 后端验证。本 runbook 只验 llama-cpp-python + Gemma 加载推理这条链，ASR 是另一条独立的线。
