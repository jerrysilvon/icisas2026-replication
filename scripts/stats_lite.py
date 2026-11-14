"""Minimal OLS with cluster-robust inference, in numpy only.

scipy/statsmodels cannot load on this machine (Application Control blocks the
compiled extensions), so the estimator and the two distribution functions the
tests need are implemented here.
"""
import math

import numpy as np


def _gamma_q(a, x):
    """Regularised upper incomplete gamma Q(a,x). Series below the crossover,
    continued fraction above (Numerical Recipes 6.2)."""
    if x < 0 or a <= 0:
        raise ValueError("domain")
    if x == 0:
        return 1.0
    gln = math.lgamma(a)
    if x < a + 1.0:
        ap, s, d = a, 1.0 / a, 1.0 / a
        for _ in range(1000):
            ap += 1
            d *= x / ap
            s += d
            if abs(d) < abs(s) * 1e-14:
                break
        return 1.0 - s * math.exp(-x + a * math.log(x) - gln)
    b, c = x + 1.0 - a, 1e300
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < 1e-300:
            d = 1e-300
        c = b + an / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        dl = d * c
        h *= dl
        if abs(dl - 1.0) < 1e-14:
            break
    return math.exp(-x + a * math.log(x) - gln) * h


def chi2_sf(x, df):
    """P(X > x) for chi-square with df degrees of freedom."""
    return _gamma_q(df / 2.0, x / 2.0)


def norm_sf2(z):
    """Two-sided normal tail probability."""
    return math.erfc(abs(z) / math.sqrt(2.0))


class OLS:
    """OLS with cluster-robust (CR1) covariance.

    With ~200 clusters the cluster-robust Wald statistics are treated as
    asymptotically normal / chi-square, which is the usual convention.
    """

    def __init__(self, y, X, groups, names):
        self.y = np.asarray(y, float)
        self.X = np.asarray(X, float)
        self.g = np.asarray(groups)
        self.names = list(names)
        n, k = self.X.shape
        XtX_inv = np.linalg.pinv(self.X.T @ self.X)
        self.beta = XtX_inv @ self.X.T @ self.y
        self.resid = self.y - self.X @ self.beta
        uniq = np.unique(self.g)
        meat = np.zeros((k, k))
        for gi in uniq:
            m = self.g == gi
            Xg, ug = self.X[m], self.resid[m]
            s = Xg.T @ ug
            meat += np.outer(s, s)
        G = len(uniq)
        c = (G / (G - 1.0)) * ((n - 1.0) / (n - k))
        self.vcov = c * (XtX_inv @ meat @ XtX_inv)
        self.se = np.sqrt(np.diag(self.vcov))
        self.n, self.k, self.G = n, k, G
        ss_res = float(self.resid @ self.resid)
        yc = self.y - self.y.mean()
        ss_tot = float(yc @ yc)
        # a demeaned outcome with no residual variation gives ss_tot == 0; report
        # R2 as nan rather than dividing by zero
        if ss_tot > 0:
            self.r2 = 1.0 - ss_res / ss_tot
            self.adj_r2 = 1.0 - (1.0 - self.r2) * (n - 1.0) / (n - k) if n > k else float("nan")
        else:
            self.r2 = self.adj_r2 = float("nan")
        self.ss_res = ss_res

    def z(self):
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(self.se > 0, self.beta / np.where(self.se > 0, self.se, 1),
                            np.nan)

    def p(self):
        return np.array([norm_sf2(v) if np.isfinite(v) else float("nan")
                         for v in self.z()])

    def wald(self, idx):
        """Joint cluster-robust Wald test that the named coefficients are zero."""
        idx = [self.names.index(i) if isinstance(i, str) else i for i in idx]
        R = np.zeros((len(idx), self.k))
        for r, c in enumerate(idx):
            R[r, c] = 1.0
        Rb = R @ self.beta
        mid = np.linalg.pinv(R @ self.vcov @ R.T)
        stat = float(Rb @ mid @ Rb)
        return stat, chi2_sf(stat, len(idx))

    def summary_rows(self):
        p = self.p()
        return [dict(name=self.names[i], coef=float(self.beta[i]), se=float(self.se[i]),
                     z=float(self.z()[i]), p=float(p[i])) for i in range(self.k)]
