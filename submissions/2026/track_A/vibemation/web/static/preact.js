// ── Preact + HTM + Marked 统一入口 ────────────────
import { h } from 'https://esm.sh/preact@10.26.4';
import htm from 'https://esm.sh/htm@3.1.1';
export { h, render, Component } from 'https://esm.sh/preact@10.26.4';
export { useState, useEffect, useCallback, useRef } from 'https://esm.sh/preact@10.26.4/hooks';
export const html = htm.bind(h);
export { marked } from 'https://cdn.jsdelivr.net/npm/marked/lib/marked.esm.js';
