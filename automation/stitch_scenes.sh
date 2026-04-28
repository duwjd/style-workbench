#!/bin/bash
# Type D: 장면 영상 스티칭
# Usage: bash stitch_scenes.sh output.mp4 scene1.mp4 scene2.mp4 scene3.mp4 ...
# 또는:  bash stitch_scenes.sh output.mp4 --dir scenes_folder/

set -e

OUTPUT="$1"
shift

if [ -z "$OUTPUT" ]; then
    echo "Usage: bash stitch_scenes.sh <output.mp4> <scene1.mp4> <scene2.mp4> ..."
    echo "   or: bash stitch_scenes.sh <output.mp4> --dir <scenes_folder>"
    exit 1
fi

# 임시 파일 리스트 생성
FILELIST=$(mktemp /tmp/filelist_XXXX.txt)

if [ "$1" = "--dir" ]; then
    # 디렉토리에서 mp4 파일 순서대로
    DIR="$2"
    for f in $(ls "$DIR"/*.mp4 | sort); do
        echo "file '$f'" >> "$FILELIST"
    done
else
    # 인자로 전달된 파일들
    for f in "$@"; do
        echo "file '$f'" >> "$FILELIST"
    done
fi

echo "스티칭 대상:"
cat "$FILELIST"
echo ""

# 단순 concat (트랜지션 없이)
ffmpeg -y -f concat -safe 0 -i "$FILELIST" -c copy "$OUTPUT" 2>/dev/null

# concat 실패 시 (코덱 불일치 등) 재인코딩
if [ $? -ne 0 ]; then
    echo "코덱 불일치 → 재인코딩 모드"
    ffmpeg -y -f concat -safe 0 -i "$FILELIST" \
        -c:v libx264 -preset fast -crf 18 \
        -c:a aac -b:a 128k \
        "$OUTPUT" 2>/dev/null
fi

rm "$FILELIST"

echo "스티칭 완료: $OUTPUT"
echo "파일 크기: $(du -h "$OUTPUT" | cut -f1)"
