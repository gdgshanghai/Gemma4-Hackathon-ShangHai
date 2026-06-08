import { useTranslation } from 'react-i18next';
import { CheckCircle2, CloudUpload, CornerLeftUp, Sparkles } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import InventorySectionFrame from './InventorySectionFrame';
import type {
  InventoryActionNotice,
  InventoryConversionState,
  InventoryItemViewModel,
} from '../../types/inventory';

interface InventoryUploadPanelProps {
  token: string;
  selectedItem?: InventoryItemViewModel;
  conversionState: InventoryConversionState;
  notice?: InventoryActionNotice | null;
  onUpload: (file: File) => Promise<void>;
  onOneClickConvert: (collectionId: number) => Promise<void>;
  guidedStage: 'upload' | 'review' | 'card' | 'mint';
  onGuidedStageChange: (stage: 'upload' | 'review' | 'card' | 'mint') => void;
}

export default function InventoryUploadPanel({
  token,
  selectedItem,
  conversionState,
  notice,
  onUpload,
  onOneClickConvert,
  guidedStage,
  onGuidedStageChange,
}: InventoryUploadPanelProps) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    if (conversionState.uploadStatus !== 'uploading' && conversionState.uploadStatus !== 'uploaded') {
      setPreviewUrl(null);
    }
  }, [conversionState.uploadStatus]);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const handleFile = (file: File) => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(URL.createObjectURL(file));
    void onUpload(file);
  };

  const stages = [
    { key: 'upload' as const, label: t('upload.stageUpload') },
    { key: 'review' as const, label: t('upload.stageReview') },
    { key: 'card' as const, label: t('upload.stageCard') },
    { key: 'mint' as const, label: t('upload.stageMint') },
  ];

  const isReadyForOneClick = Boolean(token && conversionState.collectionId);
  const canGoBack = guidedStage !== 'upload';
  const canContinueToReview = conversionState.collectionId && conversionState.aiStatus !== 'pending';
  const canContinueToCard = guidedStage === 'review';
  const canContinueToMint = guidedStage === 'card' && conversionState.cardStatus === 'completed';

  return (
    <div className="space-y-6">
      <InventorySectionFrame title={t('upload.title')} contentClassName="space-y-5">
        <div className="flex flex-wrap gap-2">
          {stages.map((stage, index) => {
            const isActive = guidedStage === stage.key;
            const isComplete = stages.findIndex((item) => item.key === guidedStage) > index;
            return (
              <button
                key={stage.key}
                type="button"
                onClick={() => onGuidedStageChange(stage.key)}
                className={[
                  'rounded-full border px-4 py-2 text-sm transition',
                  isActive
                    ? 'border-cyan-300/35 bg-cyan-300/10 text-cyan-100 shadow-[0_0_18px_rgba(34,211,238,0.18)]'
                    : isComplete
                      ? 'border-emerald-300/20 bg-emerald-300/8 text-emerald-100'
                      : 'border-white/8 bg-white/5 text-slate-300/75 hover:border-cyan-300/20 hover:text-white',
                ].join(' ')}
              >
                {stage.label}
              </button>
            );
          })}
        </div>

        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setIsDragging(false);
            const file = event.dataTransfer.files?.[0];
            if (file) {
              handleFile(file);
            }
          }}
          className={[
            'group rounded-[1.75rem] border border-dashed p-8 text-center transition',
            isDragging
              ? 'border-cyan-300/40 bg-cyan-300/8 shadow-[0_0_24px_rgba(34,211,238,0.18)]'
              : 'border-cyan-400/15 bg-[#071523]/75 hover:border-cyan-300/25',
          ].join(' ')}
        >
          <input
            ref={inputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) {
                handleFile(file);
              }
            }}
          />

          {previewUrl ? (
            <div className="relative">
              <img
                src={previewUrl}
                alt=""
                className="max-h-48 w-full rounded-xl object-contain"
              />
              <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-black/60 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    inputRef.current?.click();
                  }}
                  className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-base font-medium text-cyan-100"
                >
                  {t('upload.chooseImage')}
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-300/20 bg-cyan-300/10 text-cyan-100 shadow-[0_0_18px_rgba(34,211,238,0.18)]">
                <CloudUpload size={28} />
              </div>
              <h3 className="mt-5 text-2xl font-semibold text-white">{t('upload.dropZone')}</h3>
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  inputRef.current?.click();
                }}
                className="mt-5 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-base font-medium text-cyan-100"
              >
                {t('upload.chooseImage')}
              </button>
            </>
          )}
        </div>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
          <div className="rounded-[1.5rem] border border-white/8 bg-white/5 p-5">
            <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-cyan-300/65">
              {t('upload.conversionStatus')}
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <StatusChip label={t('upload.uploadStatus')} value={conversionState.uploadStatus} />
              <StatusChip label={t('upload.aiIdentify')} value={conversionState.aiStatus} />
              <StatusChip label={t('upload.cardStatus')} value={conversionState.cardStatus} />
              <StatusChip label={t('upload.mintStatus')} value={conversionState.mintStatus} />
            </div>
            <div className="mt-4 text-base text-slate-300/75">
              <p>{t('upload.collectionId')}: {conversionState.collectionId ?? '—'}</p>
              <p className="mt-1 break-all">{t('upload.file')}: {conversionState.uploadedFileName ?? '—'}</p>
              <p className="mt-1 break-all">{t('upload.tokenUri')}: {conversionState.tokenUri ?? '—'}</p>
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-white/8 bg-white/5 p-5">
            <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-cyan-300/65">
              {t('upload.guidedActions')}
            </p>
            <div className="mt-4 flex flex-col gap-3">
              <button
                type="button"
                disabled={!isReadyForOneClick}
                onClick={() => conversionState.collectionId && void onOneClickConvert(conversionState.collectionId)}
                className={[
                  'flex items-center justify-center gap-2 rounded-2xl border px-4 py-3 text-base font-medium transition',
                  isReadyForOneClick
                    ? 'border-fuchsia-300/20 bg-fuchsia-300/10 text-fuchsia-100 hover:-translate-y-0.5'
                    : 'cursor-not-allowed border-white/8 bg-white/5 text-slate-500',
                ].join(' ')}
              >
                <Sparkles size={16} />
                {t('upload.oneClickConvert')}
              </button>

              <button
                type="button"
                disabled={!canGoBack}
                onClick={() => {
                  if (guidedStage === 'review') onGuidedStageChange('upload');
                  if (guidedStage === 'card') onGuidedStageChange('review');
                  if (guidedStage === 'mint') onGuidedStageChange('card');
                }}
                className={[
                  'flex items-center justify-center gap-2 rounded-2xl border px-4 py-3 text-base font-medium transition',
                  canGoBack
                    ? 'border-white/10 bg-white/5 text-slate-200 hover:border-cyan-300/20 hover:text-white'
                    : 'cursor-not-allowed border-white/8 bg-white/5 text-slate-500',
                ].join(' ')}
              >
                <CornerLeftUp size={16} />
                {t('common.back')}
              </button>

              <button
                type="button"
                disabled={
                  (guidedStage === 'upload' && !canContinueToReview) ||
                  (guidedStage === 'review' && !canContinueToCard) ||
                  (guidedStage === 'card' && !canContinueToMint) ||
                  guidedStage === 'mint'
                }
                onClick={() => {
                  if (guidedStage === 'upload' && canContinueToReview) onGuidedStageChange('review');
                  if (guidedStage === 'review' && canContinueToCard) onGuidedStageChange('card');
                  if (guidedStage === 'card' && canContinueToMint) onGuidedStageChange('mint');
                }}
                className={[
                  'flex items-center justify-center gap-2 rounded-2xl border px-4 py-3 text-base font-medium transition',
                  ((guidedStage === 'upload' && canContinueToReview) ||
                    (guidedStage === 'review' && canContinueToCard) ||
                    (guidedStage === 'card' && canContinueToMint))
                    ? 'border-cyan-300/20 bg-cyan-300/10 text-cyan-100 hover:-translate-y-0.5'
                    : 'cursor-not-allowed border-white/8 bg-white/5 text-slate-500',
                ].join(' ')}
              >
                <CheckCircle2 size={16} />
                {guidedStage === 'upload'
                  ? t('upload.goToReview')
                  : guidedStage === 'review'
                    ? t('upload.goToCard')
                    : guidedStage === 'card'
                      ? t('upload.goToMint')
                      : t('upload.completed')}
              </button>
            </div>
          </div>
        </div>

        {notice ? (
          <div
            className={[
              'rounded-2xl border px-4 py-3 text-base',
              notice.tone === 'success'
                ? 'border-emerald-300/20 bg-emerald-300/8 text-emerald-100'
                : notice.tone === 'error'
                  ? 'border-rose-300/20 bg-rose-300/8 text-rose-100'
                  : 'border-cyan-300/20 bg-cyan-300/8 text-cyan-100',
            ].join(' ')}
          >
            {notice.message}
          </div>
        ) : null}
      </InventorySectionFrame>

      <InventorySectionFrame title={t('upload.currentFocus')}>
        <div className="rounded-[1.35rem] border border-cyan-400/12 bg-[#08131f]/75 p-4">
          <p className="text-xl font-medium text-white">{selectedItem?.name ?? '—'}</p>
          <p className="mt-1 text-base text-slate-300/70">{selectedItem?.displayCode ?? '—'}</p>
        </div>
      </InventorySectionFrame>
    </div>
  );
}

function StatusChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1.1rem] border border-white/8 bg-[#071523]/70 p-3">
      <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-cyan-300/60">{label}</p>
      <p className="mt-2 text-base font-medium text-white capitalize">{value.replace(/_/g, ' ')}</p>
    </div>
  );
}
