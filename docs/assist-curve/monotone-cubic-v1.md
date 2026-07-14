# `monotone-cubic-v1` numerical contract

This contract is language-neutral. Python and TypeScript implement it directly; renderers do not
define it. Inputs are the schema-version-1 integer points: speed in deci-km/h and assistance in
per-mille. Convert each speed and requested evaluation speed to IEEE 754 binary64 deci-km/h, and
convert each assistance value to binary64 dimensionless assistance by dividing by `1000`.

For consecutive points, let `h[i] = x[i+1] - x[i]` and
`s[i] = (y[i+1] - y[i]) / h[i]`. Reject a definition if it has fewer than two points or any `h[i]`
is non-finite or not strictly positive. For each interior point `i`, calculate:

```text
p = (s[i-1] * h[i] + s[i] * h[i-1]) / (h[i-1] + h[i])
m[i] = (sign(s[i-1]) + sign(s[i]))
       * min(abs(s[i-1]), abs(s[i]), 0.5 * abs(p))
sign(v) = -1 when v < 0, otherwise 1
```

When the input has exactly two points, use their single secant for both endpoint tangents. This
reduces the Hermite segment exactly to the straight line between those points and does not require
an interior tangent.

For three or more points, the endpoint tangents are one-sided:

```text
m[0] = (3 * s[0] - m[1]) / 2
m[n-1] = (3 * s[n-2] - m[n-2]) / 2
```

For `x` strictly inside segment `i`, let `t = (x - x[i]) / h[i]` and evaluate the cubic Hermite
basis:

```text
y = (2t^3 - 3t^2 + 1) * y[i]
  + (t^3 - 2t^2 + t) * h[i] * m[i]
  + (-2t^3 + 3t^2) * y[i+1]
  + (t^3 - t^2) * h[i] * m[i+1]
```

An exact control-point speed returns that point's converted assistance directly. Speeds at or below
the first point return the first assistance; speeds at or above the final point return the final
assistance. Clamp the interpolated result to `0..1` as a final defensive check. Non-finite
evaluation speeds are rejected.

Conformance uses IEEE 754 binary64 arithmetic and an absolute tolerance of `1e-12`. The checked-in
[golden vectors](monotone-cubic-v1-vectors.json) include every control point, endpoint extension,
flat and repeated values, a steep transition, the built-in curve and the smallest assistance
increment. The tangent definition follows the Steffen method used by D3's monotone-X curve, but the
equations above and the vectors are the project contract.
