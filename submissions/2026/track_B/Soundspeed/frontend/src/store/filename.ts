import { create } from "zustand"
import {
  type FileNameFormat,
  loadFileNameFormat,
  saveFileNameFormat,
} from "@/lib/filename-format"

// 文件名显示格式偏好（持久，localStorage）。独立于会话 store——纯显示偏好，跨会话保留。
// 各显示点（History / Live 分隔条 / 底栏 / titlebar / 详情）订阅 format，设置页调 setFormat。
interface FileNameState {
  format: FileNameFormat
  setFormat: (fmt: FileNameFormat) => void
}

export const useFileNameFormat = create<FileNameState>((set) => ({
  format: loadFileNameFormat(),
  setFormat: (fmt) => {
    saveFileNameFormat(fmt)
    set({ format: fmt })
  },
}))
