# JSL BioMedical

> A non-invasive brain–computer interface (BCI) and AI-BioMarker–driven system for early screening and closed-loop physical intervention of neuro-immune disorders

**Competition track:** Brain-Inspired Intelligence Special Track · Gemma Competition
**Project stage:** R&D + Incubation
**Vision:** Make early screening and closed-loop physical intervention for neuro-immune disorders as simple as taking a blood-pressure reading.

---

## Table of Contents

- [1. Market Pain Points](#1-market-pain-points)
- [2. Core Positioning](#2-core-positioning)
- [3. System Architecture](#3-system-architecture-edgedevice-cloud-three-tier-closed-loop)
- [4. Core Technologies](#4-core-technologies)
- [5. Differentiated Advantages](#5-differentiated-advantages)
- [6. Ecosystem Synergy](#6-ecosystem-synergy)
- [7. Achievements to Date](#7-achievements-to-date)
- [8. Business Model](#8-business-model)
- [9. Go-to-Market Strategy](#9-go-to-market-strategy)
- [10. Team & Financing](#10-team--financing)

---

## 1. Market Pain Points

The burden of neuro-immune disorders is enormous, yet traditional solutions leave three major gaps.

**Disease burden**

| Disease | Status quo |
| --- | --- |
| Depression | ~95 million patients in China; detection rate below 20%; low intervention adherence |
| Chronic fatigue syndrome / brain fog | Lacks objective biomarkers; high misdiagnosis rate |
| Early-stage Alzheimer's | Optimal intervention window is often missed by the time of diagnosis |
| Autoimmune-related encephalopathy | The neuro-immune intersection has long been overlooked |

**Three major gaps**

- **Cost gap:** Traditional BCI devices cost tens of thousands to hundreds of thousands of yuan, putting them out of reach for homes and communities.
- **Home-use gap:** Wet electrodes require professional operation, hurting patient adherence.
- **Closed-loop gap:** Existing solutions only screen — they offer no closed-loop physical intervention and rely heavily on medication.

> JSL's positioning: close these three gaps and bring neuro-immune early screening and physical intervention into the home.

---

## 2. Core Positioning

Non-invasive BCI + AI brings early screening and closed-loop intervention into the home. The system spans three layers — sensing, analysis, and intervention:

| Layer | Module | Key capabilities |
| --- | --- | --- |
| Sensing | 8-channel dry-electrode BCI headset | Wearable, dry-electrode, gel-free; captures EEG / HRV / EDA multimodal signals; weight < 50 g, 250 Hz high-fidelity sampling |
| Analysis | AI-BioMarker engine | HTSF-Attention time–frequency–space three-domain feature extraction; cross-modal contrastive learning to predict immune state |
| Analysis | Key metrics | Depression screening AUC = 0.93; IL-6 prediction r = 0.78 |
| Intervention | Reinforcement-learning closed-loop decision | DQN auto-recommends individualized stimulation parameters (tDCS / tACS / vagus-nerve stimulation / neurofeedback); current density auto-capped for controllable safety |

> A full sensing → analysis → intervention closed loop with millisecond-level response.

---

## 3. System Architecture: Device–Edge–Cloud Three-Tier Closed Loop

```
Device                 Edge                       Cloud
8-ch dry-electrode  →  ARM Cortex-M55 + NPU   →  JSL-Gemma LLM + AI-BioMarker
headset                Real-time denoise /        Multimodal fusion analysis
Captures EEG/HRV/EDA   preprocessing              Risk score 0–100
Integrated tDCS/tACS   ICA artifact removal        Individualized intervention plan
                       Band-power computation
                       Compressed-feature upload
                       (compression ratio ≈80%)
        ↑                                                       │
        └──────────── closed-loop intervention command ←────────┘
```

- **Device side:** 8-channel dry-electrode BCI headset captures EEG / HRV / EDA multimodal signals, with integrated tDCS / tACS stimulation modules.
- **Edge side:** ARM Cortex-M55 + NPU edge AI performs real-time denoising, ICA artifact removal, band-power computation, and feature compression (~80% ratio).
- **Cloud side:** JSL-Gemma LLM + AI-BioMarker runs multimodal fusion analysis, generating a 0–100 risk score and recommending an individualized intervention plan.

> Sensing → analysis → intervention → re-sensing, in a millisecond-level closed loop.

---

## 4. Core Technologies

### Technology 1: HTSF-Attention Multi-Scale EEG Feature Network

Unified time–frequency–space three-domain modeling that breaks the accuracy ceiling of single frequency- or spatial-domain analysis.

- **Frequency branch:** Learnable STFT + residual CNN to extract δ / θ / α / β / γ band power and coupling features.
- **Spatial branch:** Graph convolutional network (GCN) to extract functional-connectivity features.
- **Temporal branch:** Transformer Encoder to extract slow-wave oscillations and microstate sequences.
- **Cross-modal attention fusion layer:** Outputs a 504-dimensional high-level feature vector.

**Performance metrics**

| Task | AUC |
| --- | --- |
| Depression screening | 0.93 |
| MCI screening | 0.89 |
| IL-6 elevation detection | 0.91 |

### Technology 2: AI-BioMarker Virtual Immunomics

Quantitatively infers peripheral immune state from non-invasive EEG signals — a non-invasive bridge across the neuro-immune axis.

- **Dual-tower structure (cross-modal contrastive learning):**
  - Tower A: EEG features (the 504-dim vector from HTSF-Attention).
  - Tower B: Immune + multi-omics features (genomics / proteomics / clinical text, reduced via autoencoder).
  - Both towers are mapped into a shared embedding space through cross-modal contrastive learning.

**Validation results**

| Metric | Result |
| --- | --- |
| EEG prediction of serum IL-6 level | Correlation r = 0.78 (n = 240) |
| Immune-abnormality screening | AUC = 0.85 |

> Innovation: the world's first model to predict peripheral immune markers directly from EEG, enabling non-invasive virtual immunomics.

### Technology 3: Reinforcement-Learning Closed-Loop Intervention Engine

Adaptive, individualized stimulation that is safe and controllable — "a thousand plans for a thousand people," with privacy protection.

- **Algorithm:** DQN + federated learning; multi-center collaborative training with data never leaving its domain.
- **State space:** Risk score, abnormal-brain-region localization, historical adherence.
- **Action space:** tDCS (0.5–2 mA), tACS (1–40 Hz), vagus-nerve stimulation, neurofeedback difficulty adjustment.
- **Reward function:** Short-term — EEG slow-wave change; long-term — clinical-scale improvement.
- **Safety mechanism:** Auto-capping of current density / total charge, with a green safety-shield indicator.

---

## 5. Differentiated Advantages

| Dimension | Traditional solution | JSL |
| --- | --- | --- |
| Hardware | Wet electrodes / clinical-grade / no stimulation module | Dry electrodes / wearable / integrated closed-loop stimulation |
| Data fusion | Single EEG signal | EEG + peripheral + multi-omics + clinical text |
| Intervention | None or manual adjustment | AI auto-recommendation + physical closed-loop stimulation |
| Neuro-immune | No immune-prediction capability | First EEG-to-immune-marker prediction model |
| Cost | Tens to hundreds of thousands of yuan | Hardware < 2,000 yuan |
| Closed-loop capability | None | Full device–edge–cloud millisecond closed loop |

> Leading across all 6 dimensions, with hardware cost reduced by over 90%.

---

## 6. Ecosystem Synergy

Baidu AI Cloud + JSL build a neuro-immune digital-health closed loop — scaling from a single product to an ecosystem platform and amplifying social impact.

- **DAXIN Smart Health Kiosk:** Integrates 12 vital-sign tests (height / weight / temperature / blood pressure / blood oxygen / heart rate / blood glucose / uric acid / urinalysis / body composition / hemoglobin / lipid panel); 2nd-gen ID + fingerprint recognition with printed reports; Android OS + cloud health-management backend. **JSL BCI headset integration → extends into the brain-health dimension.**
- **LingYi Open Platform:** Medical knowledge management with a ten-million-scale integrated knowledge graph; trustworthy evidence-based Q&A (multi-source retrieval → transparent reasoning → evidence-backed answers). **JSL AI-BioMarker engine integration → strengthens neuro-immune knowledge reasoning.**
- **AI Doctor Assistant:** Authorized authoritative-knowledge-base Q&A. **JSL risk-score integration → supports clinical decision-making.**

**Alliance partners (Smart Elderly-Care Industry Alliance):** Shenji Tech, Caizhi Tech, Baidu AI Cloud, ZTE, Lenovo, Turing Zhixin, Evidence, TLand.

> Baidu AI Cloud ecosystem + JSL technology = full-chain health protection from clinic to doorstep.

---

## 7. Achievements to Date

**Clinical pilot trials**

| Project | Protocol | Result |
| --- | --- | --- |
| Depression intervention (n = 30) | 8 weeks of tDCS + neurofeedback | HAMD-17 score dropped 42%; adherence 85% |
| Insomnia intervention (n = 20) | Closed-loop tACS stimulation | PSQI improvement ≥ 3 points in 67% of cases |

**Competition honors**

- 3rd place, Shanghai Tianjiao Cup Biomedical & Medical-Device R&D Competition
- Selected for the Beijing Chaoyang AI Medical Proof-of-Concept program

**International data collaboration**

- Nucleon Research
- Adira Medica

> From proof-of-concept to clinical pilot, the technical pathway has been preliminarily validated.

---

## 8. Business Model

Four product lines + data services. A "three-horse carriage" of hardware + software + data, with a progressive revenue model.

| Product line | Pricing | Target customers / use |
| --- | --- | --- |
| Basic Screening Edition | 1,999 yuan/unit + subscription | Health-check centers / communities / homes; rapid brain-health screening reports |
| Professional Intervention Edition | 6,999 yuan/unit + software fee | Hospital psychiatry / rehabilitation depts.; closed-loop tDCS/tACS intervention plans |
| Research / Clinical Edition | Leasing 50k–200k yuan/set | Universities / pharma / CROs; multi-center research data platform |
| DaaS Data Services | 500k–3M yuan/data package | Pharma / investors; neuro-immune biomarker database |

**Revenue forecast**

| Period | Revenue target |
| --- | --- |
| Year 1 | 3 million yuan |
| Year 2 | Surpass 10 million yuan |
| Year 3 | Exceed 30 million yuan |

---

## 9. Go-to-Market Strategy

Based in Yuhang, Hangzhou, advancing through three competitions in parallel — one base, three competitions, accelerating from research to industrialization.

**Hangzhou landing plan**

| Phase | Key actions |
| --- | --- |
| Months 0–3 | Register subsidiary (Hangzhou AI Town); recruit hardware / algorithm engineers; submit prototypes for testing |
| Months 4–6 | Sign clinical research with Zhejiang University Yuhang campus; ≥ 50-case multi-center validation |
| Months 7–12 | Begin Class II medical-device registration; angel-round financing; host neuro-immune AI symposium |

**Three-competition layout**

- **Gemma Open-Source AI Competition (Jun 8, Google):** JSL-Gemma LLM + open-source ecosystem; AI-BioMarker engine open-source contribution.
- **Haiju Innovation Competition (June, Shanghai):** AI healthcare + Yangtze River Delta industry matchmaking; Baidu AI Cloud ecosystem co-demo.
- **Yongjiang Talent Competition (Ningbo, Zhejiang):** Talent landing + Ningbo medical-industry resources; Yuhang–Ningbo twin-city linkage.

**Policy support**

- Up to 5 million yuan in "Maker World" landing grants + Yuhang district matching funds + compute-voucher subsidies.

---

## 10. Team & Financing

A 6-person core team spanning brain science + AI + medical devices + data engineering, with strong complementarity (AI-AGI Lab).

| Role | Background |
| --- | --- |
| CEO | PhD, business (Paris, France) |
| CSO | PhD, Johns Hopkins |
| CTO | Data engineering |
| CPO | Information digitalization |
| CFO | MBA, SAIF (Shanghai Advanced Institute of Finance) |

**Financing plan: Angel round of 10 million yuan, for 10% equity**

| Use | Amount |
| --- | --- |
| Hardware tooling | 3 million yuan |
| Algorithm iteration | 2.5 million yuan |
| Team expansion | 3 million yuan |
| Medical-device registration | 1 million yuan |
| Marketing | 0.5 million yuan |

- Already invested: 5 million yuan, self-funded.

---

## Summary

**JSL — making early screening and closed-loop intervention for neuro-immune disorders as simple as taking a blood-pressure reading.**

- **Lower medical cost:** Hardware < 2,000 yuan; cost per report < 100 yuan.
- **Reach 95 million patients:** From the lab to homes and communities.
- **Advance brain-inspired intelligence:** AI-for-Science for Good · Aesthetic Medicine.

---

> Note: This README was compiled and transcribed from the project's pitch deck. OCR errors in the original PDF have been corrected (e.g., `EEf` → `EEG`, EEG bands `δ/θ/α/β/γ`, the dual-tower structure, etc.). All figures are sourced from the pitch materials; official documents take precedence.
