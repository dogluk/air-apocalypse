"""Abridged period life table over the 19 bands of ages.AGE_STARTS.

Standard method: q = n·m / (1 + (n − a)·m), l from q with radix 1.0,
L = n·l(next) + a·d, the open band closed with L = l / m, e = T / l.

a (the average years lived in the band by those who die in it) is half the band
width, except in infancy, where the SRS's own convention is used:
a0 = 0.0425 + 2.875·q0. That rule is not printed in the SRS report (which says only
that MORTPAK 4 was used); it is recovered from the tables themselves. For all 23
SRS 2020-24 tables, a0 = (L0 − l1) / d0 computed from the printed columns fits
0.0425 + 2.875·q0 within 0.0005, which is the printed rounding (fit over
q0 = 0.007 to 0.041; least squares gives 0.0425 + 2.874·q0).
"""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq

from .ages import ADULT_FROM, AGE_STARTS

STARTS = np.array(AGE_STARTS, dtype=float)
WIDTHS = np.append(np.diff(STARTS), np.inf)


@dataclass(frozen=True)
class LifeTable:
    mx: np.ndarray
    qx: np.ndarray
    lx: np.ndarray
    Lx: np.ndarray
    ex: np.ndarray


def _infant_a0(m0: float | np.ndarray) -> float | np.ndarray:
    """Solve a0 = 0.0425 + 2.875·q0 with q0 = m0 / (1 + (1 − a0)·m0)."""
    a0 = 0.1
    for _ in range(20):
        q0 = m0 / (1 + (1 - a0) * m0)
        a0 = 0.0425 + 2.875 * q0
    return a0


def _columns(mx: np.ndarray) -> tuple[np.ndarray, ...]:
    """qx, lx, Lx, ex for rates of shape (..., bands): one table per row of the last axis."""
    if mx.shape[-1:] != STARTS.shape:
        raise ValueError(f"mx must have {len(STARTS)} bands, got shape {mx.shape}")
    if (mx <= 0).any():
        raise ValueError("death rates must be positive")
    n = WIDTHS[:-1]
    a = np.broadcast_to(n / 2, mx[..., :-1].shape).copy()
    a[..., 0] = _infant_a0(mx[..., 0])
    m = mx[..., :-1]
    q = np.minimum(n * m / (1 + (n - a) * m), 1.0)
    ones = np.ones(mx.shape[:-1] + (1,))
    qx = np.concatenate([q, ones], axis=-1)
    lx = np.concatenate([ones, np.cumprod(1 - q, axis=-1)], axis=-1)
    d = lx[..., :-1] - lx[..., 1:]
    Lx = np.concatenate([n * lx[..., 1:] + a * d, lx[..., -1:] / mx[..., -1:]], axis=-1)
    Tx = np.flip(np.cumsum(np.flip(Lx, -1), axis=-1), -1)
    with np.errstate(divide="ignore", invalid="ignore"):
        ex = np.where(lx > 0, Tx / lx, 0.0)
    return qx, lx, Lx, ex


def life_table(mx: np.ndarray) -> LifeTable:
    mx = np.asarray(mx, dtype=float)
    if mx.shape != STARTS.shape:
        raise ValueError(f"mx must have {len(STARTS)} bands, got shape {mx.shape}")
    qx, lx, Lx, ex = _columns(mx)
    return LifeTable(mx=mx, qx=qx, lx=lx, Lx=Lx, ex=ex)


def e0(mx: np.ndarray) -> float:
    return float(life_table(mx).ex[0])


def e0_many(mx: np.ndarray) -> np.ndarray:
    """Life expectancy at birth for each row of rates of shape (n, bands)."""
    return _columns(np.asarray(mx, dtype=float))[3][..., 0]


def scale_adult(mx: np.ndarray, factor: float | np.ndarray,
                from_age: int = ADULT_FROM) -> np.ndarray:
    """Multiply the rates of bands starting at or above from_age by factor.

    factor is a scalar or an array matching the adult bands.
    """
    out = np.array(mx, dtype=float)
    adult = STARTS >= from_age
    out[adult] = out[adult] * factor
    return out


def solve_adult_factor(mx: np.ndarray, delta_e0: float,
                       from_age: int = ADULT_FROM) -> float:
    """The uniform multiplier on adult rates that changes e0 by delta_e0."""
    if delta_e0 == 0:
        return 1.0
    base = e0(mx)

    def gap(f: float) -> float:
        return e0(scale_adult(mx, f, from_age)) - base - delta_e0

    lo, hi = 1.0, 1.0
    if delta_e0 > 0:   # lower rates: search below 1
        while gap(lo) < 0:
            lo /= 2
            if lo < 1e-9:
                raise ValueError(f"no adult factor gains {delta_e0} years")
    else:              # higher rates: search above 1
        while gap(hi) > 0:
            hi *= 2
            if hi > 1e6:
                raise ValueError(f"no adult factor loses {-delta_e0} years")
    return brentq(gap, lo, hi, xtol=1e-10)
