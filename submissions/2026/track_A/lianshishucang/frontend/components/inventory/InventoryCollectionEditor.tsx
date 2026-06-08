import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import InventorySectionFrame from './InventorySectionFrame';
import type { InventoryActionNotice, InventoryItemViewModel } from '../../types/inventory';

interface InventoryCollectionEditorProps {
  selectedItem?: InventoryItemViewModel;
  notice?: InventoryActionNotice | null;
  onSubmit: (payload: {
    attributes: {
      ip_name: string;
      series: string;
      material: string;
      dominant_colors: string[];
      condition: string;
      style_tags: string[];
    };
    physical_location: string;
  }) => Promise<void>;
  onBack: () => void;
  onContinue: () => void;
  submitting: boolean;
}

interface EditorFormState {
  ipName: string;
  series: string;
  material: string;
  dominantColors: string;
  condition: string;
  styleTags: string;
  physicalLocation: string;
}

export default function InventoryCollectionEditor({
  selectedItem,
  notice,
  onSubmit,
  onBack,
  onContinue,
  submitting,
}: InventoryCollectionEditorProps) {
  const { t } = useTranslation();
  const [form, setForm] = useState<EditorFormState>({
    ipName: '',
    series: '',
    material: '',
    dominantColors: '',
    condition: '',
    styleTags: '',
    physicalLocation: '',
  });

  useEffect(() => {
    if (!selectedItem) {
      return;
    }

    const findAttribute = (name: string) =>
      selectedItem.attributes.find((attribute) => attribute.trait_type.toLowerCase() === name.toLowerCase())
        ?.value;

    setForm({
      ipName: String(findAttribute('Ip Name') ?? ''),
      series: String(findAttribute('Series') ?? ''),
      material: String(findAttribute('Material') ?? ''),
      dominantColors: String(findAttribute('Dominant Colors') ?? ''),
      condition: String(findAttribute('Condition') ?? ''),
      styleTags: String(findAttribute('Style Tags') ?? ''),
      physicalLocation: selectedItem.physicalLocation ?? '',
    });
  }, [selectedItem]);

  return (
    <InventorySectionFrame title={t('collectionEditor.title')} contentClassName="space-y-5">
      <div className="grid gap-4 md:grid-cols-2">
        <Field label={t('collectionEditor.ipName')} value={form.ipName} onChange={(value) => setForm((current) => ({ ...current, ipName: value }))} />
        <Field label={t('collectionEditor.series')} value={form.series} onChange={(value) => setForm((current) => ({ ...current, series: value }))} />
        <Field label={t('collectionEditor.material')} value={form.material} onChange={(value) => setForm((current) => ({ ...current, material: value }))} />
        <Field label={t('collectionEditor.condition')} value={form.condition} onChange={(value) => setForm((current) => ({ ...current, condition: value }))} />
        <Field label={t('collectionEditor.dominantColors')} value={form.dominantColors} onChange={(value) => setForm((current) => ({ ...current, dominantColors: value }))} />
        <Field label={t('collectionEditor.styleTags')} value={form.styleTags} onChange={(value) => setForm((current) => ({ ...current, styleTags: value }))} />
      </div>

      <Field
        label={t('collectionEditor.physicalLocation')}
        value={form.physicalLocation}
        onChange={(value) => setForm((current) => ({ ...current, physicalLocation: value }))}
      />

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={onBack}
          className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-base font-medium text-slate-200 transition hover:border-cyan-300/20 hover:text-white"
        >
          {t('common.back')}
        </button>
        <button
          type="button"
          onClick={() =>
            void onSubmit({
              attributes: {
                ip_name: form.ipName.trim(),
                series: form.series.trim(),
                material: form.material.trim(),
                dominant_colors: form.dominantColors
                  .split(',')
                  .map((value) => value.trim())
                  .filter(Boolean),
                condition: form.condition.trim(),
                style_tags: form.styleTags
                  .split(',')
                  .map((value) => value.trim())
                  .filter(Boolean),
              },
              physical_location: form.physicalLocation.trim(),
            })
          }
          disabled={submitting}
          className={[
            'rounded-2xl border px-4 py-3 text-base font-medium transition',
            submitting
              ? 'cursor-not-allowed border-white/8 bg-white/5 text-slate-500'
              : 'border-cyan-300/20 bg-cyan-300/10 text-cyan-100 hover:-translate-y-0.5',
          ].join(' ')}
        >
          {submitting ? t('collectionEditor.saving') : t('collectionEditor.saveMetadata')}
        </button>
        <button
          type="button"
          onClick={onContinue}
          className="rounded-2xl border border-fuchsia-300/20 bg-fuchsia-300/10 px-4 py-3 text-base font-medium text-fuchsia-100 transition hover:-translate-y-0.5"
        >
          {t('common.continue')}
        </button>
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
  );
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="mb-2 block font-mono text-[11px] uppercase tracking-[0.24em] text-cyan-300/65">
        {label}
      </span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-2xl border border-cyan-400/15 bg-[#071523]/80 px-4 py-3 text-base text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/45 focus:shadow-[0_0_0_1px_rgba(103,232,249,0.2)]"
      />
    </label>
  );
}
