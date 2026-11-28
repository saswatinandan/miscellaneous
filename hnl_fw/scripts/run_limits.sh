#!/bin/bash
# Step 6: combine the datacards of all eras and categories for each signal point,
# and compute expected (and, if unblinded, observed) limits with Combine.
#
# Needs CMSSW with HiggsAnalysis/CombinedLimit (Combine), e.g. on lxplus:
#   https://cms-analysis.github.io/HiggsAnalysis-CombinedLimit/
#
# Usage (from hnl_fw/):
#   bash scripts/run_limits.sh 2022 2022EE            # expected limits (blinded, -t -1)
#   UNBLIND=1 bash scripts/run_limits.sh 2022 2022EE  # also observed
set -e
ERAS="$@"
[ -z "$ERAS" ] && { echo "usage: $0 <era> [<era> ...]"; exit 1; }
command -v combine >/dev/null || { echo "combine not found: set up CMSSW + Combine first (cmsenv)"; exit 1; }

FW=$(cd "$(dirname "$0")/.." && pwd)
OUT=$FW/limits
mkdir -p "$OUT"

# all signal names that have a card in the first era
FIRST=$(echo $ERAS | awk '{print $1}')
SIGNALS=$(ls $FW/datacards/$FIRST/*/*.txt 2>/dev/null | xargs -n1 basename | sed 's/\.txt$//' | sort -u)
[ -z "$SIGNALS" ] && { echo "no datacards found in $FW/datacards/$FIRST"; exit 1; }

for SIG in $SIGNALS; do
    CARDS=""
    for ERA in $ERAS; do
        for CARD in $FW/datacards/$ERA/*/$SIG.txt; do
            [ -f "$CARD" ] || continue
            CAT=$(basename $(dirname $CARD))
            CARDS="$CARDS ${ERA}_${CAT}=$CARD"
        done
    done
    combineCards.py $CARDS > $OUT/$SIG.txt
    MASS=$(echo $SIG | sed -n 's/.*_M\([0-9.]*\)_.*/\1/p'); MASS=${MASS:-0}
    if [ "$UNBLIND" = "1" ]; then BLIND=""; else BLIND="-t -1"; fi
    (cd $OUT && combine -M AsymptoticLimits $SIG.txt -n _$SIG -m $MASS $BLIND > $SIG.log 2>&1) \
        && echo "done: $SIG" || echo "FAILED: $SIG (see $OUT/$SIG.log)"
done
echo "results: $OUT/higgsCombine_*.root  ->  python3 scripts/plot_limits.py"
