import React from 'react';

export default function LobbyHeader() {
  return (
    <header className="text-center py-8">
      {/* 像素边框装饰条 */}
      <div className="flex justify-center gap-0.5 mb-4">
        {[...Array(16)].map((_, i) => (
          <div
            key={i}
            className="w-3 h-3 bg-amber-600"
            style={{
              boxShadow: 'inset -1px -1px 0px 0px rgba(0,0,0,0.3), inset 1px 1px 0px 0px rgba(255,255,255,0.2)',
            }}
          />
        ))}
      </div>

      {/* 主标题 */}
      <h1 className="pixel-title-xl text-5xl md:text-7xl mb-3 text-amber-500"
        style={{
          textShadow: '4px 4px 0px #92400e, 0 0 20px rgba(245,158,11,0.3)',
        }}
      >
        CAREERCRAFT
      </h1>

      {/* 副标题 - tagline */}
      <p className="text-lg md:text-xl text-slate-300 mb-3 font-bold"
        style={{
          textShadow: '2px 2px 0px rgba(0,0,0,0.5)',
        }}
      >
        构建职业未来，解锁无限可能！
      </p>

      {/* 像素风格分界线和图标 */}
      <div className="flex items-center justify-center gap-2 mb-3">
        <div className="flex gap-0.5">
          {[...Array(4)].map((_, i) => (
            <div key={`l-${i}`} className="w-2 h-2 bg-slate-600"
              style={{ boxShadow: 'inset -1px -1px 0px 0px rgba(0,0,0,0.3)' }}
            />
          ))}
        </div>
        <span className="text-2xl">⚔️</span>
        <span className="text-2xl pixel-pulse">🌟</span>
        <span className="text-2xl">🎮</span>
        <div className="flex gap-0.5">
          {[...Array(4)].map((_, i) => (
            <div key={`r-${i}`} className="w-2 h-2 bg-slate-600"
              style={{ boxShadow: 'inset -1px -1px 0px 0px rgba(0,0,0,0.3)' }}
            />
          ))}
        </div>
      </div>

      {/* 底部像素边框装饰条 */}
      <div className="flex justify-center gap-0.5 mt-4">
        {[...Array(16)].map((_, i) => (
          <div
            key={i}
            className="w-3 h-3 bg-amber-600"
            style={{
              boxShadow: 'inset -1px -1px 0px 0px rgba(0,0,0,0.3), inset 1px 1px 0px 0px rgba(255,255,255,0.2)',
            }}
          />
        ))}
      </div>
    </header>
  );
}