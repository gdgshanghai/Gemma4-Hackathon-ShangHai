import dynamic from 'next/dynamic';
import { Suspense } from 'react';

const CommunityContent = dynamic(() => import('./community-content'), {
  ssr: false,
});

export default function CommunityPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center text-slate-400">正在进入工程师社区...</div>}>
      <CommunityContent />
    </Suspense>
  );
}