import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.ESTER_BASE_URL || 'http://127.0.0.1:5000';
const JWT = __ENV.ESTER_JWT || '';
const DURATION = __ENV.K6_DURATION || '2m';
const VUS = parseInt(__ENV.K6_VUS || '10', 10);
const RATE = parseInt(__ENV.K6_RPS || '5', 10);

export const options = {
  scenarios: {
    ragHeavy: {
      executor: 'constant-arrival-rate',
      rate: RATE,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: VUS,
      maxVUs: Math.max(VUS * 2, 50),
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.02'],
    http_req_duration: ['p(95)<4000', 'p(99)<8000'],
  },
};

const headers = Object.assign({ 'Content-Type': 'application/json' }, JWT ? { Authorization: `Bearer ${JWT}` } : {});

function longQuery() {
  const base = "Sformiruy razvernutyy otvet s perechisleniem klyuchevykh faktov, tsitat i istochnikov; verni itogovyy spisok ssylok i kratkuyu vyzhimku v 3-5 punktakh. ";
  let s = base;
  while (s.length < 2048) s += base;
  return s.slice(0, 2048);
}

export default function () {
  const body = { query: longQuery(), top_k: 20, mmr_lambda: 0.3, debug: true };
  const endpoints = [`${BASE}/rag/query`, `${BASE}/rag/search`, `${BASE}/mem/rag/query`];
  const url = endpoints[Math.floor(Math.random() * endpoints.length)];
  const res = http.post(url, JSON.stringify(body), { headers });
  check(res, { 'rag-heavy ok/known': r => [200,201,202,204,400,404].includes(r.status) });
  sleep(0.5);
}
