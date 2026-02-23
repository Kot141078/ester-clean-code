import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.ESTER_BASE_URL || 'http://127.0.0.1:5000';
const JWT = __ENV.ESTER_JWT || '';
const DURATION = __ENV.K6_DURATION || '2m';
const VUS = parseInt(__ENV.K6_VUS || '20', 10);
const RATE = parseInt(__ENV.K6_RPS || '10', 10);

export const options = {
  scenarios: {
    longops: {
      executor: 'constant-arrival-rate',
      rate: RATE,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: VUS,
      maxVUs: Math.max(VUS * 2, 50),
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<2000', 'p(99)<5000'],
  },
};

const headersJson = Object.assign({ 'Content-Type': 'application/json' }, JWT ? { Authorization: `Bearer ${JWT}` } : {});
const headersForm = Object.assign({}, JWT ? { Authorization: `Bearer ${JWT}` } : {});

function randId() { return Math.random().toString(36).slice(2); }
function bigText(bytes) {
  const base = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. ';
  let s = '';
  while (s.length < bytes) s += base;
  return s.slice(0, bytes);
}

export default function () {
  const payloadText = JSON.stringify({ id: randId(), text: bigText(128 * 1024), meta: { source: 'k6', t: Date.now() } });
  const endpointsIngest = [`${BASE}/ingest/text`, `${BASE}/ingest/doc`, `${BASE}/ingest`];
  const urlIngest = endpointsIngest[Math.floor(Math.random() * endpointsIngest.length)];
  const rIngest = http.post(urlIngest, payloadText, { headers: headersJson });
  check(rIngest, { 'ingest ok/known': r => [200,201,202,204,400,404].includes(r.status) });

  const q = { query: 'Obyasni osnovnye fakty iz dokumenta i verni spisok ssylok.', top_k: 5, mmr_lambda: 0.5, debug: false };
  const endpointsRag = [`${BASE}/rag/query`, `${BASE}/rag/search`, `${BASE}/mem/rag/query`];
  const urlRag = endpointsRag[Math.floor(Math.random() * endpointsRag.length)];
  const rRag = http.post(urlRag, JSON.stringify(q), { headers: headersJson });
  check(rRag, { 'rag ok/known': r => [200,201,202,204,400,404].includes(r.status) });

  const ev = { kind: 'perf.long', payload: { id: randId(), blob: bigText(64 * 1024), t: Date.now() } };
  const rEv = http.post(`${BASE}/events/publish`, JSON.stringify(ev), { headers: headersJson });
  check(rEv, { 'event ok': r => [200,201,202].includes(r.status) });

  const bin = bigText(64 * 1024);
  const formData = { meta: JSON.stringify({ id: randId(), note: 'k6-multipart' }), file: http.file(bin, `sample_${Date.now()}.txt`, 'text/plain') };
  const endpointsUpload = [`${BASE}/ingest/upload`, `${BASE}/upload`];
  const urlUp = endpointsUpload[Math.floor(Math.random() * endpointsUpload.length)];
  const rUp = http.post(urlUp, formData, { headers: headersForm });
  check(rUp, { 'upload ok/known': r => [200,201,202,400,404].includes(r.status) });

  sleep(0.5);
}
