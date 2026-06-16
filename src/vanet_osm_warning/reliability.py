from __future__ import annotations

import math


def packet_error_rate(packet_size_bytes: int, bit_error_rate: float = 0.0, base_loss_probability: float = 0.0) -> float:
    """Combine an independent base-loss term with BER-derived packet error rate.

    PER = 1 - (1-BER)^(8L). The combined loss assumes base loss and bit errors
    are independent. Values are clamped to [0, 1].
    """
    size_bits = max(0, int(packet_size_bytes)) * 8
    ber = min(max(float(bit_error_rate), 0.0), 1.0)
    base = min(max(float(base_loss_probability), 0.0), 1.0)
    ber_per = 1.0 - math.pow(1.0 - ber, size_bits) if size_bits else 0.0
    return min(1.0, max(0.0, 1.0 - (1.0 - base) * (1.0 - ber_per)))
