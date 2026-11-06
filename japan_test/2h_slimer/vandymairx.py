import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Optional, Tuple

from sudachipy import Dictionary, SplitMode

import sandbox.japan_test.main as jp

# ============================================================
# CONFIG
# ============================================================
SONG_CSV = Path(r"C:\Users\kniou\Documents\project_in_1141\fianl\backend\web_crawler\lyrics_output.csv")
WHISPER_DIR = Path(r"G:\我的雲端硬碟\audio2\whisper_json")
SONG_MATCH_THRESHOLD = 0.72

MAX_READING_CANDIDATES = 10
READING_DP_BEAM = 120
READING_LENGTH_SLACK = 4
ALT_READING_PENALTY = 0.25

K_FREQUENCY = 3.0
K_SONG = 2.0

# ============================================================
# SUBSTITUTION STATS
# value = (all_count, all_song_count, err_count, err_song_count, error_rate, song_error_rate)
# ============================================================
SUB_STAT_FIELDS = ("all_count", "all_song_count", "err_count", "err_song_count", "error_rate", "song_error_rate")
SUBSTITUTION_STATS = {
    ('o', 'a'): (2189, 19, 25, 5, 0.011420740063956145, 0.2631578947368421),
    ('d', 't'): (598, 19, 23, 11, 0.038461538461538464, 0.5789473684210527),
    ('u', 'a'): (1636, 19, 19, 6, 0.011613691931540342, 0.3157894736842105),
    ('i', 'a'): (2020, 19, 19, 2, 0.009405940594059406, 0.10526315789473684),
    ('n', 'r'): (1488, 19, 17, 2, 0.0114247311827957, 0.10526315789473684),
    ('e', 'a'): (1137, 19, 14, 4, 0.012313104661389622, 0.21052631578947367),
    ('r', 'n'): (792, 19, 13, 11, 0.016414141414141416, 0.5789473684210527),
    ('t', 'd'): (998, 19, 13, 8, 0.013026052104208416, 0.42105263157894735),
    ('i', 'e'): (2020, 19, 12, 8, 0.005940594059405941, 0.42105263157894735),
    ('k', 'r'): (1167, 19, 12, 2, 0.010282776349614395, 0.10526315789473684),
    ('i', 'u'): (2020, 19, 11, 8, 0.005445544554455445, 0.42105263157894735),
    ('g', 'k'): (266, 19, 11, 6, 0.041353383458646614, 0.3157894736842105),
    ('a', 'u'): (3269, 19, 11, 6, 0.00336494340776996, 0.3157894736842105),
    ('u', 'i'): (1636, 19, 11, 4, 0.006723716381418093, 0.21052631578947367),
    ('e', 'u'): (1137, 19, 10, 7, 0.008795074758135445, 0.3684210526315789),
    ('o', 'u'): (2189, 19, 10, 6, 0.0045682960255824575, 0.3157894736842105),
    ('d', 'r'): (598, 19, 10, 5, 0.016722408026755852, 0.2631578947368421),
    ('t', 'r'): (998, 19, 10, 1, 0.01002004008016032, 0.05263157894736842),
    ('u', 'e'): (1636, 19, 8, 6, 0.004889975550122249, 0.3157894736842105),
    ('e', 'i'): (1137, 19, 8, 6, 0.007036059806508356, 0.3157894736842105),
    ('a', 'o'): (3269, 19, 8, 6, 0.002447231569287244, 0.3157894736842105),
    ('m', 'n'): (821, 19, 8, 4, 0.0097442143727162, 0.21052631578947367),
    ('e', 'r'): (1137, 19, 8, 1, 0.007036059806508356, 0.05263157894736842),
    ('n', 'm'): (1488, 19, 7, 6, 0.004704301075268817, 0.3157894736842105),
    ('k', 't'): (1167, 19, 7, 6, 0.005998286203941731, 0.3157894736842105),
    ('o', 'r'): (2189, 19, 7, 1, 0.0031978072179077205, 0.05263157894736842),
    ('z', 'u'): (132, 19, 6, 5, 0.045454545454545456, 0.2631578947368421),
    ('o', 'e'): (2189, 19, 6, 4, 0.002740977615349475, 0.21052631578947367),
    ('o', 'i'): (2189, 19, 6, 3, 0.002740977615349475, 0.15789473684210525),
    ('i', 'n'): (2020, 19, 6, 3, 0.0029702970297029703, 0.15789473684210525),
    ('u', 'o'): (1636, 19, 6, 3, 0.003667481662591687, 0.15789473684210525),
    ('u', 'q'): (1636, 19, 6, 3, 0.003667481662591687, 0.15789473684210525),
    ('u', 'r'): (1636, 19, 6, 3, 0.003667481662591687, 0.15789473684210525),
    ('i', 'r'): (2020, 19, 6, 2, 0.0029702970297029703, 0.10526315789473684),
    ('a', 'f'): (3269, 19, 5, 5, 0.0015295197308045274, 0.2631578947368421),
    ('m', 'a'): (821, 19, 5, 3, 0.0060901339829476245, 0.15789473684210525),
    ('h', 'r'): (441, 19, 5, 2, 0.011337868480725623, 0.10526315789473684),
    ('s', 'a'): (460, 19, 5, 2, 0.010869565217391304, 0.10526315789473684),
    ('t', 'b'): (998, 19, 4, 4, 0.004008016032064128, 0.21052631578947367),
    ('u', 'n'): (1636, 19, 4, 4, 0.0024449877750611247, 0.21052631578947367),
    ('a', 'e'): (3269, 19, 4, 4, 0.001223615784643622, 0.21052631578947367),
    ('a', 'n'): (3269, 19, 4, 4, 0.001223615784643622, 0.21052631578947367),
    ('ch', 'j'): (80, 18, 4, 3, 0.05, 0.16666666666666666),
    ('m', 'b'): (821, 19, 4, 3, 0.0048721071863581, 0.15789473684210525),
    ('z', 's'): (132, 19, 4, 3, 0.030303030303030304, 0.15789473684210525),
    ('y', 'ry'): (244, 19, 4, 2, 0.01639344262295082, 0.10526315789473684),
    ('y', 'a'): (244, 19, 4, 2, 0.01639344262295082, 0.10526315789473684),
    ('s', 'r'): (460, 19, 4, 2, 0.008695652173913044, 0.10526315789473684),
    ('o', 'w'): (2189, 19, 4, 2, 0.001827318410232983, 0.10526315789473684),
    ('n', 'a'): (1488, 19, 4, 2, 0.002688172043010753, 0.10526315789473684),
    ('a', 'i'): (3269, 19, 4, 2, 0.001223615784643622, 0.10526315789473684),
    ('a', 's'): (3269, 19, 4, 2, 0.001223615784643622, 0.10526315789473684),
    ('g', 'r'): (266, 19, 4, 2, 0.015037593984962405, 0.10526315789473684),
    ('sh', 'r'): (363, 19, 4, 1, 0.011019283746556474, 0.05263157894736842),
    ('w', 'h'): (389, 19, 3, 3, 0.007712082262210797, 0.15789473684210525),
    ('u', 'k'): (1636, 19, 3, 3, 0.0018337408312958435, 0.15789473684210525),
    ('f', 'k'): (60, 15, 3, 3, 0.05, 0.2),
    ('d', 'n'): (598, 19, 3, 3, 0.005016722408026756, 0.15789473684210525),
    ('m', 'w'): (821, 19, 3, 3, 0.0036540803897685747, 0.15789473684210525),
    ('m', 'o'): (821, 19, 3, 3, 0.0036540803897685747, 0.15789473684210525),
    ('n', 'u'): (1488, 19, 3, 3, 0.0020161290322580645, 0.15789473684210525),
    ('k', 'g'): (1167, 19, 3, 3, 0.002570694087403599, 0.15789473684210525),
    ('j', 'ch'): (59, 16, 3, 3, 0.05084745762711865, 0.1875),
    ('k', 'ch'): (1167, 19, 3, 2, 0.002570694087403599, 0.10526315789473684),
    ('sh', 'a'): (363, 19, 3, 2, 0.008264462809917356, 0.10526315789473684),
    ('r', 'k'): (792, 19, 3, 2, 0.003787878787878788, 0.10526315789473684),
    ('r', 't'): (792, 19, 3, 2, 0.003787878787878788, 0.10526315789473684),
    ('t', 'o'): (998, 19, 3, 2, 0.003006012024048096, 0.10526315789473684),
    ('t', 'a'): (998, 19, 3, 2, 0.003006012024048096, 0.10526315789473684),
    ('y', 'i'): (244, 19, 3, 1, 0.012295081967213115, 0.05263157894736842),
    ('m', 'hy'): (821, 19, 3, 1, 0.0036540803897685747, 0.05263157894736842),
    ('m', 'r'): (821, 19, 3, 1, 0.0036540803897685747, 0.05263157894736842),
    ('q', 'a'): (97, 16, 3, 1, 0.030927835051546393, 0.0625),
    ('o', 't'): (2189, 19, 3, 1, 0.0013704888076747374, 0.05263157894736842),
    ('a', 'q'): (3269, 19, 3, 1, 0.0009177118384827164, 0.05263157894736842),
    ('b', 'r'): (226, 19, 2, 2, 0.008849557522123894, 0.10526315789473684),
    ('b', 'h'): (226, 19, 2, 2, 0.008849557522123894, 0.10526315789473684),
    ('f', 'n'): (60, 15, 2, 2, 0.03333333333333333, 0.13333333333333333),
    ('h', 'b'): (441, 19, 2, 2, 0.0045351473922902496, 0.10526315789473684),
    ('h', 'u'): (441, 19, 2, 2, 0.0045351473922902496, 0.10526315789473684),
    ('r', 'd'): (792, 19, 2, 2, 0.0025252525252525255, 0.10526315789473684),
    ('n', 'sh'): (1488, 19, 2, 2, 0.0013440860215053765, 0.10526315789473684),
    ('n', 'd'): (1488, 19, 2, 2, 0.0013440860215053765, 0.10526315789473684),
    ('m', 'h'): (821, 19, 2, 2, 0.00243605359317905, 0.10526315789473684),
    ('m', 'd'): (821, 19, 2, 2, 0.00243605359317905, 0.10526315789473684),
    ('k', 'm'): (1167, 19, 2, 2, 0.001713796058269066, 0.10526315789473684),
    ('k', 'n'): (1167, 19, 2, 2, 0.001713796058269066, 0.10526315789473684),
    ('k', 'p'): (1167, 19, 2, 2, 0.001713796058269066, 0.10526315789473684),
    ('k', 'a'): (1167, 19, 2, 2, 0.001713796058269066, 0.10526315789473684),
    ('k', 'b'): (1167, 19, 2, 2, 0.001713796058269066, 0.10526315789473684),
    ('z', 'ts'): (132, 19, 2, 2, 0.015151515151515152, 0.10526315789473684),
    ('y', 'w'): (244, 19, 2, 2, 0.00819672131147541, 0.10526315789473684),
    ('w', 'y'): (389, 19, 2, 2, 0.005141388174807198, 0.10526315789473684),
    ('u', 'm'): (1636, 19, 2, 2, 0.0012224938875305623, 0.10526315789473684),
    ('p', 't'): (21, 11, 2, 2, 0.09523809523809523, 0.18181818181818182),
    ('t', 's'): (998, 19, 2, 2, 0.002004008016032064, 0.10526315789473684),
    ('s', 'z'): (460, 19, 2, 2, 0.004347826086956522, 0.10526315789473684),
    ('r', 'w'): (792, 19, 2, 1, 0.0025252525252525255, 0.05263157894736842),
    ('ts', 'r'): (289, 19, 2, 1, 0.006920415224913495, 0.05263157894736842),
    ('u', 'sh'): (1636, 19, 2, 1, 0.0012224938875305623, 0.05263157894736842),
    ('u', 't'): (1636, 19, 2, 1, 0.0012224938875305623, 0.05263157894736842),
    ('i', 't'): (2020, 19, 2, 1, 0.0009900990099009901, 0.05263157894736842),
    ('m', 'u'): (821, 19, 2, 1, 0.00243605359317905, 0.05263157894736842),
    ('q', 'o'): (97, 16, 2, 1, 0.020618556701030927, 0.0625),
    ('o', 'k'): (2189, 19, 2, 1, 0.0009136592051164915, 0.05263157894736842),
    ('e', 'sh'): (1137, 19, 2, 1, 0.001759014951627089, 0.05263157894736842),
    ('h', 'n'): (441, 19, 2, 1, 0.0045351473922902496, 0.05263157894736842),
    ('h', 'p'): (441, 19, 2, 1, 0.0045351473922902496, 0.05263157894736842),
    ('d', 'o'): (598, 19, 2, 1, 0.0033444816053511705, 0.05263157894736842),
    ('b', 'g'): (226, 19, 2, 1, 0.008849557522123894, 0.05263157894736842),
    ('a', 'r'): (3269, 19, 1, 1, 0.0003059039461609055, 0.05263157894736842),
    ('a', 'v'): (3269, 19, 1, 1, 0.0003059039461609055, 0.05263157894736842),
    ('a', 'w'): (3269, 19, 1, 1, 0.0003059039461609055, 0.05263157894736842),
    ('a', 'y'): (3269, 19, 1, 1, 0.0003059039461609055, 0.05263157894736842),
    ('b', 'a'): (226, 19, 1, 1, 0.004424778761061947, 0.05263157894736842),
    ('b', 'f'): (226, 19, 1, 1, 0.004424778761061947, 0.05263157894736842),
    ('a', 'm'): (3269, 19, 1, 1, 0.0003059039461609055, 0.05263157894736842),
    ('a', 'h'): (3269, 19, 1, 1, 0.0003059039461609055, 0.05263157894736842),
    ('a', 'b'): (3269, 19, 1, 1, 0.0003059039461609055, 0.05263157894736842),
    ('a', 'd'): (3269, 19, 1, 1, 0.0003059039461609055, 0.05263157894736842),
    ('b', 'ts'): (226, 19, 1, 1, 0.004424778761061947, 0.05263157894736842),
    ('by', 'u'): (1, 1, 1, 1, 1.0, 1.0),
    ('b', 'i'): (226, 19, 1, 1, 0.004424778761061947, 0.05263157894736842),
    ('b', 'k'): (226, 19, 1, 1, 0.004424778761061947, 0.05263157894736842),
    ('b', 'm'): (226, 19, 1, 1, 0.004424778761061947, 0.05263157894736842),
    ('ch', 'sh'): (80, 18, 1, 1, 0.0125, 0.05555555555555555),
    ('ch', 't'): (80, 18, 1, 1, 0.0125, 0.05555555555555555),
    ('ch', 'tch'): (80, 18, 1, 1, 0.0125, 0.05555555555555555),
    ('ch', 'ts'): (80, 18, 1, 1, 0.0125, 0.05555555555555555),
    ('ch', 'u'): (80, 18, 1, 1, 0.0125, 0.05555555555555555),
    ('d', 'a'): (598, 19, 1, 1, 0.0016722408026755853, 0.05263157894736842),
    ('d', 'b'): (598, 19, 1, 1, 0.0016722408026755853, 0.05263157894736842),
    ('d', 'e'): (598, 19, 1, 1, 0.0016722408026755853, 0.05263157894736842),
    ('d', 'i'): (598, 19, 1, 1, 0.0016722408026755853, 0.05263157894736842),
    ('d', 'k'): (598, 19, 1, 1, 0.0016722408026755853, 0.05263157894736842),
    ('d', 'm'): (598, 19, 1, 1, 0.0016722408026755853, 0.05263157894736842),
    ('h', 'w'): (441, 19, 1, 1, 0.0022675736961451248, 0.05263157894736842),
    ('h', 't'): (441, 19, 1, 1, 0.0022675736961451248, 0.05263157894736842),
    ('h', 'ch'): (441, 19, 1, 1, 0.0022675736961451248, 0.05263157894736842),
    ('h', 'd'): (441, 19, 1, 1, 0.0022675736961451248, 0.05263157894736842),
    ('h', 'f'): (441, 19, 1, 1, 0.0022675736961451248, 0.05263157894736842),
    ('h', 'i'): (441, 19, 1, 1, 0.0022675736961451248, 0.05263157894736842),
    ('h', 'k'): (441, 19, 1, 1, 0.0022675736961451248, 0.05263157894736842),
    ('g', 'sh'): (266, 19, 1, 1, 0.0037593984962406013, 0.05263157894736842),
    ('h', 'a'): (441, 19, 1, 1, 0.0022675736961451248, 0.05263157894736842),
    ('f', 'o'): (60, 15, 1, 1, 0.016666666666666666, 0.06666666666666667),
    ('f', 'p'): (60, 15, 1, 1, 0.016666666666666666, 0.06666666666666667),
    ('f', 'y'): (60, 15, 1, 1, 0.016666666666666666, 0.06666666666666667),
    ('g', 'd'): (266, 19, 1, 1, 0.0037593984962406013, 0.05263157894736842),
    ('g', 'e'): (266, 19, 1, 1, 0.0037593984962406013, 0.05263157894736842),
    ('g', 'h'): (266, 19, 1, 1, 0.0037593984962406013, 0.05263157894736842),
    ('e', 'j'): (1137, 19, 1, 1, 0.0008795074758135445, 0.05263157894736842),
    ('e', 'm'): (1137, 19, 1, 1, 0.0008795074758135445, 0.05263157894736842),
    ('e', 'o'): (1137, 19, 1, 1, 0.0008795074758135445, 0.05263157894736842),
    ('d', 's'): (598, 19, 1, 1, 0.0016722408026755853, 0.05263157894736842),
    ('d', 'w'): (598, 19, 1, 1, 0.0016722408026755853, 0.05263157894736842),
    ('o', 'n'): (2189, 19, 1, 1, 0.00045682960255824577, 0.05263157894736842),
    ('o', 'f'): (2189, 19, 1, 1, 0.00045682960255824577, 0.05263157894736842),
    ('o', 'h'): (2189, 19, 1, 1, 0.00045682960255824577, 0.05263157894736842),
    ('r', 'a'): (792, 19, 1, 1, 0.0012626262626262627, 0.05263157894736842),
    ('r', 'e'): (792, 19, 1, 1, 0.0012626262626262627, 0.05263157894736842),
    ('q', 'i'): (97, 16, 1, 1, 0.010309278350515464, 0.0625),
    ('o', 'z'): (2189, 19, 1, 1, 0.00045682960255824577, 0.05263157894736842),
    ('n', 'b'): (1488, 19, 1, 1, 0.0006720430107526882, 0.05263157894736842),
    ('m', 'sh'): (821, 19, 1, 1, 0.001218026796589525, 0.05263157894736842),
    ('n', 'i'): (1488, 19, 1, 1, 0.0006720430107526882, 0.05263157894736842),
    ('n', 'o'): (1488, 19, 1, 1, 0.0006720430107526882, 0.05263157894736842),
    ('n', 'w'): (1488, 19, 1, 1, 0.0006720430107526882, 0.05263157894736842),
    ('n', 'y'): (1488, 19, 1, 1, 0.0006720430107526882, 0.05263157894736842),
    ('i', 'z'): (2020, 19, 1, 1, 0.0004950495049504951, 0.05263157894736842),
    ('i', 'o'): (2020, 19, 1, 1, 0.0004950495049504951, 0.05263157894736842),
    ('k', 'd'): (1167, 19, 1, 1, 0.000856898029134533, 0.05263157894736842),
    ('k', 'f'): (1167, 19, 1, 1, 0.000856898029134533, 0.05263157894736842),
    ('j', 'd'): (59, 16, 1, 1, 0.01694915254237288, 0.0625),
    ('j', 'i'): (59, 16, 1, 1, 0.01694915254237288, 0.0625),
    ('j', 'sh'): (59, 16, 1, 1, 0.01694915254237288, 0.0625),
    ('j', 'z'): (59, 16, 1, 1, 0.01694915254237288, 0.0625),
    ('k', 's'): (1167, 19, 1, 1, 0.000856898029134533, 0.05263157894736842),
    ('k', 'sh'): (1167, 19, 1, 1, 0.000856898029134533, 0.05263157894736842),
    ('k', 'h'): (1167, 19, 1, 1, 0.000856898029134533, 0.05263157894736842),
    ('k', 'i'): (1167, 19, 1, 1, 0.000856898029134533, 0.05263157894736842),
    ('k', 'j'): (1167, 19, 1, 1, 0.000856898029134533, 0.05263157894736842),
    ('m', 'g'): (821, 19, 1, 1, 0.001218026796589525, 0.05263157894736842),
    ('k', 'z'): (1167, 19, 1, 1, 0.000856898029134533, 0.05263157894736842),
    ('u', 'z'): (1636, 19, 1, 1, 0.0006112469437652812, 0.05263157894736842),
    ('v', 'b'): (2, 1, 1, 1, 0.5, 1.0),
    ('u', 'ky'): (1636, 19, 1, 1, 0.0006112469437652812, 0.05263157894736842),
    ('y', 'd'): (244, 19, 1, 1, 0.004098360655737705, 0.05263157894736842),
    ('w', 'i'): (389, 19, 1, 1, 0.002570694087403599, 0.05263157894736842),
    ('w', 'r'): (389, 19, 1, 1, 0.002570694087403599, 0.05263157894736842),
    ('w', 't'): (389, 19, 1, 1, 0.002570694087403599, 0.05263157894736842),
    ('z', 'i'): (132, 19, 1, 1, 0.007575757575757576, 0.05263157894736842),
    ('z', 'm'): (132, 19, 1, 1, 0.007575757575757576, 0.05263157894736842),
    ('y', 'ky'): (244, 19, 1, 1, 0.004098360655737705, 0.05263157894736842),
    ('y', 'o'): (244, 19, 1, 1, 0.004098360655737705, 0.05263157894736842),
    ('ts', 's'): (289, 19, 1, 1, 0.0034602076124567475, 0.05263157894736842),
    ('ts', 't'): (289, 19, 1, 1, 0.0034602076124567475, 0.05263157894736842),
    ('ts', 'z'): (289, 19, 1, 1, 0.0034602076124567475, 0.05263157894736842),
    ('t', 'y'): (998, 19, 1, 1, 0.001002004008016032, 0.05263157894736842),
    ('tch', 'j'): (1, 1, 1, 1, 1.0, 1.0),
    ('ts', 'k'): (289, 19, 1, 1, 0.0034602076124567475, 0.05263157894736842),
    ('ts', 'n'): (289, 19, 1, 1, 0.0034602076124567475, 0.05263157894736842),
    ('t', 'e'): (998, 19, 1, 1, 0.001002004008016032, 0.05263157894736842),
    ('t', 'g'): (998, 19, 1, 1, 0.001002004008016032, 0.05263157894736842),
    ('t', 'h'): (998, 19, 1, 1, 0.001002004008016032, 0.05263157894736842),
    ('t', 'k'): (998, 19, 1, 1, 0.001002004008016032, 0.05263157894736842),
    ('t', 'n'): (998, 19, 1, 1, 0.001002004008016032, 0.05263157894736842),
    ('ry', 'gy'): (6, 4, 1, 1, 0.16666666666666666, 0.25),
    ('ry', 'my'): (6, 4, 1, 1, 0.16666666666666666, 0.25),
    ('r', 'm'): (792, 19, 1, 1, 0.0012626262626262627, 0.05263157894736842),
    ('r', 'o'): (792, 19, 1, 1, 0.0012626262626262627, 0.05263157894736842),
    ('s', 'ch'): (460, 19, 1, 1, 0.002173913043478261, 0.05263157894736842),
    ('s', 'i'): (460, 19, 1, 1, 0.002173913043478261, 0.05263157894736842),
    ('sh', 'j'): (363, 19, 1, 1, 0.0027548209366391185, 0.05263157894736842),
    ('sh', 'm'): (363, 19, 1, 1, 0.0027548209366391185, 0.05263157894736842),
    ('sh', 'ts'): (363, 19, 1, 1, 0.0027548209366391185, 0.05263157894736842),
    ('sh', 'u'): (363, 19, 1, 1, 0.0027548209366391185, 0.05263157894736842),
}

