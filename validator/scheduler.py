# -*- coding: utf-8 -*-
import numpy as np
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def compute_delta(p_alarm, B_gc, J_os, epsilon, margin=0.2):
    effective_shift = B_gc + J_os
    delta = (p_alarm * effective_shift) / (2 * epsilon)
    delta = delta * (1 + margin)
    return delta


def theoretical_tv(p_alarm, B_gc, delta):
    if B_gc > 2 * delta:
        return 1.0
    return (p_alarm * B_gc) / (2 * delta)


def simulate_tv(p_alarm, B_gc, delta, n_samples=100000, bins=1000):
    p_int = []
    p_no = []
    for _ in range(n_samples):
        no = np.random.uniform(-delta, delta)
        p_no.append(no)
        if np.random.rand() < p_alarm:
            int_sample = np.random.uniform(-delta + B_gc, delta + B_gc)
        else:
            int_sample = np.random.uniform(-delta, delta)
        p_int.append(int_sample)
    lo = -delta - 0.001
    hi = delta + B_gc + 0.001
    bins_edges = np.linspace(lo, hi, bins)
    hist_no, _ = np.histogram(p_no, bins=bins_edges, density=True)
    hist_int, _ = np.histogram(p_int, bins=bins_edges, density=True)
    tv = 0.5 * np.sum(np.abs(hist_int - hist_no) * np.diff(bins_edges))
# return tv