import { useState } from 'react'
import { useAppStore } from '../store/appStore'

export default function SafeScreen() {
  const [notes, setNotes] = useState('周一\n- 取快递\n- 买牛奶\n\n本周\n- 整理房间\n- 预约洗牙')
  const setHidden = useAppStore((state) => state.setHidden)
  return (
    <div className="u2-screen safe-screen" onDoubleClick={() => setHidden(false)}>
      <div className="status-bar"><span>9:41</span><span>•••</span></div>
      <header><strong>备忘录</strong><button onClick={() => setHidden(false)}>完成</button></header>
      <textarea value={notes} onChange={(event) => setNotes(event.target.value)} aria-label="备忘录内容" />
      <div className="safe-hint">双击空白处也可返回</div>
    </div>
  )
}
