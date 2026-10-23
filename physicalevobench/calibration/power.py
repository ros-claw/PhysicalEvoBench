"""Exact prospective power under explicit hypothetical paired outcome probabilities."""

import math


def paired_power(n, gain, discordance, alpha=.05):
    if not (0 <= gain <= discordance <= 1) or n <= 0:
        raise ValueError('Invalid hypothetical paired outcome probabilities')
    if discordance == 0:
        return 0.
    probability_win=(discordance+gain)/(2*discordance)
    power=0.
    for k in range(1,n+1):
        probability_k=math.comb(n,k)*discordance**k*(1-discordance)**(n-k)
        tail=1.
        for wins in range(k+1):
            if tail <= alpha+1e-14:
                power+=probability_k*sum(math.comb(k,j)*probability_win**j*(1-probability_win)**(k-j)
                                          for j in range(wins,k+1))
                break
            tail-=math.comb(k,wins)/2**k
    return power