def get_substitution_stats(lyrics_phoneme: str, whisper_phoneme: str):
    value = SUBSTITUTION_STATS.get((lyrics_phoneme, whisper_phoneme))
    return dict(zip(SUB_STAT_FIELDS, value)) if value else None

def build_substitution_matrix():
    target_total, observed_total = {}, {}
    total_errors = 0

    for (target, observed), data in SUBSTITUTION_STATS.items():
        err_count = data[2]
        target_total[target] = target_total.get(target, 0) + err_count
        observed_total[observed] = observed_total.get(observed, 0) + err_count
        total_errors += err_count

    matrix = {}

    for (target, observed), data in SUBSTITUTION_STATS.items():
        _, _, err_count, err_song_count, _, _ = data

        probability = err_count / target_total[target]
        background = observed_total[observed] / total_errors
        lift = probability / background if background else 0.0

        freq_conf = err_count / (err_count + K_FREQUENCY)
        song_conf = err_song_count / (err_song_count + K_SONG)
        confidence = freq_conf * song_conf

        score = (
            confidence * ((lift - 1.0) / (lift + 1.0))
            if lift > 0 else 0.0
        )

        matrix[(target, observed)] = max(0.0, min(1.0, score))

    return matrix

SUBSTITUTION_MATRIX = build_substitution_matrix()

