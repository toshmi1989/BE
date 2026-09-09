"""Pure-Python helpers for Student t / non-central t (no scipy required).

Used by BE_TOST_2X2_NCT.v1 when scipy is unavailable.
Algorithm: continued-fraction incomplete beta for central t;
Owen (1965) / Lenth-style series for non-central t CDF.
"""

from __future__ import annotations

import math


def _betacf(a: float, b: float, x: float, max_iter: int = 200, eps: float = 3e-14) -> float:
    """Continued fraction for incomplete beta (Numerical Recipes style)."""
    am = 1.0
    bm = 1.0
    az = 1.0
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    bz = 1.0 - qab * x / qap
    for m in range(1, max_iter + 1):
        em = float(m)
        tem = em + em
        d = em * (b - em) * x / ((qam + tem) * (a + tem))
        ap = az + d * am
        bp = bz + d * bm
        d = -(a + em) * (qab + em) * x / ((a + tem) * (qap + tem))
        app = ap + d * az
        bpp = bp + d * bz
        aold = az
        am = ap / bpp
        bm = bp / bpp
        az = app / bpp
        bz = 1.0
        if abs(az - aold) < eps * abs(az):
            return az
    return az


def _betai(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1.0 - x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def student_t_cdf(t: float, df: float) -> float:
    """P(T <= t) for central Student t with `df` degrees of freedom."""
    if df <= 0:
        raise ValueError("df must be > 0")
    x = df / (df + t * t)
    ib = 0.5 * _betai(0.5 * df, 0.5, x)
    if t >= 0:
        return 1.0 - ib
    return ib


def student_t_ppf(p: float, df: float) -> float:
    """Approximate inverse CDF via bisection (deterministic)."""
    if not (0.0 < p < 1.0):
        raise ValueError("p must be in (0,1)")
    if abs(p - 0.5) < 1e-15:
        return 0.0
    # Wide bracket
    lo, hi = -1e6, 1e6
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if student_t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def nct_cdf(t: float, df: float, ncp: float) -> float:
    """Non-central t CDF F(t; df, ncp).

    Series expansion (Lenth 1989 / Johnson & Kotz style):
    mix Poisson weights on noncentrality with central t / beta terms.
    """
    if df <= 0:
        raise ValueError("df must be > 0")
    # For extreme ncp, clamp numerically
    if ncp > 100:
        ncp = 100.0
    if ncp < -100:
        ncp = -100.0

    # Use recursive algorithm: P(T<=t) = sum_{j=0}^∞ p_j * I_{x}(j+0.5, df/2)  (t>0)
    # with p_j Poisson(λ=ncp²/2) mixed odd/even — implement via iterative terms.
    # Simpler robust approach: integrate density numerically with Gauss-Hermite-like
    # discretization of normal latent variable: T = (Z+ncp)/sqrt(V/df), V~chi2(df)
    # Approximate via quadrature over chi2 using gamma points.
    return _nct_cdf_quad(t, df, ncp)


def _nct_cdf_quad(t: float, df: float, ncp: float, n_points: int = 64) -> float:
    """Gauss-Laguerre style quadrature on chi-square latent for non-central t CDF."""
    # V ~ chi2(df) = Gamma(df/2, 2). Use Gauss-Laguerre on y = V/2 → Gamma(df/2,1)
    # nodes from simple Gauss-Laguerre for large alpha via quantile grid.
    alpha = df / 2.0
    # Quantile grid of Gamma(alpha,1)
    probs = [(i + 0.5) / n_points for i in range(n_points)]
    nodes = [_gamma_ppf(p, alpha) for p in probs]
    weight = 1.0 / n_points
    acc = 0.0
    for y in nodes:
        # V = 2y; sqrt(V/df) = sqrt(2y/df)
        scale = math.sqrt(max(2.0 * y / df, 1e-18))
        # P( (Z+ncp)/scale <= t ) = P(Z <= t*scale - ncp)
        acc += weight * _norm_cdf(t * scale - ncp)
    return max(0.0, min(1.0, acc))


def _gamma_ppf(p: float, alpha: float) -> float:
    """Approximate Gamma(alpha,1) PPF via Wilson-Hilferty + Newton refinement."""
    if p <= 0:
        return 0.0
    if p >= 1:
        return 1e6
    # Wilson–Hilferty
    z = _norm_ppf(p)
    h = 2.0 / (9.0 * alpha)
    approx = alpha * (1.0 - h + z * math.sqrt(h)) ** 3
    if approx < 0:
        approx = alpha * math.exp(z * math.sqrt(1.0 / alpha) - 0.5 / alpha)
    # One Newton step on CDF
    for _ in range(8):
        c = _gamma_cdf(approx, alpha)
        dens = math.exp(-approx + (alpha - 1.0) * math.log(max(approx, 1e-18)) - math.lgamma(alpha))
        if dens <= 0:
            break
        approx -= (c - p) / dens
        if approx <= 0:
            approx = 1e-12
    return approx


def _norm_ppf(p: float) -> float:
    """Acklam rational approximation for normal PPF."""
    if p <= 0 or p >= 1:
        raise ValueError("p in (0,1)")
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577459334513e02,
        -3.066479806614736e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    ]
    plow = 0.02425
    phigh = 1 - plow
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    )


def _gamma_cdf(x: float, alpha: float) -> float:
    if x <= 0:
        return 0.0
    # Regularized lower gamma via incomplete gamma series / continued fraction
    return _gammainc_lower(alpha, x)


def _gammainc_lower(a: float, x: float) -> float:
    if x < a + 1.0:
        # series
        term = 1.0 / a
        s = term
        for n in range(1, 200):
            term *= x / (a + n)
            s += term
            if abs(term) < abs(s) * 1e-14:
                break
        return s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    # continued fraction for upper, then 1-upper
    b0 = x + 1.0 - a
    c = 1e30
    d = 1.0 / b0
    h = d
    for i in range(1, 200):
        an = -i * (i - a)
        b0 += 2.0
        d = an * d + b0
        if abs(d) < 1e-30:
            d = 1e-30
        c = b0 + an / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-14:
            break
    upper = math.exp(-x + a * math.log(x) - math.lgamma(a)) * h
    return max(0.0, min(1.0, 1.0 - upper))


def nct_sf(t: float, df: float, ncp: float) -> float:
    """Survival function 1 - CDF."""
    return max(0.0, min(1.0, 1.0 - nct_cdf(t, df, ncp)))
