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
    http_req_duration: ['p(95)<2000', 'p(99)<5000'],
  },
};

const headers = JWT ? { Authorization: `Bearer ${JWT}` } : {};
const endpoints = ['/providers/status','/routes','/health','/mem/kg/neighbors?limit=5&k=3'];

export default function () {
  const url = BASE + endpoints[Math.floor(Math.random() * endpoints.length)];
  const res = http.get(url, { headers });
  check(res, { 'status is ok/known': r => [200,201,202,204,404].includes(r.status) });
  sleep(0.2);
}
