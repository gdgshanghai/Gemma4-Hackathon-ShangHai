/**
 * WebLLM 引擎封装 — OpenAI 兼容接口
 *
 * 底层: MLC-LLM WebLLM (@mlc-ai/web-llm)
 * API:   chat.completions.create (与 OpenAI SDK 一致)
 *
 * 模型下载源（按优先级尝试）:
 *   1. Hugging Face 官方 (huggingface.co/mlc-ai)
 *   2. hf-mirror.com (国内镜像)
 *   3. ModelScope (modelscope.cn)
 *   4. 用户自定义 URL
 */
let engine = null;

/* ── 模型配置表 ────────────────────────────── */
const MODEL_CONFIGS = {
  'gemma-4-e2b-it-q4f16_1-MLC': {
    label: 'Gemma 4 E2B Q4',
    hfRepo: 'mlc-ai/gemma-4-e2b-it-q4f16_1-MLC',
    // WebLLM 模型需要 MLC 编译后的格式，默认可从 Hugging Face 加载
    mirrors: [
      { name: 'Hugging Face', url: 'https://huggingface.co/mlc-ai/gemma-4-e2b-it-q4f16_1-MLC/resolve/main/' },
      { name: 'hf-mirror.com', url: 'https://hf-mirror.com/mlc-ai/gemma-4-e2b-it-q4f16_1-MLC/resolve/main/' },
      { name: 'ModelScope', url: 'https://www.modelscope.cn/mlc-ai/gemma-4-e2b-it-q4f16_1-MLC/resolve/main/' },
    ],
  },
  'gemma-4-e4b-it-q4f16_1-MLC': {
    label: 'Gemma 4 E4B Q4',
    hfRepo: 'mlc-ai/gemma-4-e4b-it-q4f16_1-MLC',
    mirrors: [
      { name: 'Hugging Face', url: 'https://huggingface.co/mlc-ai/gemma-4-e4b-it-q4f16_1-MLC/resolve/main/' },
      { name: 'hf-mirror.com', url: 'https://hf-mirror.com/mlc-ai/gemma-4-e4b-it-q4f16_1-MLC/resolve/main/' },
      { name: 'ModelScope', url: 'https://www.modelscope.cn/mlc-ai/gemma-4-e4b-it-q4f16_1-MLC/resolve/main/' },
    ],
  },
  'gemma-4-e4b-it-q5f16_1-MLC': {
    label: 'Gemma 4 E4B Q5',
    hfRepo: 'mlc-ai/gemma-4-e4b-it-q5f16_1-MLC',
    mirrors: [
      { name: 'Hugging Face', url: 'https://huggingface.co/mlc-ai/gemma-4-e4b-it-q5f16_1-MLC/resolve/main/' },
      { name: 'hf-mirror.com', url: 'https://hf-mirror.com/mlc-ai/gemma-4-e4b-it-q5f16_1-MLC/resolve/main/' },
      { name: 'ModelScope', url: 'https://www.modelscope.cn/mlc-ai/gemma-4-e4b-it-q5f16_1-MLC/resolve/main/' },
    ],
  },
};

// 动态 import（避免污染全局命名空间）
async function getMLC() {
  return import('https://esm.sh/@mlc-ai/web-llm@0.2.72');
}

/**
 * 加载 WebLLM 模型（自动尝试多个镜像源）
 * @param {string} modelId - 模型标识符
 * @param {function} onProgress - 进度回调 ({progress: 0-1, text: string})
 * @returns {Promise<object>} engine 实例
 */
export async function loadModel(modelId, onProgress) {
  const cfg = MODEL_CONFIGS[modelId];
  if (!cfg) {
    throw new Error(`未知模型: ${modelId}`);
  }

  const mlc = await getMLC();
  const errors = [];

  // 依次尝试每个镜像源
  for (const mirror of cfg.mirrors) {
    if (typeof onProgress === 'function') {
      onProgress({ progress: 0, text: `尝试从 ${mirror.name} 下载...` });
    }
    try {
      engine = await mlc.CreateMLCEngine(modelId, {
        modelUrl: mirror.url,
        initProgressCallback: onProgress,
      });
      return engine;
    } catch (e) {
      errors.push(`${mirror.name}: ${e.message || e}`);
      if (typeof onProgress === 'function') {
        onProgress({ progress: 0, text: `${mirror.name} 失败，尝试下一个源...` });
      }
    }
  }

  // 尝试不带 modelUrl 的默认加载（WebLLM 自行查询注册表）
  try {
    if (typeof onProgress === 'function') {
      onProgress({ progress: 0, text: '尝试从 WebLLM 注册表加载...' });
    }
    engine = await mlc.CreateMLCEngine(modelId, {
      initProgressCallback: onProgress,
    });
    return engine;
  } catch (e) {
    errors.push(`WebLLM 注册表: ${e.message || e}`);
  }

  // 全部失败
  const errorMsg = `模型 ${cfg.label} 加载失败。\n尝试了以下源:\n` +
    errors.map(e => `  ❌ ${e}`).join('\n') +
    `\n\n可用下载源:\n` +
    cfg.mirrors.map(m => `  • ${m.name}: ${m.url}`).join('\n') +
    `\n\n请确认:\n` +
    `  1. 模型已被 MLC-LLM 编译并上传到 Hugging Face\n` +
    `  2. 网络可访问上述镜像源\n` +
    `  3. 如需自定义源，可在 MODEL_CONFIGS 中配置`;
  throw new Error(errorMsg);
}

/**
 * 生成回复（OpenAI 兼容格式）
 * @param {Array} messages - [{role, content}, ...]
 * @param {object} options - {temperature, max_tokens, ...}
 * @returns {Promise<string>} 回复文本
 */
export async function generate(messages, options = {}) {
  if (!engine) throw new Error('模型未加载，请先调用 loadModel()');
  const reply = await engine.chat.completions.create({
    messages,
    temperature: options.temperature ?? 0.7,
    max_tokens: options.max_tokens ?? 4096,
  });
  return reply.choices?.[0]?.message?.content || '';
}

/**
 * 卸载模型，释放内存
 */
export function unload() {
  if (engine) {
    try { engine.resetChat(); } catch { /* ignore */ }
    engine = null;
  }
}

/**
 * 检查 WebGPU 支持
 * @returns {boolean}
 */
export async function checkWebGPU() {
  if (!navigator.gpu) return false;
  try {
    const adapter = await navigator.gpu.requestAdapter();
    return !!adapter;
  } catch {
    return false;
  }
}
