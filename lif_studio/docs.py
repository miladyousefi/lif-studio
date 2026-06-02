"""Embedded analysis documentation (single source of truth).

Kept as a string so it is always available — in the app's "Method & formulas"
dialog and when frozen with PyInstaller. ``docs/ANALYSIS.md`` is generated from
this constant.
"""

ANALYSIS_MD = r"""# LIF Studio — Analysis Methods & Formulas

This document describes every metric LIF Studio computes, the exact formula
used, the parameters that control it, and how to read the result. Analysis runs
on the **raw channel data** of each LIF series (full bit depth), not on the
colored TIFF exports.

Notation: a channel is an image of pixels $I_i$, $i = 1 \dots N$ (N = number of
pixels). $\bar I$ is the mean, $\sigma$ the standard deviation, $T$ a threshold.

---

## 1. Preprocessing

### 1.1 Z-stack projection
A series may contain a Z-stack. It is collapsed to one plane per channel:

- **Max** (default): $I(x,y) = \max_z S(x,y,z)$ — brightest value through the stack (what LAS X "Maximum Projection" does).
- **Mean**: $I(x,y) = \frac{1}{N_z}\sum_z S(x,y,z)$ — averages noise down, dims sparse signal.
- **First slice**: $I(x,y) = S(x,y,0)$.

*Guide:* use **Max** for punctate/sparse staining, **Mean** for diffuse signal where you want average intensity.

### 1.2 Background correction
Optional removal of a slowly-varying background $B$, then $I' = \max(I - B, 0)$.
Controlled by **Background method** and **Background size** ($s$):

- **None**: $B = 0$.
- **Gaussian**: $B = G_\sigma * I$ — convolution with a Gaussian of $\sigma = s$. Removes smooth, large-scale shading. Choose $\sigma$ much larger than your features.
- **Rolling-ball** (grey opening): $B = (I \ominus E) \oplus E$ — morphological opening with a structuring element of radius $s$. Classic for uneven illumination; $s$ should exceed the largest object you want to keep.
- **Median**: $B = \mathrm{median}_{s \times s}(I)$ — median filter of window $s$. Robust to bright outliers; slower for large $s$.

*Guide:* if the field has a glow/gradient, turn this on with $s$ ≈ 2–4× your object size. Verify by checking that % positive area drops to a sensible value and the histogram's low end collapses toward 0.

---

## 2. Thresholding

A threshold $T$ separates "signal" pixels ($I > T$) from background. It feeds
**% positive area**, **object counting**, and **Manders** colocalization.

- **Otsu** (default, automatic): chooses $T$ maximizing between-class variance.
  With histogram classes split at $t$, weights $\omega_0(t),\omega_1(t)$ and means $\mu_0(t),\mu_1(t)$:
  $$\sigma_b^2(t) = \omega_0(t)\,\omega_1(t)\,\big(\mu_0(t) - \mu_1(t)\big)^2,\qquad T = \arg\max_t \sigma_b^2(t).$$
- **Manual**: $T$ = the value you enter (absolute intensity).
- **Percentile**: $T = P_p(I)$, the $p$-th percentile of the pixel intensities.
- **Mean + k·std**: $T = \bar I + k\,\sigma$.

*Guide:* **Otsu** is a good default when there are clear bright objects. Use **Percentile** (e.g. 99) for very sparse puncta, **Mean+k·std** (k≈2–3) for low-contrast signal, **Manual** when you must hold the threshold constant across a batch for comparison.

---

## 3. Intensity statistics (per channel)

Computed over all pixels of the (preprocessed) channel:

| Metric | Formula |
|---|---|
| mean | $\bar I = \frac1N \sum_i I_i$ |
| median | middle value of sorted $I$ |
| std | $\sigma = \sqrt{\frac1N\sum_i (I_i-\bar I)^2}$ (population) |
| min / max | $\min_i I_i$, $\max_i I_i$ |
| integrated density | $\mathrm{ID} = \sum_i I_i$ |
| p95 | 95th percentile of $I$ |
| CV | $\sigma / \bar I$ (coefficient of variation) |
| skewness | $\gamma_1 = \frac{1}{N}\sum_i \big(\frac{I_i-\bar I}{\sigma}\big)^3$ |
| kurtosis (excess) | $\gamma_2 = \frac{1}{N}\sum_i \big(\frac{I_i-\bar I}{\sigma}\big)^4 - 3$ |

*Guide:* **Integrated density** ≈ total signal (good for "how much marker"). **CV** measures relative variability. **Skew/kurtosis** describe distribution shape: high positive skew + high kurtosis is typical of sparse bright puncta on a dark field.

---

## 4. Threshold & % positive area (per channel)

$$N_+ = \#\{ i : I_i > T \},\qquad \%\,\text{area} = \frac{N_+}{N}\times 100.$$

*Guide:* the fraction of the field occupied by signal. Compare only when the
threshold method (and any manual value) is identical across images.

---

## 5. Object / particle analysis (per channel)

On the binary mask $M = (I > T)$:

1. **Connected components** are labelled (pixels touching in 4/8-connectivity form one object).
2. **Size filter**: objects with area (pixel count) below **Min object size** are discarded.
3. Reported: **object count** = number of surviving components, and **mean object area** = average pixel count of those components.

*Guide:* set **Min object size** to reject single-pixel noise (e.g. 10–50 px).
Counts are sensitive to the threshold — keep it fixed across a comparison.

---

## 6. Colocalization (between channel A and channel B)

How much two channels overlap. Computed on the preprocessed channels; Manders
uses each channel's threshold $T_A, T_B$.

- **Pearson correlation coefficient** — linear co-variation, range $[-1, 1]$:
  $$r = \frac{\sum_i (A_i-\bar A)(B_i-\bar B)}{\sqrt{\sum_i (A_i-\bar A)^2}\,\sqrt{\sum_i (B_i-\bar B)^2}}.$$
- **Manders' coefficients** — fraction of one channel's signal coincident with the other's positive pixels, range $[0, 1]$:
  $$M_1 = \frac{\sum_i A_i\,[\,B_i > T_B\,]}{\sum_i A_i},\qquad
    M_2 = \frac{\sum_i B_i\,[\,A_i > T_A\,]}{\sum_i B_i}.$$
- **Overlap coefficient**:
  $$r_{ov} = \frac{\sum_i A_i B_i}{\sqrt{\sum_i A_i^2\,\sum_i B_i^2}}.$$

*Guide:* **Pearson** answers "do intensities rise and fall together" (sensitive to background; consider background correction first). **Manders M1/M2** answer "what fraction of A overlaps B, and vice-versa" and are usually the most interpretable for two markers. Set the colocalization **channel pair (A/B)** in the parameters.

References: Otsu (1979); Manders, Verbeek & Aten (1993); Pearson (1895).

---

## 7. Comparing types (groups)

Each image is assigned a **type** by the keyword rules in *Types & Colors*
(e.g. `AQP4`, `C5-9`). The **By type** tab counts images per type and, for the
selected metric, reports per group:

- **n** (count), **mean**, **std** (sample, $\mathrm{ddof}=1$),
- **SEM** $= \sigma / \sqrt{n}$, **median**.

Between the two groups it runs:

- **Welch's t-test** (unequal variances):
  $$t = \frac{\bar x_1 - \bar x_2}{\sqrt{s_1^2/n_1 + s_2^2/n_2}},$$
  with Welch–Satterthwaite degrees of freedom; reports $t$ and two-sided $p$.
- **Mann–Whitney U** (non-parametric rank test); reports $U$ and two-sided $p$.

*Guide:* use **Welch's t-test** when each group's metric is roughly normal and
$n$ is reasonable; use **Mann–Whitney U** for small samples or skewed
distributions. A small $p$ (e.g. < 0.05) suggests the two types differ for that
metric — but inspect the **box plot** and $n$ before concluding.

---

## 8. Charts

- **Bar chart** — mean ± SEM per type for a chosen metric (quick group comparison).
- **Box plot** — median, quartiles (box = IQR), and 1.5·IQR whiskers per type (shows spread and outliers).
- **Scatter plot** — any metric vs. any metric, colored by type (e.g. `ch0_mean` vs `ch1_mean` to eyeball colocalization across images).
- **Histogram** — per-series, per-channel intensity distribution with the threshold marker (y-axis uses $\log(1+\text{count})$ so sparse signal isn't hidden by the background peak).
"""
