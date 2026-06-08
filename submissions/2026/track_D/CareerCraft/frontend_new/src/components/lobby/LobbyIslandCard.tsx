'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { PixelCard, PixelButton } from '@/components/pixel';

interface LobbyIslandCardProps {
  title: string;
  description: string;
  icon: string;
  themeColor: string;
  route: string;
  features: string[];
}

export default function LobbyIslandCard({
  title,
  description,
  icon,
  themeColor,
  route,
  features,
}: LobbyIslandCardProps) {
  const [isHovered, setIsHovered] = useState(false);
  const router = useRouter();

  return (
    <div
      className="transition-all duration-200"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={() => router.push(route)}
    >
      <PixelCard
        hoverable
        className={`
          cursor-pointer
          transition-all duration-300
          ${isHovered ? 'scale-105' : ''}
        `}
      >
        <div
          className={`
            relative
            border-4
            p-6
            bg-slate-800
            transition-all duration-300
          `}
          style={{
            borderColor: isHovered ? '#f59e0b' : themeColor,
            boxShadow: isHovered
              ? `0 0 20px ${themeColor}, inset -4px -4px 0px 0px #0f172a, inset 4px 4px 0px 0px #475569`
              : 'inset -4px -4px 0px 0px #0f172a, inset 4px 4px 0px 0px #475569',
          }}
        >
          {isHovered && (
            <div className="absolute top-0 left-0 right-0 h-1 bg-amber-500 animate-pulse" />
          )}

          <div className="text-center">
            <div
              className="text-8xl mb-4"
              style={{ filter: isHovered ? 'drop-shadow(0 0 10px ' + themeColor + ')' : 'none' }}
            >
              {icon}
            </div>

            <h2
              className="text-2xl font-bold mb-3"
              style={{ color: themeColor }}
            >
              {title}
            </h2>

            <p className="text-slate-300 mb-6 leading-relaxed">
              {description}
            </p>

            <div className="space-y-2 mb-6">
              {features.map((feature, index) => (
                <div
                  key={index}
                  className="flex items-center gap-2 text-sm text-slate-400"
                >
                  <span className="text-green-500">✓</span>
                  <span>{feature}</span>
                </div>
              ))}
            </div>

            <PixelButton
              variant={themeColor === '#3b82f6' ? 'secondary' : 'primary'}
              className="w-full"
            >
              开始冒险 →
            </PixelButton>
          </div>
        </div>
      </PixelCard>
    </div>
  );
}
