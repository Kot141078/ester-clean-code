# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def entropy_corrected(counts, base=2):
    counts = np.asarray(counts, dtype=float)
    total_count = np.sum(counts)
    if total_count <= 0:
        return 0.0
    probs = counts[counts > 0] / total_count
    h_plugin = -np.sum(probs * np.log(probs) / np.log(base))
    k_eff = len(probs)
    bias_correction = (k_eff - 1) / (2 * total_count * np.log(base))
    return h_plugin + bias_correction


def mi_corrected(x, y, base=2):
    joint = pd.crosstab(pd.Series(x, name="x"), pd.Series(y, name="y"))
    joint_counts = joint.values
    x_counts = joint_counts.sum(axis=1)
    y_counts = joint_counts.sum(axis=0)
    h_x = entropy_corrected(x_counts, base)
    h_y = entropy_corrected(y_counts, base)
    h_xy = entropy_corrected(joint_counts.flatten(), base)
    mi = h_x + h_y - h_xy
    return max(mi, 0.0)


def syndep_corrected(a, b, c, base=2):
    df = pd.DataFrame({"A": a, "B": b, "C": c})
    h_a = entropy_corrected(df["A"].value_counts().values, base)
    h_b = entropy_corrected(df["B"].value_counts().values, base)
    h_c = entropy_corrected(df["C"].value_counts().values, base)
    h_ab = entropy_corrected(pd.crosstab(df["A"], df["B"]).values.flatten(), base)
    h_ac = entropy_corrected(pd.crosstab(df["A"], df["C"]).values.flatten(), base)
    h_bc = entropy_corrected(pd.crosstab(df["B"], df["C"]).values.flatten(), base)
    h_abc = entropy_corrected(df.groupby(["A", "B", "C"]).size().values, base)
    i_ab_c = h_ab + h_c - h_abc
    i_a_c_b = h_ab + h_bc - h_abc - h_b
    i_b_c_a = h_ab + h_ac - h_abc - h_a
    syndep = i_ab_c - i_a_c_b - i_b_c_a
# return syndep, i_ab_c, i_a_c_b, i_b_c_a