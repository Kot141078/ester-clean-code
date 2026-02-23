import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.ESTER_BASE_URL || 'http://127.0.0.1:5000';
const JWT = __ENV.ESTER_JWT || '';
const DURATION = __ENV.K6_DURATION || '2m';
const VUS = parseInt(__ENV.K6_VUS || '10', 10);
const RATE = parseInt(__ENV.K6_RPS || '5', 10);
const RUN_RATIO = parseFloat(__ENV.OPS_RUN_RATIO || '0.05');

export const options = {
  scenarios: {
    ops: {
      executor: 'constant-arrival-rate',
      rate: RATE,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: VUS,
      maxVUs: Math.max(VUS * 2, 30),
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<2000','p(99)<5000'],
  },
};

const headers = Object.assign({ 'Content-Type': 'application/json' }, JWT ? { Authorization: `Bearer ${JWT}` } : {});

export default function () {
  // verify chasche, run inogda
  const doRun = Math.random() < RUN_RATIO;
  if (doRun) {
    const r = http.post(`${BASE}/ops/backup/run`, JSON.stringify({}), { headers });
    check(r, { 'backup.run ok': resp => [200,201,202].includes(resp.status) });
  } else {
    const r = http.post(`${BASE}/ops/backup/verify`, JSON.stringify({ quick: true }), { headers });
    check(r, { 'backup.verify ok/unauth': resp => [200,401,403].includes(resp.status) });
  }
  sleep(0.2);
}