def substitution_cost(target: str, observed: str, use_matrix: bool) -> float:
    if target == observed:
        return 0.0
    if not use_matrix:
        return 1.0

    learned_score = SUBSTITUTION_MATRIX.get((target, observed), 0.0)
    return 1.0 - learned_score

# ============================================================
# SUDACHI
# ============================================================
SUDACHI_DICT = Dictionary(dict="full")
SUDACHI = SUDACHI_DICT.create(mode=SplitMode.C)
SKIP_POS = {"空白", "補助記号", "記号"}

# ============================================================
# ROMAJI -> PHONEME
# ============================================================
VOWELS = set("aiueo")
MULTI_PHONEMES = [
    "tch", "sh", "ch", "ts", "ky", "gy", "ny", "hy", 
    "by", "py", "my", "ry", "dy", "ty", "jy"
]
CONSONANTS = set("bcdfghjklmnpqrstvwxyz")

def clean_romaji(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    replacements = {"ā": "aa", "ī": "ii", "ū": "uu", "ē": "ee", "ō": "ou"}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return "".join(c for c in text if c.isalpha())

def roma_to_phoneme_tokens(roma: str) -> List[str]:
    roma = clean_romaji(roma)
    tokens = []
    i = 0
    while i < len(roma):
        c = roma[i]
        if c in VOWELS:
            tokens.append(c)
            i += 1
            continue
        if c in CONSONANTS and c != "n" and i + 1 < len(roma) and roma[i + 1] == c:
            tokens.append("q")
            i += 1
            continue
        matched = False
        for phoneme in MULTI_PHONEMES:
            if roma.startswith(phoneme, i):
                tokens.append(phoneme)
                i += len(phoneme)
                matched = True
                break
        if matched:
            continue
        if c in CONSONANTS:
            tokens.append(c)
        i += 1
    return tokens

def reading_to_phonemes(reading: str) -> List[str]:
    return roma_to_phoneme_tokens(jp.to_romaji(reading))

# ============================================================
# CSV
# ============================================================
def open_csv_with_fallback(path: Path):
    for encoding in ("utf-8-sig", "utf-8", "cp932"):
        try:
            f = open(path, "r", encoding=encoding, newline="")
            f.read(4096)
            f.seek(0)
            return f
        except UnicodeDecodeError:
            try: f.close()
            except Exception: pass
    raise RuntimeError(f"Cannot decode CSV: {path}")

def load_song_csv(path: Path):
    songs = []
    with open_csv_with_fallback(path) as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return songs
        header = [x.strip().lstrip("\ufeff") for x in header]
        
        for row in reader:
            if not row:
                continue
            if len(header) == 5 and len(row) >= 6 and row[4].strip().lower().startswith(("http://", "https://")):
                song_name, lyrics = row[3].strip(), row[5].strip()
            else:
                mapping = {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}
                song_name = mapping.get("Song_Name", "").strip()
                lyrics = mapping.get("Lyrics", "").strip()
            if song_name and lyrics:
                songs.append({"song_name": song_name, "lyrics": lyrics})
    return songs

# ============================================================
# SONG NAME MATCH
# ============================================================
def normalize_song_name(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"(whisper|whisper_json|final|test|audio|vocal)", "", text, flags=re.IGNORECASE)
    return "".join(c for c in text if c.isalnum() or "\u3040" <= c <= "\u30ff" or "\u4e00" <= c <= "\u9fff")

def find_song_for_json(json_path: Path, songs) -> Tuple[Optional[dict], float]:
    stem = normalize_song_name(json_path.stem)
    for song in songs:
        if normalize_song_name(song["song_name"]) == stem:
            return song, 1.0

    best_song, best_score = None, 0.0
    for song in songs:
        song_norm = normalize_song_name(song["song_name"])
        if not song_norm:
            continue
        if song_norm in stem or stem in song_norm:
            score = min(len(song_norm), len(stem)) / max(len(song_norm), len(stem))
        else:
            score = SequenceMatcher(None, stem, song_norm).ratio()
        if score > best_score:
            best_score, best_song = score, song

    if best_score >= SONG_MATCH_THRESHOLD:
        return best_song, best_score
    return None, best_score

# ============================================================
# WHISPER JSON
# ============================================================
def load_whisper_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        segments = data["segments"] if isinstance(data.get("segments"), list) else [data]
    elif isinstance(data, list):
        segments = data
    else:
        raise ValueError(f"Unsupported JSON structure: {path}")

    lines = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        text = (seg.get("line") or seg.get("text") or "").strip()
        if text:
            lines.append(text)
    return "\n".join(lines)

# ============================================================
# PHONEME EDIT DISTANCE
# ============================================================
def phoneme_edit_distance(
    expected: List[str],
    observed: List[str],
    use_matrix: bool = False
) -> float:
    """Phoneme-level Levenshtein. Direction: Lyrics -> Whisper."""
    previous = [float(j) for j in range(len(observed) + 1)]

    for i, target in enumerate(expected, start=1):
        current = [float(i)]

        for j, actual in enumerate(observed, start=1):
            sub = previous[j - 1] + substitution_cost(
                target, actual, use_matrix
            )

            current.append(min(
                previous[j] + 1.0,      # DELETE
                current[j - 1] + 1.0,  # INSERT
                sub
            ))

        previous = current

    return previous[-1]

# ============================================================
# 多讀音候選
# ============================================================
@dataclass
class ReadingCandidate:
    reading: str
    phonemes: List[str]
    is_default: bool

@dataclass
class ReadingUnit:
    surface: str
    candidates: List[ReadingCandidate]

def get_lookup_readings(surface: str) -> List[str]:
    result = []
    try:
        entries = SUDACHI_DICT.lookup(surface)
    except Exception:
        return result
    for entry in entries:
        reading = entry.reading_form()
        if reading and reading not in result:
            result.append(reading)
    return result

def build_reading_units(text: str) -> List[ReadingUnit]:
    units = []
    for morpheme in SUDACHI.tokenize(text):
        pos = morpheme.part_of_speech()
        if pos[0] in SKIP_POS:
            continue
        surface = morpheme.surface()
        default_reading = morpheme.reading_form() or surface
        readings = [default_reading]
        for reading in get_lookup_readings(surface):
            if reading not in readings:
                readings.append(reading)

        candidates, seen = [], set()
        for reading in readings:
            phonemes = reading_to_phonemes(reading)
            signature = tuple(phonemes)
            if signature in seen:
                continue
            seen.add(signature)
            candidates.append(ReadingCandidate(
                reading=reading, phonemes=phonemes, is_default=(reading == default_reading)
            ))
            if len(candidates) >= MAX_READING_CANDIDATES:
                break
        units.append(ReadingUnit(surface=surface, candidates=candidates))
    return units

def default_phonemes(text: str) -> List[str]:
    result = []
    for unit in build_reading_units(text):
        if unit.candidates:
            result.extend(unit.candidates[0].phonemes)
    return result

# ============================================================
# 一字多音 Reading DP
# ============================================================
def choose_whisper_reading_dp(whisper_text: str, reference_phonemes: List[str]) -> List[str]:
    units = build_reading_units(whisper_text)
    if not units:
        return []

    states = {0: (0.0, [])}
    ref_len = len(reference_phonemes)

    for unit in units:
        next_states = {}
        for ref_pos, (base_cost, built_phonemes) in states.items():
            for candidate in unit.candidates:
                p = candidate.phonemes
                p_len = len(p)
                min_len = max(0, p_len - READING_LENGTH_SLACK)
                max_len = min(ref_len - ref_pos, p_len + READING_LENGTH_SLACK)
                
                lengths = [0] if ref_pos >= ref_len else range(min_len, max_len + 1)

                for seg_len in lengths:
                    end = ref_pos + seg_len
                    ref_segment = reference_phonemes[ref_pos:end]
                    cost = phoneme_edit_distance(p, ref_segment, use_matrix=False)
                    if not candidate.is_default:
                        cost += ALT_READING_PENALTY
                    total = base_cost + cost
                    old = next_states.get(end)
                    if old is None or total < old[0]:
                        next_states[end] = (total, built_phonemes + p)

        states = dict(sorted(next_states.items(), key=lambda item: item[1][0])[:READING_DP_BEAM])

    best = None
    for ref_pos, (cost, phonemes) in states.items():
        total_cost = cost + (ref_len - ref_pos)
        if best is None or total_cost < best[0]:
            best = (total_cost, phonemes)
    return best[1]

# ============================================================
# CHANGE-ONLY SCORE
#
# INSERT / DELETE 只負責幫 DP 對齊，不進最後分數。
#
# Baseline:
#   MATCH = 0
#   SUB   = 1
#
# Matrix:
#   MATCH = 0
#   SUB   = 1 - learned_score
#
# 最後只用 MATCH + SUB 當 denominator。
# ============================================================
def baseline_alignment(expected: List[str], observed: List[str]):
    n, m = len(expected), len(observed)

    dp = [[0] * (m + 1) for _ in range(n + 1)]
    trace = [[None] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp[i][0] = i
        trace[i][0] = "D"

    for j in range(1, m + 1):
        dp[0][j] = j
        trace[0][j] = "I"

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            sub = dp[i - 1][j - 1] + (
                0 if expected[i - 1] == observed[j - 1] else 1
            )
            delete = dp[i - 1][j] + 1
            insert = dp[i][j - 1] + 1

            best = min(sub, delete, insert)
            dp[i][j] = best

            # Tie 時優先 diagonal，減少不必要 gap。
            if best == sub:
                trace[i][j] = "M" if expected[i - 1] == observed[j - 1] else "S"
            elif best == delete:
                trace[i][j] = "D"
            else:
                trace[i][j] = "I"

    aligned = []
    i, j = n, m

    while i > 0 or j > 0:
        op = trace[i][j]

        if i > 0 and j > 0 and op in ("M", "S"):
            aligned.append((expected[i - 1], observed[j - 1], op))
            i -= 1
            j -= 1
        elif i > 0 and (j == 0 or op == "D"):
            i -= 1
        else:
            j -= 1

    aligned.reverse()
    return aligned


def calculate_scores(lyrics_text: str, whisper_text: str):
    lyrics_phonemes = default_phonemes(lyrics_text)

    # Reading DP 固定使用 baseline cost，
    # 讓 Baseline / Matrix 比較同一組 phoneme sequence。
    whisper_phonemes = choose_whisper_reading_dp(
        whisper_text,
        lyrics_phonemes
    )

    aligned = baseline_alignment(
        lyrics_phonemes,
        whisper_phonemes
    )

    match_count = 0
    sub_count = 0
    covered_sub = 0
    matrix_sub_cost = 0.0

    for target, observed, op in aligned:
        if op == "M":
            match_count += 1
            continue

        sub_count += 1

        if (target, observed) in SUBSTITUTION_STATS:
            covered_sub += 1

        matrix_sub_cost += substitution_cost(
            target,
            observed,
            use_matrix=True
        )

    compared = match_count + sub_count

    if compared == 0:
        return 0.0, 0.0, 0, 0, 0, 0.0

    baseline_score = 1.0 - sub_count / compared
    matrix_score = 1.0 - matrix_sub_cost / compared
    coverage = covered_sub / sub_count if sub_count else 0.0

    return (
        baseline_score,
        matrix_score,
        match_count,
        sub_count,
        covered_sub,
        coverage
    )

# ============================================================
# MAIN
# ============================================================
def main():
    songs = load_song_csv(SONG_CSV)
    whisper_files = sorted(WHISPER_DIR.glob("*.json"))

    print(f"Songs in CSV : {len(songs)}")
    print(f"Whisper JSON : {len(whisper_files)}")
    print(f"Matrix pairs : {len(SUBSTITUTION_MATRIX)}")
    print()
    print("=" * 116)
    print(
        f"{'Song':<30} "
        f"{'Baseline':>10} "
        f"{'Matrix':>10} "
        f"{'Delta':>10} "
        f"{'MATCH':>8} "
        f"{'SUB':>8} "
        f"{'Covered':>9} "
        f"{'Coverage':>10}"
    )
    print("-" * 116)

    base_total = 0.0
    matrix_total = 0.0
    total_sub = 0
    total_covered = 0
    processed = 0

    for whisper_path in whisper_files:
        song, _ = find_song_for_json(whisper_path, songs)

        if song is None:
            print(f"[SKIP] {whisper_path.name}")
            continue

        try:
            whisper_text = load_whisper_text(whisper_path)

            (
                baseline,
                matrix,
                matches,
                subs,
                covered,
                coverage
            ) = calculate_scores(
                song["lyrics"],
                whisper_text
            )

        except Exception as exc:
            print(f"[ERROR] {whisper_path.name}: {exc}")
            continue

        delta = matrix - baseline

        base_total += baseline
        matrix_total += matrix
        total_sub += subs
        total_covered += covered
        processed += 1

        print(
            f"{song['song_name']:<30} "
            f"{baseline:>10.6f} "
            f"{matrix:>10.6f} "
            f"{delta:>+10.6f} "
            f"{matches:>8} "
            f"{subs:>8} "
            f"{covered:>9} "
            f"{coverage:>9.2%}"
        )

    print("=" * 116)

    if processed:
        base_avg = base_total / processed
        matrix_avg = matrix_total / processed
        overall_coverage = total_covered / total_sub if total_sub else 0.0

        print(
            f"{'Average':<30} "
            f"{base_avg:>10.6f} "
            f"{matrix_avg:>10.6f} "
            f"{matrix_avg - base_avg:>+10.6f}"
        )

        print(
            f"Matrix coverage: "
            f"{total_covered}/{total_sub} "
            f"= {overall_coverage:.2%}"
        )

        print(f"Processed: {processed}")


if __name__ == "__main__":
    main()
