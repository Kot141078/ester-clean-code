import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.ESTER_BASE_URL || 'http://127.0.0.1:5000';
const JWT = __ENV.ESTER_JWT || '';
const DURATION = __ENV.K6_DURATION || '2m';
const VUS = parseInt(__ENV.K6_VUS || '20', 10);
const RATE = parseInt(__ENV.K6_RPS || '10', 10);

export const options = {
  scenarios: {
    perftest: {
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
    http_req_duration: ['p(95)<2000','p(99)<5000'],
  },
};

const headers = Object.assign({ 'Content-Type': 'application/json' }, JWT ? { Authorization: `Bearer ${JWT}` } : {});
function randId(){ return Math.random().toString(36).slice(2); }

export default function () {
  const ev = { kind: 'perf.test', payload: { id: randId(), t: Date.now(), note: 'k6' } };
  let res = http.post(`${BASE}/events/publish`, JSON.stringify(ev), { headers });
  check(res, { 'publish ok': r => [200,201,202].includes(r.status) });

  const r2 = http.post(`${BASE}/replication/push`, JSON.stringify({ items:[ev] }), { headers });
  check(r2, { 'replicate ok or not found': r => [200,201,202,404].includes(r.status) });

  const r3 = http.post(`${BASE}/ops/backup/verify`, JSON.stringify({ quick:true }), { headers });
  check(r3, { 'verify ok or unauthorized': r => [200,401,403].includes(r.status) });

  sleep(0.3);
}
