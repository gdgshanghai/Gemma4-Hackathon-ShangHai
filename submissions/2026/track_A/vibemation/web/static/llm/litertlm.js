/**
 * LiteRT 引擎封装 — OpenAI 兼容适配器
 *
 * LiteRT-LM (Google 官方) 提供浏览器端推理 SDK。
 * 模型从 Google Edge Gallery / gstatic CDN 下载。
 *
 * 由于 LiteRT 原生 API 非 OpenAI 格式，此适配器负责：
 *   1. 加载 LiteRT SDK + 模型
 *   2. 将 OpenAI messages 转换为 Gemma 4 原生模板
 *   3. 调用 LiteRT 推理 → 返回 OpenAI 格式结果
 *
 * 参考: docs/refs/web.txt (convertOpenAIToGemma4)
 *       https://ai.google.dev/edge/gallery
 */

let _engine = null;

/* ── LiteRT SDK 动态加载 ──────────────────────── */
async function getLiteRT() {
  // LiteRT-LM for Web 可通过 esm.sh / Google CDN 加载
  // 生产环境建议锁定版本号
  // TODO: 确认 Google 官方 CDN URL
  return import('https://esm.sh/@google-ai/litert@0.1.0');
}

/* ── 消息格式转换: OpenAI → Gemma 4 模板 ──────── */
function convertOpenAIToGemma4(messages, enableThinking = true) {
  let prompt = '';
  let systemPrompt = '';

  const systemMsg = messages.find(m => m.role === 'system');
  if (systemMsg) {
    systemPrompt = systemMsg.content + '\n\n';
  }

  const chatMessages = messages.filter(m => m.role !== 'system');

  chatMessages.forEach((msg, index) => {
    if (msg.role === 'user') {
      const content = (index === 0 && systemPrompt)
        ? `${systemPrompt}用户指令：${msg.content}`
        : msg.content;
      prompt += `<start_of_turn>user\n${content}<end_of_turn>\n`;
    } else if (msg.role === 'assistant') {
      prompt += `<start_of_turn>model\n${msg.content}<end_of_turn>\n`;
    } else if (msg.role === 'tool') {
      prompt += `<start_of_turn>user\n<response:${msg.name || 'tool'}>${msg.content}</response:${msg.name || 'tool'}><end_of_turn>\n`;
    }
  });

  if (enableThinking) {
    prompt += `<start_of_turn>model\n<start_of_turn>thought\n`;
  } else {
    prompt += `<start_of_turn>model\n`;
  }

  return prompt;
}

/* ── 模型大小映射 ────────────────────────────── */
const MODEL_URLS = {
  'gemma-4-e2b-it-q4': {
    label: 'Gemma 4 E2B Q4',
    downloadSize: '~2.5 GB',
    mirrors: [
      { name: 'Google Edge Gallery', url: 'https://www.gstatic.com/litert/models/gemma-4-e2b-it-q4.litertlm' },
      { name: 'ModelScope', url: 'https://www.modelscope.cn/google-ai/litert/gemma-4-e2b-it-q4/resolve/main/model.litertlm' },
      { name: 'Hugging Face', url: 'https://huggingface.co/google/litert-gemma-4-e2b-q4/resolve/main/model.litertlm' },
    ],
  },
  'gemma-4-e4b-it-q4': {
    label: 'Gemma 4 E4B Q4',
    downloadSize: '~4.5 GB',
    mirrors: [
      { name: 'Google Edge Gallery', url: 'https://www.gstatic.com/litert/models/gemma-4-e4b-it-q4.litertlm' },
      { name: 'ModelScope', url: 'https://www.modelscope.cn/google-ai/litert/gemma-4-e4b-it-q4/resolve/main/model.litertlm' },
    ],
  },
  'gemma-4-e4b-it-q5': {
    label: 'Gemma 4 E4B Q5',
    downloadSize: '~5.5 GB',
    mirrors: [
      { name: 'Google Edge Gallery', url: 'https://www.gstatic.com/litert/models/gemma-4-e4b-it-q5.litertlm' },
      { name: 'ModelScope', url: 'https://www.modelscope.cn/google-ai/litert/gemma-4-e4b-it-q5/resolve/main/model.litertlm' },
    ],
  },
};

/**
 * 检查 WebGPU / XNNPACK 支持
 * LiteRT 支持 CPU (XNNPACK) 和 WebGPU 两种后端
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

/**
 * 加载 LiteRT 模型
 * @param {string} modelId - 模型标识符
 * @param {function} onProgress - 进度回调 ({progress: 0-1, text: string})
 */
export async function loadModel(modelId, onProgress) {
  const litert = await getLiteRT();
  const modelInfo = MODEL_URLS[modelId];
  if (!modelInfo) {
    throw new Error(`未知模型: ${modelId}`);
  }

  const errors = [];
  for (const mirror of modelInfo.mirrors) {
    if (typeof onProgress === 'function') {
      onProgress({ progress: 0, text: `尝试从 ${mirror.name} 下载...` });
    }
    try {
      // TODO: LiteRT SDK 加载模型的实际 API
      // const modelRunner = await litert.LlmInference.createLLMInference({
      //   modelUrl: mirror.url,
      //   onProgress,
      // });
      // _engine = modelRunner;
      // return _engine;
      throw new Error('LiteRT SDK 尚未集成');
    } catch (e) {
      errors.push(`${mirror.name}: ${e.message || e}`);
    }
  }

  const errorMsg = `模型 ${modelInfo.label} 加载失败。\n` +
    `可用下载源:\n` +
    modelInfo.mirrors.map(m => `  • ${m.name}: ${m.url}`).join('\n') +
    `\n\n错误详情:\n` +
    errors.map(e => `  ❌ ${e}`).join('\n');
  throw new Error(errorMsg);
}

/**
 * 生成回复
 * @param {Array} messages - [{role, content}, ...]
 * @param {object} options - {temperature, max_tokens}
 * @returns {Promise<string>}
 */
export async function generate(messages, options = {}) {
  if (!_engine) throw new Error('模型未加载');

  // 1. 转换消息格式
  const prompt = convertOpenAIToGemma4(messages, true);

  // 2. 调用 LiteRT 推理
  // return new Promise((resolve, reject) => {
  //   let result = '';
  //   _engine.generateResponse(prompt, {
  //     temperature: options.temperature ?? 0.7,
  //     maxTokens: options.max_tokens ?? 4096,
  //   }, (text, done) => {
  //     result += text;
  //     if (done) resolve(result);
  //   });
  // });

  throw new Error('LiteRT 推理引擎尚未就绪，请等待 SDK 集成完成');
}

/**
 * 卸载模型，释放内存
 */
export function unload() {
  if (_engine) {
    try { _engine.delete(); } catch { /* ignore */ }
    _engine = null;
  }
}
