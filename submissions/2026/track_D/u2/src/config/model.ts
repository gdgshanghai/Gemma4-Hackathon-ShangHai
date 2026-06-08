export const WEB_MODEL_ID = 'onnx-community/gemma-4-E4B-it-ONNX'
export const MOBILE_MODEL_ID = 'onnx-community/gemma-4-E4B-it-qat-mobile-ONNX'
export const BUNDLED_MODEL_FOLDER = 'gemma-4-E4B-it-ONNX'
export const MODEL_SOURCE = import.meta.env.VITE_GEMMA_MODEL_SOURCE === 'bundled' ? 'bundled' : 'remote'
export const MODEL_ID = import.meta.env.VITE_GEMMA_MODEL_ID || (MODEL_SOURCE === 'bundled' ? BUNDLED_MODEL_FOLDER : WEB_MODEL_ID)
