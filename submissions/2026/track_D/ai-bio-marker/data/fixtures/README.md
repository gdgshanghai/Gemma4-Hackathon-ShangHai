# Synthetic data fixtures — placeholder.
#
# Purpose: enable full local end-to-end testing without physical BCI hardware.
#
# Expected fixtures:
#   - eeg_8ch_250hz_clean.csv       — Clean 8-channel EEG at 250 Hz
#   - eeg_8ch_250hz_noisy.csv       — Noisy EEG with ocular/muscular artifacts
#   - hrv_eda_synthetic.json        — Synthetic HRV/EDA streams
#   - feature_bundle_expected.json  — Expected output after preprocessing + codec
#
# All data is synthetic — no real patient data should ever be stored here.
